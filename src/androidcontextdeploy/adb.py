"""The only place that runs adb. Every command goes through AdbService._run,
which is also the single instrumentation point of the diagnostic recorder."""
from __future__ import annotations

import os
import queue
import re
import shutil
import subprocess
import threading
import time
from typing import Iterable

from androidcontextdeploy.manifest import app_root
from androidcontextdeploy.models import DeviceInfo

# In a windowed PyInstaller build every adb call would flash a console window
# on Windows. The constant is 0 elsewhere.
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# Launcher activities used when `cmd package resolve-activity` answers nothing.
_KNOWN_ACTIVITIES: dict[str, str] = {
    "com.microsoft.windowsintune.companyportal":
        "com.microsoft.windowsintune.companyportal/com.microsoft.intune.MainActivity",
    "com.azure.authenticator": "com.azure.authenticator/.AuthenticatorActivity",
    "com.microsoft.teams": "com.microsoft.teams/.activity.TeamsActivity",
    "com.microsoft.office.outlook": "com.microsoft.office.outlook/.MainActivity",
    "com.microsoft.emmx": "com.microsoft.emmx/.MainActivity",
}

KEY_ENTER = 66


def resolve_adb() -> str:
    """ADB_COMMAND, then platform-tools/ next to the tool, then adb on PATH,
    then the adb that ships inside the adbutils package."""
    if os.getenv("ADB_COMMAND"):
        return os.environ["ADB_COMMAND"]
    local = app_root() / "platform-tools" / ("adb.exe" if os.name == "nt" else "adb")
    if local.exists():
        return str(local)
    if shutil.which("adb"):
        return shutil.which("adb")
    try:
        from adbutils._utils import adb_path
        return adb_path()
    except Exception:
        return "adb"


class AdbService:
    def __init__(self, adb_command: str | None = None) -> None:
        self.adb_command = adb_command or resolve_adb()
        # Diagnostic recorder (ADR-0005), injected by the app. None = no capture.
        self.recorder = None
        # The Detection Loop and the diagnostic poller write the same remote dump
        # file; two concurrent dumps would corrupt each other.
        self._dump_lock = threading.Lock()

    def _run(self, args: Iterable[str], timeout: int = 15) -> tuple[bool, str, str]:
        args = list(args)
        command = [self.adb_command, *args]
        try:
            # adb speaks UTF-8; Windows would decode as cp1252 and choke on
            # uiautomator dumps. errors="replace" keeps a stray byte harmless.
            result = subprocess.run(
                command, capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=timeout, check=False,
                creationflags=_NO_WINDOW)
            ok, out, err = result.returncode == 0, result.stdout.strip(), result.stderr.strip()
        except FileNotFoundError:
            ok, out, err = False, "", f"adb not found: {self.adb_command}"
        except subprocess.TimeoutExpired:
            ok, out, err = False, "", f"timeout: {' '.join(command)}"
        except OSError as exc:
            ok, out, err = False, "", f"adb failed: {exc}"
        if self.recorder is not None:
            self.recorder.log_adb(args, ok, out, err)
        return ok, out, err

    def _shell(self, serial: str, *args: str, timeout: int = 15) -> tuple[bool, str, str]:
        return self._run(["-s", serial, "shell", *args], timeout=timeout)

    # ── Device ───────────────────────────────────────────────────────────
    def get_device_info(self) -> DeviceInfo:
        ok, stdout, stderr = self._run(["devices"])
        if not ok:
            return DeviceInfo(state="adb_missing", detail=stderr)
        rows = []
        for line in stdout.splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 2 and not line.startswith("*"):
                rows.append((parts[0], parts[1]))
        if not rows:
            return DeviceInfo(state="none")
        ready = [serial for serial, state in rows if state == "device"]
        if not ready:
            serial, state = rows[0]
            return DeviceInfo(state="not_ready", detail=state, serial=serial)
        serial = ready[0]
        return DeviceInfo(
            connected=True, state="connected", serial=serial,
            model=self.get_prop(serial, "ro.product.model") or "?",
            battery_level=self._battery_level(serial) or "N/A",
            work_user_id=self.get_work_user_id(serial))

    def get_prop(self, serial: str, prop: str) -> str:
        ok, stdout, _ = self._shell(serial, "getprop", prop)
        return stdout if ok else ""

    def _battery_level(self, serial: str) -> str:
        ok, stdout, _ = self._shell(serial, "dumpsys", "battery")
        for line in stdout.splitlines() if ok else []:
            if line.strip().startswith("level:"):
                return line.split(":", 1)[1].strip() + "%"
        return ""

    def get_work_user_id(self, serial: str) -> int:
        """`pm list users` prints UserInfo{<id>:<name>:<hex flags>}. The managed
        profile carries FLAG_MANAGED_PROFILE (0x20). Falls back to the first
        secondary user, then 0 -- safe on a phone with no Work Profile."""
        ok, stdout, _ = self._shell(serial, "pm", "list", "users", timeout=10)
        if not ok:
            return 0
        fallback = 0
        for match in re.finditer(r"UserInfo\{(\d+):[^:}]*:([0-9a-fA-F]+)\}", stdout):
            uid, flags = int(match.group(1)), int(match.group(2), 16)
            if uid == 0:
                continue
            if flags & 0x20:
                return uid
            fallback = fallback or uid
        return fallback

    # ── Settings ─────────────────────────────────────────────────────────
    def put_setting(self, serial: str, namespace: str, key: str, value: str) -> tuple[bool, str]:
        ok, _, err = self._shell(serial, "settings", "put", namespace, key, value)
        return ok, err

    def get_setting(self, serial: str, namespace: str, key: str) -> str:
        ok, stdout, _ = self._shell(serial, "settings", "get", namespace, key, timeout=10)
        value = stdout.strip()
        return "" if not ok or value == "null" else value

    def lockdown(self, serial: str) -> tuple[bool, bool]:
        """Hide Developer options, then turn USB debugging off.

        ORDER MATTERS: `adb_enabled 0` severs ADB, so it must be the very last
        command. Returns (developer options hidden and confirmed, adb cut sent)."""
        self.put_setting(serial, "global", "development_settings_enabled", "0")
        dev_off = self.get_setting(serial, "global", "development_settings_enabled") == "0"
        ok_adb, _ = self.put_setting(serial, "global", "adb_enabled", "0")
        return dev_off, ok_adb

    # ── Screen ───────────────────────────────────────────────────────────
    def get_focused_activity(self, serial: str) -> str:
        """The focused window line from `dumpsys window` (~100 ms). A cheap
        "the screen changed" signal for the Detection Loop."""
        ok, stdout, _ = self._shell(serial, "dumpsys", "window", timeout=10)
        for line in stdout.splitlines() if ok else []:
            line = line.strip()
            if line.startswith(("mCurrentFocus", "mFocusedApp")):
                return line
        return ""

    @staticmethod
    def focus_is_play_store(focus_line: str) -> bool:
        # The managed Play Store shares com.android.vending with the public one;
        # at the Enrollment gate it is the Company Portal that brings it up.
        return "com.android.vending" in focus_line.lower()

    def is_play_store_focused(self, serial: str) -> bool:
        return self.focus_is_play_store(self.get_focused_activity(serial))

    def dump_ui_xml(self, serial: str) -> str:
        """The current UI tree as XML, or "" when the dump fails (secure screen,
        busy device) -- the caller simply tries again."""
        remote = "/sdcard/acd_ui_dump.xml"
        with self._dump_lock:
            ok, stdout, _ = self._shell(serial, "uiautomator", "dump", remote, timeout=20)
            if not ok or "dumped to" not in stdout.lower():
                return ""
            ok, xml_text, _ = self._shell(serial, "cat", remote, timeout=20)
        return xml_text if ok and xml_text.lstrip().startswith("<") else ""

    def tap(self, serial: str, x: int, y: int) -> tuple[bool, str]:
        ok, _, err = self._shell(serial, "input", "tap", str(int(x)), str(int(y)))
        return ok, err

    def inject_text(self, serial: str, text: str) -> tuple[bool, str]:
        # `input text` goes through the Android shell: spaces become %s and the
        # whole string is single-quoted so &, |, ; in a password stay literal.
        quoted = "'" + text.replace(" ", "%s").replace("'", "'\\''") + "'"
        ok, _, err = self._shell(serial, "input", "text", quoted)
        return ok, err

    def press_key(self, serial: str, keyevent: int) -> tuple[bool, str]:
        ok, _, err = self._shell(serial, "input", "keyevent", str(keyevent))
        return ok, err

    # ── Apps ─────────────────────────────────────────────────────────────
    def open_play_store(self, serial: str, package_id: str, user_id: int = 0) -> tuple[bool, str]:
        args = ["am", "start"] + (["--user", str(user_id)] if user_id else [])
        args += ["-a", "android.intent.action.VIEW", "-d", f"market://details?id={package_id}"]
        ok, _, err = self._shell(serial, *args)
        return ok, err

    def is_installed(self, serial: str, package_id: str, user_id: int = 0) -> bool:
        # --user limits the search to the Work Profile: an app pushed by Intune
        # only exists under that user.
        args = ["pm", "list", "packages"] + (["--user", str(user_id)] if user_id else [])
        _, stdout, _ = self._shell(serial, *args, package_id, timeout=10)
        return f"package:{package_id}" in stdout.split()

    def wait_for_package(self, serial: str, package_id: str, user_id: int = 0,
                         timeout: float = 300, poll_interval: float = 1.0) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.is_installed(serial, package_id, user_id):
                return True
            time.sleep(poll_interval)
        return False

    def _launch_activity(self, serial: str, package_id: str, user_id: int = 0) -> str:
        args = ["cmd", "package", "resolve-activity", "--brief",
                "-c", "android.intent.category.LAUNCHER"]
        args += (["--user", str(user_id)] if user_id else []) + [package_id]
        _, stdout, _ = self._shell(serial, *args, timeout=10)
        for line in stdout.splitlines():
            if line.strip().startswith(package_id + "/"):
                return line.strip()
        return _KNOWN_ACTIVITIES.get(package_id, f"{package_id}/.MainActivity")

    def open_app(self, serial: str, package_id: str, user_id: int = 0) -> tuple[bool, str]:
        """`am start -n` on the resolved launcher. Android Enterprise refuses
        this for a Work Profile app ("permission to access user") -- that is
        expected and becomes a Manual Action. `monkey` is a fallback on user 0
        only; it cannot target a managed profile."""
        activity = self._launch_activity(serial, package_id, user_id)
        args = ["am", "start"] + (["--user", str(user_id)] if user_id else []) + ["-n", activity]
        ok, stdout, err = self._shell(serial, *args)
        # am start can exit 0 while printing "Error: ..."
        if ok and "error:" not in f"{stdout}\n{err}".lower():
            return True, ""
        if not user_id:
            ok2, _, err2 = self._shell(serial, "monkey", "-p", package_id,
                                       "-c", "android.intent.category.LAUNCHER", "1")
            return (True, "") if ok2 else (False, err or stdout or err2)
        return False, err or stdout

    def pin_to_home(self, serial: str, package_id: str, app_name: str,
                    user_id: int = 0) -> tuple[bool, str]:
        activity = self._launch_activity(serial, package_id, user_id)
        extras = ["--es", "android.intent.extra.shortcut.NAME", app_name,
                  "--ez", "android.intent.extra.shortcut.DUPLICATE", "false",
                  "--ecn", "android.intent.extra.shortcut.INTENT", activity]
        action = ["am", "broadcast", "-a", "com.android.launcher.action.INSTALL_SHORTCUT"]
        if "samsung" in self.get_prop(serial, "ro.product.manufacturer").lower():
            ok, out, err = self._shell(serial, *action, "-n",
                "com.sec.android.app.launcher/"
                "com.sec.android.app.launcher.shortcuts.InstallShortcutReceiver", *extras)
            if ok and "error" not in err.lower():
                return True, " | ".join(p for p in (out, err) if p)
            action = ["am", "broadcast", "-a", "com.sec.android.launcher.action.INSTALL_SHORTCUT"]
        ok, out, err = self._shell(serial, *action, *extras)
        return ok, " | ".join(p for p in (out, err) if p)


class DeviceMonitor:
    """Polls `adb devices` in the background; the UI drains the latest state."""

    def __init__(self, adb: AdbService) -> None:
        self.adb = adb
        self.events: queue.Queue[DeviceInfo] = queue.Queue()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self, interval_seconds: float = 4.0) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, args=(interval_seconds,),
                                        daemon=True, name="device-monitor")
        self._thread.start()

    def _loop(self, interval_seconds: float) -> None:
        while not self._stop.is_set():
            self.events.put(self.adb.get_device_info())
            self._stop.wait(interval_seconds)

    def stop(self) -> None:
        self._stop.set()

    def drain(self) -> list[DeviceInfo]:
        items: list[DeviceInfo] = []
        while True:
            try:
                items.append(self.events.get_nowait())
            except queue.Empty:
                return items
