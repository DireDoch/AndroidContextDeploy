"""The window: Session state, queue polling, and wiring between the panels.

Rule: no adb call on the UI thread. Modules run in WorkflowRunner's thread and
talk back through queues that this class drains every 150 ms with after().
"""
from __future__ import annotations

import argparse
import re
import sys
import threading
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

from androidcontextdeploy import i18n
from androidcontextdeploy.adb import AdbService, DeviceMonitor
from androidcontextdeploy.diagnostics import DiagnosticPoller, DiagnosticRecorder
from androidcontextdeploy.i18n import t
from androidcontextdeploy.manifest import MANIFEST_NAME, Manifest, ManifestError, app_root, load_manifest
from androidcontextdeploy.mirror_service import MirrorService
from androidcontextdeploy.models import AppLogger, DeviceInfo, Result, SessionConfig
from androidcontextdeploy.modules import MODULES, Context
from androidcontextdeploy.runner import WorkflowRunner
from androidcontextdeploy.ui import theme
from androidcontextdeploy.ui.console import ConsolePanel
from androidcontextdeploy.ui.mirror import MirrorPanel
from androidcontextdeploy.ui.rail import RailPanel
from androidcontextdeploy.ui.session_form import SessionFormPanel
from androidcontextdeploy.ui.step_cards import StepCardsPanel

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MODULE_NAMES = [module.NAME for module in MODULES]
_CONSOLE_TAGS = {"OK": "OK", "WARNING": "WARN", "ERROR": "ERROR", "MANUAL": "WARN", "N/A": "system"}


class DeploymentApp(ctk.CTk):
    def __init__(self, manifest: Manifest, diag: bool = False) -> None:
        super().__init__()
        ctk.set_appearance_mode("dark")
        self.title(theme.APP_NAME)
        self.geometry("1440x940")
        self.minsize(1200, 820)
        self.configure(fg_color=theme.BG)

        self.manifest = manifest
        self.logger = AppLogger()
        self.adb = AdbService()
        self.runner = WorkflowRunner(self.adb, self.logger)
        self.recorder: DiagnosticRecorder | None = None
        self.poller: DiagnosticPoller | None = None
        if diag:
            self.recorder = DiagnosticRecorder(app_root(), self.adb.adb_command)
            self.poller = DiagnosticPoller(
                self.adb, self.recorder,
                serial_provider=lambda: self.device.serial if self.device.connected else "")
            self.adb.recorder = self.recorder
            self.runner.poller = self.poller
        self.monitor = DeviceMonitor(self.adb)
        self.mirror_service = MirrorService(self.logger, self.adb.adb_command)
        self._mirror_seq = 0
        self._mirror_failed_shown = False

        self.session: SessionConfig | None = None
        self.device = DeviceInfo()
        self.completed: set[str] = set()
        self.issues: set[str] = set()
        self.current = MODULE_NAMES[0]
        self.status_var = tk.StringVar(value=t("status.no_session"))
        self.app_checks = {app.name: tk.BooleanVar(value=app.selected) for app in manifest.catalog}

        self._build_layout()
        self.monitor.start()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(150, self._poll_queues)
        self.after(40, self._render_mirror)
        self.logger.info(t("log.app.ready", adb=self.adb.adb_command))

    # ── Layout: rail | cards + console | mirror ──────────────────────────
    def _build_layout(self) -> None:
        banner = load_banner()
        self.grid_columnconfigure(0, weight=0, minsize=290)
        self.grid_columnconfigure(1, weight=1, minsize=560)
        self.grid_columnconfigure(2, weight=0, minsize=MirrorPanel.SIZES["normal"])
        self.grid_rowconfigure(0, weight=1)

        steps = [(name, t(f"module.{name}.title")) for name in MODULE_NAMES]
        self.rail = RailPanel(self, steps, on_new_session=self._reset_session)
        self.rail.grid(row=0, column=0, sticky="nsew", padx=(14, 7), pady=14)
        self.sidebar = self.rail.steps

        center = ctk.CTkFrame(self, fg_color="transparent")
        center.grid(row=0, column=1, sticky="nsew", padx=7, pady=14)
        center.grid_columnconfigure(0, weight=1)
        center.grid_rowconfigure(0, weight=65, uniform="center")
        center.grid_rowconfigure(1, weight=35, uniform="center")

        stack = ctk.CTkFrame(center, corner_radius=16, fg_color=theme.CARD)
        stack.grid(row=0, column=0, sticky="nsew", pady=(0, 7))
        stack.grid_columnconfigure(0, weight=1)
        stack.grid_rowconfigure(0, weight=1)
        self.workflow = ctk.CTkFrame(stack, fg_color="transparent")
        self.workflow.grid(row=0, column=0, sticky="nsew")
        self.workflow.grid_columnconfigure(0, weight=1)
        self.workflow.grid_rowconfigure(0, weight=1)
        self.cards = StepCardsPanel(
            self.workflow, MODULE_NAMES, self.status_var, on_run=self._run_current,
            on_confirm_auth=self._confirm_auth, on_cancel_session=self._cancel_session,
            on_lockdown=self._lockdown, on_new_device=self._reset_session)
        self.cards.grid(row=0, column=0, sticky="nsew", padx=14, pady=14)
        self.cards.build_app_checkboxes(
            [(f"{app.name}  ({app.package_id})", self.app_checks[app.name]) for app in self.manifest.catalog])
        self.cards.build_app_statuses([])

        self.form = SessionFormPanel(stack, self.manifest.organization, on_start=self._start_session)
        self.form.grid(row=0, column=0, sticky="nsew")
        self.form.tkraise()

        self.console = ConsolePanel(center, banner)
        self.console.grid(row=1, column=0, sticky="nsew")

        self.mirror = MirrorPanel(self, on_touch=self.mirror_service.touch, on_resize=self._resize_mirror)
        self.mirror.grid(row=0, column=2, sticky="nsew", padx=(7, 14), pady=14)

        self.sidebar.set_states(self.completed, self.current, self.issues)
        self.rail.set_new_session_enabled(False)

    # ── Session ──────────────────────────────────────────────────────────
    def _start_session(self, email: str, password: str, phone: str = "") -> None:
        if not EMAIL_PATTERN.match(email):
            self.form.set_validation(t("form.invalid_email"), is_error=True)
            return
        self.session = SessionConfig(email=email, user_password=password, employee_phone=phone)
        if not all(value.isascii() for value in (email, password, phone)):
            self.logger.warn(t("log.app.not_typeable"))
        self.runner.reset()
        if self.recorder is not None and self.poller is not None:
            # Secrets first, then open the capture folder.
            self.recorder.set_secrets(password, phone)
            self.logger.info(t("log.app.diag_active", folder=self.recorder.start_session()))
            self.poller.start()
        self.logger.ok(t("log.app.session_started", email=email))
        self.rail.show_session(email)
        self.workflow.tkraise()
        self._show(MODULE_NAMES[0])
        self.status_var.set(t("status.ready", module=t(f"module.{self.current}.title")))

    def _reset_session(self) -> None:
        if self.runner.busy:
            self.logger.warn(t("log.app.busy_reset"))
            return
        if self.poller is not None and self.recorder is not None:
            self.poller.stop()
            self.recorder.stop_session()
        self.session = None
        self.runner.reset()
        self.completed.clear()
        self.issues.clear()
        for app in self.manifest.catalog:
            self.app_checks[app.name].set(app.selected)
        self.status_var.set(t("status.no_session"))
        self.cards.reset_progress()
        self.cards.build_app_statuses([])
        self.cards.set_confirm_enabled(False)
        self.cards.set_cancel_enabled(False)
        self.cards.set_applications_running(False)
        self.cards.set_manual_action("")
        self.sidebar.clear_apps()
        self.rail.clear_session()
        self._show(MODULE_NAMES[0])
        self.form.reset()
        self.form.tkraise()
        self.logger.info(t("log.app.session_reset"))

    def _show(self, name: str) -> None:
        self.current = name
        self.cards.show(name)
        self._refresh_access()

    def _refresh_access(self) -> None:
        ready = self.session is not None and not self.runner.busy
        self.cards.set_run_enabled(ready)
        self.rail.set_new_session_enabled(ready)
        self.sidebar.set_states(self.completed, self.current, self.issues)

    # ── Running Modules ──────────────────────────────────────────────────
    def _run_current(self) -> None:
        if self.runner.busy or self.session is None:
            return
        if not self.device.connected:
            self.logger.error(t("log.app.no_device"))
            return
        apps = [app for app in self.manifest.catalog if self.app_checks[app.name].get()]
        if self.current == "applications":
            names = [app.name for app in apps]
            self.cards.build_app_statuses(names)
            self.sidebar.build_apps("applications", names)
        ctx = Context(session=self.session, device=self.device, manifest=self.manifest,
                      apps=apps, adb=self.adb, runner=self.runner, log=self.logger)
        module = MODULES[MODULE_NAMES.index(self.current)]
        if self.runner.run_module(module, ctx):
            self.cards.set_run_enabled(False)

    def _confirm_auth(self) -> None:
        self.runner.confirm_auth()
        self.cards.set_confirm_enabled(False)

    def _cancel_session(self) -> None:
        self.runner.cancel_session()
        self.cards.set_cancel_enabled(False)
        self.logger.warn(t("log.app.cancel_requested"))

    def _finish_module(self, name: str, kinds: list[str]) -> None:
        self.completed.add(name)
        if "ERROR" in kinds or "WARNING" in kinds:
            self.issues.add(name)
        self.cards.set_progress(name, 1.0)
        index = MODULE_NAMES.index(name)
        if index + 1 < len(MODULE_NAMES):
            self._show(MODULE_NAMES[index + 1])
            self.status_var.set(t("status.ready", module=t(f"module.{self.current}.title")))
        else:
            self.current = ""
            self._refresh_access()
            self._show_checklist()

    def _show_checklist(self) -> None:
        results = self.runner.results
        self.cards.set_lock_enabled(self.device.connected)
        self.cards.show_checklist(results)
        lines = [("=" * 60, "system"), (t("checklist.title").upper(), "system"), ("=" * 60, "system")]
        for r in results:
            lines.append((f"  [{r.kind:<7}] {r.name:<28} {r.detail}", _CONSOLE_TAGS[r.kind]))
            if r.remedy:
                lines.append((f"{'':>40}-> {r.remedy}", _CONSOLE_TAGS[r.kind]))
        self.console.append_text(lines)

    # ── Lockdown: explicit, irreversible, never automatic ────────────────
    def _lockdown(self) -> None:
        if self.runner.busy or not self.device.connected:
            self.logger.warn(t("log.app.no_device"))
            return
        if not messagebox.askyesno(theme.APP_NAME, t("lockdown.confirm"), parent=self):
            return
        self.cards.set_lock_enabled(False)
        self.logger.info(t("log.lockdown.start"))
        # The Mirror runs over ADB: stop it BEFORE cutting adb_enabled.
        self.mirror_service.stop()
        self.mirror.set_disconnected()
        threading.Thread(target=self._do_lockdown, args=(self.device.serial,), daemon=True).start()

    def _do_lockdown(self, serial: str) -> None:
        dev_off, adb_sent = self.adb.lockdown(serial)
        (self.logger.ok if dev_off else self.logger.warn)(
            t("log.lockdown.dev_options_off" if dev_off else "log.lockdown.dev_options_unconfirmed"))
        (self.logger.ok if adb_sent else self.logger.warn)(
            t("log.lockdown.adb_off" if adb_sent else "log.lockdown.adb_failed"))
        if dev_off and adb_sent:
            # Worker thread: never touch Tk here, the UI thread drains the queue.
            self.runner.emit({"type": "lockdown_done"})

    def _mark_lockdown_done(self) -> None:
        name = t("result.lockdown.name")
        self.runner.results = [Result(name, "OK", t("result.lockdown.done")) if r.name == name else r
                               for r in self.runner.results]
        self.cards.show_checklist(self.runner.results)

    # ── Queues ───────────────────────────────────────────────────────────
    def _poll_queues(self) -> None:
        self.console.append(self.logger.drain())
        for event in self.runner.drain_events():
            self._on_runner_event(event)
        devices = self.monitor.drain()
        if devices:
            self.device = self._merge_device(devices[-1])
            self.rail.update_device(self.device)
            self._sync_mirror()
        self.after(150, self._poll_queues)

    def _merge_device(self, fresh: DeviceInfo) -> DeviceInfo:
        # A Module holds a reference to self.device and updates work_user_id on
        # it; keep that object while the same phone stays connected.
        if fresh.connected and self.device.connected and fresh.serial == self.device.serial:
            fresh.work_user_id = fresh.work_user_id or self.device.work_user_id
            for field in ("state", "detail", "model", "battery_level", "work_user_id"):
                setattr(self.device, field, getattr(fresh, field))
            return self.device
        return fresh

    def _on_runner_event(self, event: dict) -> None:
        kind = event["type"]
        if kind == "started":
            self.status_var.set(t("status.running", module=t(f"module.{event['module']}.title")))
            self.cards.set_progress(str(event["module"]), 0.0)
            self.sidebar.set_running(True)
            self.rail.set_new_session_enabled(False)
            if event["module"] == "applications":
                self.cards.set_applications_running(True)
        elif kind == "progress":
            self.cards.set_progress(self.current, float(event["value"]))
            self.status_var.set(str(event["message"]))
        elif kind == "finished":
            self.sidebar.set_running(False)
            if event["module"] == "applications":
                self.cards.set_confirm_enabled(False)
                self.cards.set_cancel_enabled(False)
                self.cards.set_manual_action("")
                self.cards.set_applications_running(False)
            self._finish_module(str(event["module"]), list(event["kinds"]))
        elif kind == "auth_required":
            self.cards.set_confirm_enabled(True)
            self.status_var.set(t("status.sign_in", app=event["app"]))
        elif kind == "auth_done":
            self.cards.set_confirm_enabled(False)
        elif kind == "enrollment":
            self.cards.set_cancel_enabled(bool(event["active"]))
            if event["active"]:
                self.status_var.set(t("status.enrollment"))
        elif kind == "app_status":
            self.cards.set_app_status(str(event["app"]), str(event["status"]))
            self.sidebar.set_app_status(str(event["app"]), str(event["status"]))
        elif kind == "manual_action":
            self.cards.set_manual_action(str(event["message"]))
        elif kind == "lockdown_done":
            self._mark_lockdown_done()

    # ── Mirror ───────────────────────────────────────────────────────────
    def _resize_mirror(self, state: str) -> None:
        self.grid_columnconfigure(2, weight=0, minsize=MirrorPanel.SIZES[state])

    def _sync_mirror(self) -> None:
        if not self.device.connected:
            if self.mirror_service.state != "idle":
                self.mirror_service.stop()
            self._mirror_failed_shown = False
            self.mirror.set_disconnected()
        elif not self.mirror_service.available:
            self.mirror.set_unavailable(t("mirror.missing_dependency"))
        elif self.mirror_service.state == "idle" and self.mirror_service.start(self.device.serial):
            self._mirror_failed_shown = False
            self.mirror.set_connecting()

    def _render_mirror(self) -> None:
        if self.mirror_service.state == "running":
            seq, frame = self.mirror_service.get_frame()
            if frame is not None and seq != self._mirror_seq:
                self._mirror_seq = seq
                self.mirror.show_frame(frame)
        elif self.mirror_service.state == "failed" and not self._mirror_failed_shown:
            self._mirror_failed_shown = True
            self.mirror.set_unavailable(t("mirror.see_console"))
        self.after(40, self._render_mirror)       # ~25 fps, enough for a workbench

    def _on_close(self) -> None:
        self.session = None
        if self.poller is not None:
            self.poller.stop()
        self.mirror_service.stop()
        self.monitor.stop()
        self.destroy()


def load_banner() -> str:
    """banner.txt next to the tool; "" when absent (the plain name is shown)."""
    try:
        return (app_root() / "banner.txt").read_text(encoding="utf-8").rstrip("\n")
    except OSError:
        return ""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="AndroidContextDeploy")
    parser.add_argument("--diag", action="store_true",
                        help="capture every screen and adb command to diag/ (masked)")
    parser.add_argument("--lang", help="UI Language, e.g. en or fr (default: deploy.json)")
    args = parser.parse_args(argv)

    root = app_root()
    try:
        manifest = load_manifest(root / MANIFEST_NAME)
    except ManifestError as exc:
        # Nothing else can run without a valid Manifest; say exactly what to fix.
        hidden = tk.Tk()
        hidden.withdraw()
        messagebox.showerror("AndroidContextDeploy", f"{MANIFEST_NAME}\n\n{exc}")
        hidden.destroy()
        print(f"{MANIFEST_NAME}: {exc}", file=sys.stderr)
        return 1

    i18n.load(root, args.lang or manifest.language)
    app = DeploymentApp(manifest, diag=args.diag)
    try:
        app.mainloop()
    except KeyboardInterrupt:
        app._on_close()
    return 0
