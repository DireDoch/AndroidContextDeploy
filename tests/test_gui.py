"""The real window, driven the way a technician drives it, with a fake phone.

These open Tk windows. Without a display they are skipped -- except where
ACD_REQUIRE_GUI=1 (the Linux CI job, under Xvfb), where that is an error.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import time
import tkinter as tk
from pathlib import Path

import customtkinter as ctk
import numpy as np
import pytest
from PIL import Image

from androidcontextdeploy import app as app_module
from androidcontextdeploy import i18n
from androidcontextdeploy.i18n import t
from androidcontextdeploy.manifest import parse_manifest
from androidcontextdeploy.models import DeviceInfo
from androidcontextdeploy.ui.mirror import MirrorPanel

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.gui


def _display_available() -> bool:
    try:
        tk.Tk().destroy()
    except tk.TclError:
        return False
    return True


if not _display_available():
    if os.environ.get("ACD_REQUIRE_GUI"):
        raise RuntimeError("ACD_REQUIRE_GUI=1 but Tk cannot open a window")
    pytest.skip("no display", allow_module_level=True)

i18n.load(ROOT, "en")


def _pump(window: tk.Misc, until, timeout: float = 20.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        window.update()
        if until():
            return
        time.sleep(0.02)
    raise AssertionError("the window never reached the expected state")


# ── The Mirror: a click lands on the pixel under the pointer ─────────────
W, H = 464, 1024


def _gradient() -> np.ndarray:
    """BGR frame whose colour says where it is: blue = x, green = y, red = 0."""
    ys, xs = np.mgrid[0:H, 0:W]
    frame = np.zeros((H, W, 3), np.uint8)
    frame[:, :, 0] = 8 + xs * 247 // (W - 1)
    frame[:, :, 1] = 8 + ys * 247 // (H - 1)
    return frame


def _window_pixels(root: tk.Misc, folder: Path) -> Image.Image:
    """What X actually drew in the window. ImageMagick's `import -window` reads
    the window itself, so screen scaling and other windows cannot get in the way."""
    if shutil.which("import") is None:
        if os.environ.get("ACD_REQUIRE_GUI"):
            raise RuntimeError("ACD_REQUIRE_GUI=1 needs ImageMagick's `import`")
        pytest.skip("ImageMagick's `import` is needed to read the window's pixels")
    path = folder / "window.png"
    subprocess.run(["import", "-silent", "-window", hex(root.winfo_id()), str(path)], check=True)
    return Image.open(path).convert("RGB")


def _widget_at(widget: tk.Misc, x: int, y: int) -> tk.Misc:
    """The deepest mapped widget under a screen point, children in Tk's stacking
    order (topmost last) -- what receives the click. winfo_containing asks the X
    server instead, which answers None when another desktop window covers ours."""
    for child in reversed(widget.tk.splitlist(widget.tk.call("winfo", "children", widget._w))):
        child_widget = widget.nametowidget(child)
        if (child_widget.winfo_ismapped()
                and child_widget.winfo_rootx() <= x < child_widget.winfo_rootx() + child_widget.winfo_width()
                and child_widget.winfo_rooty() <= y < child_widget.winfo_rooty() + child_widget.winfo_height()):
            return _widget_at(child_widget, x, y)
    return widget


@pytest.mark.parametrize("size", ["normal", "large"])
@pytest.mark.parametrize("scaling", [1.0, 1.5])
def test_a_click_on_the_mirror_touches_the_pixel_under_the_pointer(scaling: float, size: str, tmp_path) -> None:
    ctk.set_widget_scaling(scaling)
    root = ctk.CTk()
    try:
        # Room for the enlarged Mirror at 150 %: 560 px * 1.5 plus the margins.
        root.geometry("1100x1040+0+0")
        root.attributes("-topmost", True)
        root.grid_rowconfigure(0, weight=1)
        touches: list[tuple[float, float, str]] = []
        panel = MirrorPanel(root, on_touch=lambda x, y, a: touches.append((x, y, a)), on_resize=lambda s: None)
        panel.grid(row=0, column=0, sticky="ns")
        panel._apply_size(size)
        frame = _gradient()
        for _ in range(3):                           # the first frame measures, the next ones settle
            _pump(root, lambda: True)
            panel.show_frame(frame)
        _pump(root, lambda: True)
        time.sleep(0.2)
        _pump(root, lambda: True)

        ox, oy = root.winfo_rootx(), root.winfo_rooty()
        shot = _window_pixels(root, tmp_path)
        screen = panel._screen
        errors: list[float] = []
        for fy in (0.03, 0.2, 0.5, 0.8, 0.97):
            for fx in (0.03, 0.2, 0.5, 0.8, 0.97):
                x = screen.winfo_rootx() + int(fx * screen.winfo_width())
                y = screen.winfo_rooty() + int(fy * screen.winfo_height())
                red, green, blue = shot.getpixel((x - ox, y - oy))
                target = _widget_at(root, x, y)
                touches.clear()
                where = {"x": x - target.winfo_rootx(), "y": y - target.winfo_rooty(), "rootx": x, "rooty": y}
                target.event_generate("<Button-1>", **where)
                target.event_generate("<ButtonRelease-1>", **where)
                root.update()
                presses = [touch for touch in touches if touch[2] == "down"]
                if red != 0 or green < 8 or blue < 8:        # the margin, not the picture
                    assert not presses, f"a press beside the picture ({fx}, {fy}) reached the phone"
                    continue
                assert presses, f"a press on the picture ({fx}, {fy}) was lost"
                want = ((blue - 8) / 247 * (W - 1), (green - 8) / 247 * (H - 1))
                errors.append(max(abs(presses[0][0] - want[0]), abs(presses[0][1] - want[1])))
        assert len(errors) >= 5, "too few clicks landed on the picture to judge"
        assert max(errors) <= 6, f"stream pixels between the touch and the pointer: {errors}"
    finally:
        root.destroy()
        ctk.set_widget_scaling(1.0)


# ── A whole Session in the real window ───────────────────────────────────
MANIFEST = parse_manifest({
    "organization": "Example Corp",
    "device_settings": [{"name": "Timeout", "namespace": "system", "key": "screen_off_timeout", "value": "600000"}],
    "catalog": [
        {"name": "Teams", "package_id": "com.microsoft.teams", "pin": True},
        {"name": "Edge", "package_id": "com.microsoft.emmx", "selected": False},
    ],
})


class FakePhone:
    """The AdbService surface the window and the Modules use."""

    adb_command = "adb"

    def __init__(self) -> None:
        self.recorder = None
        self.settings: dict[tuple[str, str], str] = {}
        self.locked = False

    def get_device_info(self) -> DeviceInfo:
        return DeviceInfo(connected=True, state="connected", serial="FAKE", model="Pixel 8",
                          battery_level="80%", work_user_id=10)

    def put_setting(self, serial, namespace, key, value):
        self.settings[(namespace, key)] = value
        return True, ""

    def get_setting(self, serial, namespace, key):
        return self.settings.get((namespace, key), "")

    def get_work_user_id(self, serial):
        return 10

    def is_installed(self, serial, package_id, user=0):
        return package_id == "com.microsoft.teams"

    def wait_for_package(self, serial, package_id, user=0, timeout=0, poll_interval=0):
        return self.is_installed(serial, package_id, user)

    def open_play_store(self, serial, package_id, user=0):
        return True, ""

    def pin_to_home(self, serial, package_id, name, user=0, activity=""):
        return True, ""

    def lockdown(self, serial):
        self.locked = True
        return True, True


class FakeMirror:
    def __init__(self, logger, adb_command) -> None:
        self.state, self.available = "idle", True
        self.touches: list[tuple[float, float, str]] = []
        self._latest: tuple[int, object] = (0, None)

    def start(self, serial) -> bool:
        self.state, self._latest = "running", (1, np.full((1024, 464, 3), 90, np.uint8))
        return True

    def stop(self) -> None:
        self.state = "idle"

    def get_frame(self):
        return self._latest

    def touch(self, x, y, action) -> None:
        self.touches.append((x, y, action))


@pytest.fixture
def window(monkeypatch):
    phone = FakePhone()
    monkeypatch.setattr(app_module, "AdbService", lambda: phone)
    monkeypatch.setattr(app_module, "MirrorService", FakeMirror)
    monkeypatch.setattr(app_module.messagebox, "askyesno", lambda *a, **k: True)
    deployment = app_module.DeploymentApp(MANIFEST)
    yield deployment, phone
    deployment._on_close()


def _console(deployment) -> str:
    return deployment.console._textbox.get("1.0", "end")


def test_a_whole_session_from_plugging_in_to_lockdown(window) -> None:
    deployment, phone = window
    _pump(deployment, lambda: deployment.device.connected and deployment.mirror._streaming)
    assert "Example Corp" in deployment.form.winfo_children()[0].winfo_children()[1].cget("text")

    deployment._run_current()
    assert not deployment.runner.busy, "nothing runs before a Session"

    deployment.form.email_var.set("not-an-email")
    deployment.form.password_var.set("pw")
    deployment.form._submit()
    assert deployment.session is None

    deployment.form.email_var.set("alex.martin@example.com")
    deployment.form.password_var.set("Pässword")
    deployment.form._toggle_password()
    deployment.form._submit()
    assert deployment.session is not None
    _pump(deployment, lambda: "cannot type" in _console(deployment))

    for module in ("device_settings", "applications", "final_check"):
        deployment._run_current()
        _pump(deployment, lambda module=module: module in deployment.completed)
    assert phone.settings[("system", "screen_off_timeout")] == "600000"
    kinds = {result.name: result.kind for result in deployment.runner.results}
    assert kinds["Timeout"] == "OK" and kinds["Teams"] == "OK" and kinds["Edge"] == "N/A"
    assert "CHECKLIST" in _console(deployment).upper()

    deployment._lockdown()
    lockdown = t("result.lockdown.name")
    _pump(deployment, lambda: any(r.name == lockdown and r.kind == "OK" for r in deployment.runner.results))
    assert phone.locked

    deployment._reset_session()
    assert deployment.session is None and deployment.current == "device_settings"


def test_runner_events_reach_the_cards_and_the_sidebar(window) -> None:
    deployment, _ = window
    _pump(deployment, lambda: deployment.device.connected)
    deployment.form.email_var.set("alex.martin@example.com")
    deployment.form.password_var.set("x")
    deployment.form._submit()
    deployment._show("applications")
    deployment.cards.build_app_statuses(["Teams"])
    deployment.sidebar.build_apps("applications", ["Teams"])
    runner = deployment.runner
    runner.emit({"type": "started", "module": "applications"})
    runner.emit_progress(0.5, "halfway")
    runner.emit({"type": "enrollment", "app": "Teams", "active": True})
    runner.emit({"type": "auth_required", "app": "Teams"})
    runner.emit_app_status("Teams", "auth_pending")
    runner.emit_manual_action("Teams", "Open Teams in the Mirror")
    _pump(deployment, lambda: deployment.cards._confirm_btn.cget("state") == "normal")
    assert deployment.cards._cancel_btn.cget("state") == "normal"
    assert deployment.status_var.get() == t("status.sign_in", app="Teams")

    deployment._confirm_auth()
    deployment._cancel_session()
    assert runner.auth_gate.is_set() and runner.cancel_gate.is_set()
    runner.emit({"type": "auth_done", "app": "Teams"})
    runner.emit({"type": "finished", "module": "applications", "kinds": ["WARNING"]})
    _pump(deployment, lambda: "applications" in deployment.issues)
    assert deployment.current == "final_check"


def test_the_mirror_forwards_clicks_resizes_and_follows_the_phone(window) -> None:
    deployment, _ = window
    _pump(deployment, lambda: deployment.mirror._streaming)
    video = deployment.mirror._video
    middle = {"x": video.winfo_width() // 2, "y": video.winfo_height() // 2}
    video.event_generate("<Button-1>", **middle)
    video.event_generate("<B1-Motion>", **middle)
    video.event_generate("<ButtonRelease-1>", **middle)
    _pump(deployment, lambda: len(deployment.mirror_service.touches) == 3)
    x, y, _ = deployment.mirror_service.touches[0]
    assert x == pytest.approx(232, abs=3) and y == pytest.approx(512, abs=3)

    deployment.mirror._toggle_enlarge()
    deployment.mirror._toggle_minimize()
    deployment.mirror._toggle_minimize()

    deployment.mirror_service.state = "failed"
    _pump(deployment, lambda: t("mirror.see_console") in deployment.mirror._state.cget("text"))

    deployment.monitor.events.put(DeviceInfo())
    _pump(deployment, lambda: not deployment.device.connected)
    assert deployment.mirror_service.state == "idle"


def test_a_broken_manifest_is_reported_before_the_window_opens(monkeypatch, tmp_path) -> None:
    (tmp_path / "deploy.json").write_text('{"organization": ""}', encoding="utf-8")
    shown: list[str] = []
    monkeypatch.setattr(app_module, "app_root", lambda: tmp_path)
    monkeypatch.setattr(app_module.messagebox, "showerror", lambda title, message: shown.append(message))
    assert app_module.main([]) == 1
    assert "organization" in shown[0]


def test_main_loads_the_language_and_opens_the_window(monkeypatch) -> None:
    opened: list[bool] = []

    class Window:
        def __init__(self, manifest, diag=False) -> None:
            opened.append(diag)

        def mainloop(self) -> None:
            pass

    monkeypatch.setattr(app_module, "DeploymentApp", Window)
    assert app_module.main(["--lang", "fr", "--diag"]) == 0
    assert opened == [True] and t("mirror.title") == "▌MIROIR"
    i18n.load(ROOT, "en")
