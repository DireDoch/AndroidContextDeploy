"""AdbService against a fake `subprocess.run`: what it sends, and how it reads the answers."""
from __future__ import annotations

import subprocess
import time
from types import SimpleNamespace

import pytest

from androidcontextdeploy import adb as adb_module
from androidcontextdeploy.adb import NOT_TYPEABLE, AdbService, DeviceMonitor, resolve_adb, typing_script
from androidcontextdeploy.diagnostics import DiagnosticRecorder
from androidcontextdeploy.models import DeviceInfo


class FakeAdbProcess:
    """Answers an adb command line by the first fragment it contains; records every call."""

    def __init__(self) -> None:
        self.answers: dict[str, tuple[int, str, str]] = {}
        self.calls: list[tuple[list[str], dict]] = []

    def __call__(self, command, **kwargs):
        self.calls.append((command, kwargs))
        line = " ".join(command[1:])
        for fragment, (code, out, err) in self.answers.items():
            if fragment in line:
                return SimpleNamespace(returncode=code, stdout=out, stderr=err)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    def lines(self) -> list[str]:
        return [" ".join(command[1:]) for command, _ in self.calls]


@pytest.fixture
def process(monkeypatch) -> FakeAdbProcess:
    fake = FakeAdbProcess()
    monkeypatch.setattr(adb_module.subprocess, "run", fake)
    return fake


def _as_android_types_it(script: str) -> str:
    """What the phone ends up with: the shell removes the quoting, then `input
    text` turns each %s into a space (the rule of Android's Input.java)."""
    typed = ""
    for line in script.splitlines():
        argument = line.removeprefix("input text '").removesuffix("'").replace("'\\''", "'")
        chars, escape = list(argument), False
        i = 0
        while i < len(chars):
            if escape:
                escape = False
                if chars[i] == "s":
                    chars[i] = " "
                    del chars[i - 1]
                    i -= 1
            if chars[i] == "%":
                escape = True
            i += 1
        typed += "".join(chars)
    return typed


@pytest.mark.parametrize("secret", ["plain", "two words", "ab%scd", "%s%s", "a b%sc %%s d% e",
                                    "p\"a\\$x&|;()<>*?!#~`'q", ""])
def test_typing_script_types_the_text_exactly(secret: str) -> None:
    assert _as_android_types_it(typing_script(secret)) == secret


def test_a_literal_percent_s_is_split_across_two_commands() -> None:
    assert typing_script("ab%scd") == "input text 'ab%'\ninput text 'scd'\n"


def test_secrets_go_on_stdin_never_on_the_command_line(process: FakeAdbProcess) -> None:
    ok, _ = AdbService("adb").inject_text("X", "S3cret Pass")
    command, kwargs = process.calls[-1]
    assert ok
    assert command == ["adb", "-s", "X", "shell"]
    assert "S3cret" not in " ".join(command) and "S3cret" in kwargs["input"]


def test_text_adb_cannot_type_is_refused_before_anything_is_sent(process: FakeAdbProcess) -> None:
    assert AdbService("adb").inject_text("X", "Pässword") == (False, NOT_TYPEABLE)
    assert not process.calls


def test_input_that_throws_is_a_failure_even_with_exit_code_zero(process: FakeAdbProcess) -> None:
    process.answers["shell"] = (0, "", "Exception occurred while executing 'text':")
    ok, error = AdbService("adb").inject_text("X", "abc")
    assert not ok and "Exception" in error


def test_the_diagnostic_log_never_sees_what_was_typed(process: FakeAdbProcess, tmp_path) -> None:
    service = AdbService("adb")
    service.recorder = DiagnosticRecorder(tmp_path, "adb")
    session = service.recorder.start_session()
    service.inject_text("X", "S3cret Pass")
    log = (session / "adb.log").read_text(encoding="utf-8")
    assert "<stdin>" in log and "S3cret" not in log


def test_a_connected_phone_is_read_in_full(process: FakeAdbProcess) -> None:
    process.answers.update({
        "devices": (0, "List of devices attached\nABC123\tdevice\n", ""),
        "getprop ro.product.model": (0, "Pixel 8\n", ""),
        "dumpsys battery": (0, "Current Battery Service state:\n  level: 87\n", ""),
        "pm list users": (0, "Users:\n\tUserInfo{0:Owner:c13} running\n\tUserInfo{10:Work profile:1030} running\n", ""),
    })
    info = AdbService("adb").get_device_info()
    assert (info.connected, info.serial, info.model, info.battery_level, info.work_user_id) == \
        (True, "ABC123", "Pixel 8", "87%", 10)


@pytest.mark.parametrize(("answer", "state", "detail"), [
    ((0, "List of devices attached\n\n", ""), "none", ""),
    ((0, "List of devices attached\nABC123\tunauthorized\n", ""), "not_ready", "unauthorized"),
    ((1, "", "cannot connect to daemon"), "adb_missing", "cannot connect to daemon"),
])
def test_a_phone_that_is_not_ready_says_why(process: FakeAdbProcess, answer, state, detail) -> None:
    process.answers["devices"] = answer
    info = AdbService("adb").get_device_info()
    assert (info.connected, info.state, info.detail) == (False, state, detail)


def test_work_profile_falls_back_to_a_secondary_user_then_zero(process: FakeAdbProcess) -> None:
    service = AdbService("adb")
    process.answers["pm list users"] = (0, "UserInfo{0:Owner:c13}\nUserInfo{11:Guest:410}\n", "")
    assert service.get_work_user_id("X") == 11
    process.answers["pm list users"] = (1, "", "error")
    assert service.get_work_user_id("X") == 0


def test_settings_read_null_as_empty(process: FakeAdbProcess) -> None:
    process.answers["settings get"] = (0, "null\n", "")
    assert AdbService("adb").get_setting("X", "system", "missing") == ""


def test_lockdown_cuts_adb_last(process: FakeAdbProcess) -> None:
    process.answers["settings get global development_settings_enabled"] = (0, "0", "")
    assert AdbService("adb").lockdown("X") == (True, True)
    assert process.lines()[-1].endswith("settings put global adb_enabled 0")


def test_focused_window_and_screen_dump(process: FakeAdbProcess) -> None:
    service = AdbService("adb")
    process.answers.update({
        "dumpsys window": (0, "junk\n  mCurrentFocus=Window{1 u0 com.android.vending/.Main}\n", ""),
        "uiautomator dump": (0, "UI hierchary dumped to: /sdcard/acd_ui_dump.xml", ""),
        "cat /sdcard/acd_ui_dump.xml": (0, "<?xml version='1.0'?><hierarchy/>", ""),
    })
    assert service.is_play_store_focused("X")
    assert service.dump_ui_xml("X").startswith("<?xml")
    process.answers["uiautomator dump"] = (0, "ERROR: could not get idle state.", "")
    assert service.dump_ui_xml("X") == ""


def test_packages_are_matched_exactly_in_the_work_profile(process: FakeAdbProcess) -> None:
    service = AdbService("adb")
    process.answers["pm list packages"] = (0, "package:com.x.beta\npackage:com.y\n", "")
    assert not service.is_installed("X", "com.x", 10)
    assert service.is_installed("X", "com.y", 10)
    assert "pm list packages --user 10 com.y" in process.lines()[-1]
    assert service.wait_for_package("X", "com.y", 10, timeout=1)
    assert not service.wait_for_package("X", "com.x", 10, timeout=0)


def test_open_app_prefers_the_phone_then_the_catalog_activity(process: FakeAdbProcess) -> None:
    service = AdbService("adb")
    assert service.open_app("X", "com.x", 0, activity="com.x/.FromCatalog") == (True, "")
    assert process.lines()[-1].endswith("am start -n com.x/.FromCatalog")
    process.answers["resolve-activity"] = (0, "priority=0\ncom.x/.FromPhone\n", "")
    service.open_app("X", "com.x", 0, activity="com.x/.FromCatalog")
    assert process.lines()[-1].endswith("am start -n com.x/.FromPhone")


def test_a_work_profile_app_that_will_not_open_is_reported(process: FakeAdbProcess) -> None:
    service = AdbService("adb")
    process.answers["am start"] = (0, "Error: permission to access user 10", "")
    ok, error = service.open_app("X", "com.x", 10)
    assert not ok and "permission" in error
    ok, _ = service.open_app("X", "com.x", 0)        # user 0: monkey takes over
    assert ok and "monkey -p com.x" in process.lines()[-1]


def test_store_tap_type_and_pin(process: FakeAdbProcess) -> None:
    service = AdbService("adb")
    service.open_play_store("X", "com.x", 10)
    assert "am start --user 10 -a android.intent.action.VIEW -d market://details?id=com.x" in process.lines()[-1]
    service.tap("X", 10.6, 20.2)
    assert process.lines()[-1].endswith("input tap 10 20")
    service.press_key("X", 66)
    assert process.lines()[-1].endswith("input keyevent 66")
    process.answers["getprop ro.product.manufacturer"] = (0, "samsung", "")
    ok, _ = service.pin_to_home("X", "com.x", "X app", 10, activity="com.x/.Main")
    assert ok and "com.sec.android.app.launcher" in process.lines()[-1]


@pytest.mark.parametrize(("error", "message"), [
    (FileNotFoundError(), "adb not found"),
    (subprocess.TimeoutExpired("adb", 1), "timeout"),
    (PermissionError("denied"), "adb failed"),
])
def test_adb_failures_become_messages(monkeypatch, error, message) -> None:
    def boom(*args, **kwargs):
        raise error
    monkeypatch.setattr(adb_module.subprocess, "run", boom)
    ok, out, err = AdbService("adb")._run(["devices"])
    assert (ok, out) == (False, "") and message in err


def test_adb_is_looked_up_in_the_documented_order(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("ADB_COMMAND", "/custom/adb")
    assert resolve_adb() == "/custom/adb"
    monkeypatch.delenv("ADB_COMMAND")
    monkeypatch.setattr(adb_module, "app_root", lambda: tmp_path)
    monkeypatch.setattr(adb_module.shutil, "which", lambda name: "/usr/bin/adb")
    assert resolve_adb() == "/usr/bin/adb"
    local = tmp_path / "platform-tools" / ("adb.exe" if adb_module.os.name == "nt" else "adb")
    local.parent.mkdir()
    local.touch()
    assert resolve_adb() == str(local)


def test_device_monitor_reports_in_the_background() -> None:
    phone = SimpleNamespace(get_device_info=lambda: DeviceInfo(connected=True, serial="X"))
    monitor = DeviceMonitor(phone)  # type: ignore[arg-type]
    monitor.start(interval_seconds=0.01)
    monitor.start()                                  # a second start is a no-op
    deadline = time.time() + 2
    seen: list[DeviceInfo] = []
    while not seen and time.time() < deadline:
        seen = monitor.drain()
        time.sleep(0.01)
    monitor.stop()
    assert seen and seen[0].serial == "X"
