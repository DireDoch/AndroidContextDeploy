"""Runs one Module at a time off the UI thread and keeps every Result of the
Session until the Checklist. The UI never calls adb: it drains `events`."""
from __future__ import annotations

import queue
import threading
from typing import TYPE_CHECKING

from androidcontextdeploy.i18n import t
from androidcontextdeploy.models import AppLogger, Result

if TYPE_CHECKING:
    from androidcontextdeploy.diagnostics import DiagnosticPoller


class WorkflowRunner:
    def __init__(self, adb, logger: AppLogger) -> None:
        self.adb = adb
        self.logger = logger
        self.events: queue.Queue[dict[str, object]] = queue.Queue()
        self.results: list[Result] = []
        # "Confirm": ends a stuck sign-in loop. Never ends Enrollment.
        self.auth_gate = threading.Event()
        # "Cancel session": the only way out of Enrollment short of the gate.
        self.cancel_gate = threading.Event()
        self.poller: DiagnosticPoller | None = None     # only with --diag
        self._busy = False
        self._busy_lock = threading.Lock()

    @property
    def busy(self) -> bool:
        return self._busy

    def reset(self) -> None:
        self.results.clear()
        self.cancel_gate.clear()
        self.auth_gate.clear()

    def confirm_auth(self) -> None:
        self.auth_gate.set()

    def cancel_session(self) -> None:
        self.cancel_gate.set()
        self.auth_gate.set()

    def pause_poller(self) -> None:
        if self.poller is not None:
            self.poller.pause()

    def resume_poller(self) -> None:
        if self.poller is not None:
            self.poller.resume()

    # ── Running a Module ─────────────────────────────────────────────────
    def run_module(self, module, ctx) -> bool:
        with self._busy_lock:
            if self._busy:
                self.logger.warn(t("log.runner.busy"))
                return False
            self._busy = True
        self.emit({"type": "started", "module": module.NAME})
        threading.Thread(target=self._execute, args=(module, ctx), daemon=True,
                         name=f"module-{module.NAME}").start()
        return True

    def _execute(self, module, ctx) -> None:
        try:
            results = module.run(ctx)
        except Exception as exc:
            # A crash is recorded as a Result; the Session and the Checklist go on.
            self.logger.error(t("log.runner.crash", module=module.NAME, error=exc))
            results = [Result(t(f"module.{module.NAME}.title"), "ERROR", str(exc),
                              t("remedy.crash"))]
        self.results.extend(results)
        with self._busy_lock:
            self._busy = False
        self.emit({"type": "finished", "module": module.NAME,
                   "kinds": sorted({r.kind for r in results})})

    # ── Events for the UI ────────────────────────────────────────────────
    def emit(self, event: dict[str, object]) -> None:
        self.events.put(event)

    def emit_progress(self, value: float, message: str) -> None:
        self.emit({"type": "progress", "value": value, "message": message})

    def emit_app_status(self, app_name: str, status: str) -> None:
        self.emit({"type": "app_status", "app": app_name, "status": status})

    def emit_manual_action(self, app_name: str, message: str) -> None:
        """Ask the technician to do something now; an empty message clears it."""
        self.emit({"type": "manual_action", "app": app_name, "message": message})

    def drain_events(self) -> list[dict[str, object]]:
        items: list[dict[str, object]] = []
        while True:
            try:
                items.append(self.events.get_nowait())
            except queue.Empty:
                return items
