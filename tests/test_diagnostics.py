"""Diagnostic capture (ADR-0005): masking and the passive poller."""
from __future__ import annotations

from pathlib import Path

from androidcontextdeploy.diagnostics import MASK, DiagnosticPoller, DiagnosticRecorder


def _screen(label: str) -> str:
    return ('<?xml version="1.0" encoding="UTF-8"?><hierarchy rotation="0">'
            f'<node class="android.widget.Button" text="{label}" clickable="true"'
            ' bounds="[80,600][1000,720]"/></hierarchy>')


class CountingAdb:
    def __init__(self, dumps: list[str]) -> None:
        self.dumps = list(dumps)
        self.actions: list[tuple] = []

    def dump_ui_xml(self, serial):
        return self.dumps.pop(0) if self.dumps else ""

    def tap(self, *a):
        self.actions.append(("tap", a))

    def inject_text(self, *a):
        self.actions.append(("text", a))


def _make(dumps, tmp: Path, active=True, serial="X"):
    adb = CountingAdb(dumps)
    # A bogus adb: the PNG is skipped cleanly, the XML and trace still land.
    recorder = DiagnosticRecorder(tmp, adb_command="adb-does-not-exist")
    if active:
        recorder.start_session()
    return DiagnosticPoller(adb, recorder, lambda: serial, poll_interval=0.01), adb, recorder


def _xml_count(recorder) -> int:
    return len(list(recorder._session_dir.glob("*.xml"))) if recorder._session_dir else 0


def test_secrets_are_masked_before_writing(tmp_path) -> None:
    recorder = DiagnosticRecorder(tmp_path, "adb")
    session = recorder.start_session()
    recorder.set_secrets("my pass word", "+1 202 555 0143")
    recorder.log_adb(["shell", "input", "text", "'my%spass%sword'"], True, "", "")
    recorder.log_adb(["shell", "input", "text", "'+1 202 555 0143'"], True, "", "")
    log = (session / "adb.log").read_text(encoding="utf-8")
    assert "pass" not in log and "0143" not in log
    assert log.count(MASK) == 2


def test_captures_each_distinct_screen_without_acting(tmp_path) -> None:
    poller, adb, recorder = _make([_screen("Continue"), _screen("Accept"), _screen("Finish")], tmp_path)
    assert all(poller.poll_once() for _ in range(3))
    assert _xml_count(recorder) == 3
    assert adb.actions == [], "the poller NEVER acts on the phone"


def test_same_screen_is_captured_once(tmp_path) -> None:
    poller, _, recorder = _make([_screen("Continue"), _screen("Continue")], tmp_path)
    poller.poll_once()
    poller.poll_once()
    assert _xml_count(recorder) == 1


def test_pause_suspends_capture(tmp_path) -> None:
    poller, _, recorder = _make([_screen("Continue")], tmp_path)
    poller.pause()
    assert not poller.poll_once() and _xml_count(recorder) == 0
    poller.resume()
    assert poller.poll_once() and _xml_count(recorder) == 1


def test_nothing_without_session_or_device(tmp_path) -> None:
    assert not _make([_screen("Continue")], tmp_path, active=False)[0].poll_once()
    poller, _, recorder = _make([_screen("Continue")], tmp_path, serial="")
    assert not poller.poll_once() and _xml_count(recorder) == 0
