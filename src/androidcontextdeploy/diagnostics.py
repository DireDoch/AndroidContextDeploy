"""Diagnostic capture (ADR-0005), off unless the tool is started with --diag.

Every adb command goes to adb.log; every new screen seen gets its raw XML, a
PNG and a trace.jsonl line with the ScreenDetector's verdict -- i.e. what the
tool was about to do. That is what a contributor needs to teach the tool a
screen it has never seen (manual, chapter 7).

Non-negotiable safeguards:
- The session password and phone number are replaced by a mask BEFORE anything
  is written, including the `input text` encoding of spaces as %s.
- diag/ is gitignored: PNGs can show the phone number in pixels. Only masked
  XML fixtures under tests/ belong in git.
"""
from __future__ import annotations

import json
import subprocess
import threading
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable

from androidcontextdeploy.detection import ScreenDetector, screen_signature
from androidcontextdeploy.models import ScreenAnalysis

MASK = "█████MASKED█████"
_MAX_OUTPUT = 400
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


class DiagnosticRecorder:
    """Observational only: inactive until start_session(), never changes behaviour."""

    def __init__(self, root_dir: Path, adb_command: str) -> None:
        self._root = Path(root_dir) / "diag"
        self._adb_command = adb_command
        self._secrets: list[str] = []
        self._session_dir: Path | None = None
        self._lock = threading.Lock()
        self._screen_index = 0
        self._last_signature = ""

    def start_session(self) -> Path:
        session_dir = self._root / datetime.now().strftime("session_%Y-%m-%d_%Hh%M%S")
        session_dir.mkdir(parents=True, exist_ok=True)
        with self._lock:
            self._session_dir = session_dir
            self._screen_index = 0
            self._last_signature = ""
        return session_dir

    def stop_session(self) -> None:
        with self._lock:
            self._session_dir = None
        self._secrets = []

    def set_secrets(self, *values: str) -> None:
        variants = {v for value in values if value for v in (value, value.replace(" ", "%s"))}
        # Longest first, so a short secret never half-masks a longer one.
        self._secrets = sorted(variants, key=len, reverse=True)

    @property
    def active(self) -> bool:
        return self._session_dir is not None

    def mask(self, text: str) -> str:
        for secret in self._secrets:
            text = text.replace(secret, MASK)
        return text

    def log_adb(self, args: Iterable[object], ok: bool, stdout: str, stderr: str) -> None:
        if not self.active:
            return
        lines = [f"[{datetime.now():%H:%M:%S}] ({'ok' if ok else 'ERR'}) "
                 f"adb {self.mask(' '.join(str(a) for a in args))}"]
        for label, value in (("out", stdout), ("err", stderr)):
            value = self.mask((value or "").strip())
            if value:
                cut = value if len(value) <= _MAX_OUTPUT else f"{value[:_MAX_OUTPUT]}… (+{len(value) - _MAX_OUTPUT})"
                lines.append(f"    {label}: {cut}")
        self._append("adb.log", "\n".join(lines) + "\n")

    def capture_screen(self, serial: str, signature: str, xml_text: str,
                       analysis: ScreenAnalysis) -> None:
        """Save NNN.xml (masked), NNN.png and a trace line -- once per screen."""
        with self._lock:
            if not self.active or signature == self._last_signature:
                return
            self._last_signature = signature
            self._screen_index += 1
            tag, session_dir = f"{self._screen_index:03d}", self._session_dir
        (session_dir / f"{tag}.xml").write_text(self.mask(xml_text), encoding="utf-8")
        self._screencap(serial, session_dir / f"{tag}.png")
        record = {"i": int(tag), "t": f"{datetime.now():%H:%M:%S}", "verdict": self._verdict(analysis)}
        self._append("trace.jsonl", json.dumps(record, ensure_ascii=False) + "\n")

    def _verdict(self, a: ScreenAnalysis) -> dict[str, object]:
        def label(f) -> str:
            return self.mask((f.text or f.content_desc).strip())
        return {
            "named_screen": a.named_screen,
            "named_targets": {role: {"label": label(f), "xy": [f.center_x, f.center_y]}
                              for role, f in a.named_targets.items()},
            "mfa": a.mfa_detected,
            "mfa_hint": a.mfa_hint,
            "email_field_empty": bool(a.email_field and a.email_field.is_empty),
            "password_field_empty": bool(a.password_field and a.password_field.is_empty),
            "otc_field": bool(a.otc_field),
            "action_button": label(a.action_button) if a.action_button else None,
            "login_markers": a.login_markers,
            "managed_play_store": a.managed_play_store,
            "clickable": [self.mask(c) for c in a.clickable_labels[:12]],
        }

    def _screencap(self, serial: str, dest: Path) -> None:
        # Binary mode: a text pipe would corrupt the PNG.
        try:
            result = subprocess.run(
                [self._adb_command, "-s", serial, "exec-out", "screencap", "-p"],
                capture_output=True, timeout=20, check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except (OSError, subprocess.SubprocessError):
            return
        if result.returncode == 0 and (result.stdout or b"").startswith(_PNG_MAGIC):
            dest.write_bytes(result.stdout)

    def _append(self, filename: str, content: str) -> None:
        with self._lock:
            if self._session_dir is None:
                return
            with (self._session_dir / filename).open("a", encoding="utf-8") as handle:
                handle.write(content)


class DiagnosticPoller:
    """Captures screens the Detection Loop does not drive -- typically the apps
    the technician sets up by hand after Enrollment. Never taps or types, and
    pauses while a Detection Loop runs (those capture already)."""

    def __init__(self, adb, recorder: DiagnosticRecorder,
                 serial_provider: Callable[[], str], *, poll_interval: float = 2.0) -> None:
        self._adb = adb
        self._recorder = recorder
        self._serial_provider = serial_provider
        self._poll_interval = poll_interval
        self._detector = ScreenDetector()
        self._paused = threading.Event()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def pause(self) -> None:
        self._paused.set()

    def resume(self) -> None:
        self._paused.clear()

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._paused.clear()
        self._thread = threading.Thread(target=self._loop, name="diag-poller", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        while not self._stop.wait(self._poll_interval):
            self.poll_once()

    def poll_once(self) -> bool:
        if self._paused.is_set() or not self._recorder.active:
            return False
        serial = self._serial_provider()
        xml_text = self._adb.dump_ui_xml(serial) if serial else ""
        screen = self._detector.analyze(xml_text) if xml_text else None
        if screen is None:
            return False
        self._recorder.capture_screen(serial, screen_signature(screen), xml_text, screen)
        return True
