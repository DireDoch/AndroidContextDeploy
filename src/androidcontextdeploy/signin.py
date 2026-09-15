"""The Detection Loop (ADR-0002) and the Enrollment controller (ADR-0004).

Both loops read the screen, let ScreenDetector say what is on it, and act:
inject the email or password, tap the button that leads to sign-in, or wait
for the employee (MFA approval, SMS code). Neither password nor phone number is
ever logged.

Cadence: `dumpsys window` (~100 ms) tells when the screen changed; the costly
`uiautomator dump` only runs then, or every poll_interval as a safety net for
WebView transitions inside one activity.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

from androidcontextdeploy.adb import KEY_ENTER
from androidcontextdeploy.detection import ScreenDetector, screen_signature
from androidcontextdeploy.i18n import t
from androidcontextdeploy.models import DeviceInfo, ScreenAnalysis, SessionConfig, UiField

# Let a freshly tapped field take focus before typing into it.
_FOCUS_DELAY = 0.6
_TYPE_DELAY = 0.4


@dataclass
class _State:
    """Attempt counters and log-once flags for one loop run."""
    email_attempts: int = 0
    password_attempts: int = 0
    mfa_logged: bool = False
    code_logged: bool = False
    manual_logged: bool = False
    button_clicks: dict[str, int] = field(default_factory=dict)
    button_blocked_logged: bool = False
    ownership_tapped: bool = False
    phone_injected: bool = False
    sms_checked: bool = False
    phone_manual_logged: bool = False


class SignInDriver:
    def __init__(self, runner, organization: str = "") -> None:
        self.runner = runner
        self.adb = runner.adb
        self.log = runner.logger
        self.organization = organization

    # ── Helpers ──────────────────────────────────────────────────────────
    def _capture(self, serial: str, xml_text: str, screen: ScreenAnalysis) -> None:
        recorder = getattr(self.adb, "recorder", None)
        if recorder is not None:
            recorder.capture_screen(serial, screen_signature(screen), xml_text, screen)

    def _wait_for_change(self, serial: str, max_wait: float, gate: threading.Event) -> None:
        """Sleep up to max_wait, but return as soon as the focused window changes
        or the gate is set."""
        baseline = self.adb.get_focused_activity(serial)
        deadline = time.time() + max_wait
        while time.time() < deadline and not gate.is_set():
            time.sleep(min(0.2, max_wait))
            if self.adb.get_focused_activity(serial) != baseline:
                return

    def _type_into(self, serial: str, target: UiField, text: str) -> tuple[bool, str]:
        self.adb.tap(serial, target.center_x, target.center_y)
        time.sleep(_FOCUS_DELAY)
        ok, err = self.adb.inject_text(serial, text)
        if ok:
            time.sleep(_TYPE_DELAY)
        return ok, err

    # ── Generic sign-in loop ─────────────────────────────────────────────
    def run_sign_in(self, session: SessionConfig, device: DeviceInfo, app_name: str,
                    timeout: float = 600, poll_interval: float = 1.5) -> str:
        """Returns "auto" (sign-in screen gone), "manual" (technician pressed
        Confirm) or "timeout"."""
        runner = self.runner
        runner.auth_gate.clear()
        runner.emit({"type": "auth_required", "app": app_name})
        runner.pause_poller()
        try:
            return self._sign_in_loop(session, device, app_name, time.time() + timeout, poll_interval)
        finally:
            runner.resume_poller()
            runner.emit({"type": "auth_done", "app": app_name})

    def _sign_in_loop(self, session, device, app_name, deadline, poll_interval) -> str:
        detector = ScreenDetector(self.organization)
        state = _State()
        gate = self.runner.auth_gate
        seen_login, dump_failures, clean_polls = False, 0, 0
        while time.time() < deadline:
            if gate.is_set():
                return "manual"
            xml_text = self.adb.dump_ui_xml(device.serial)
            screen = detector.analyze(xml_text) if xml_text else None
            if screen is None:
                dump_failures += 1
                if dump_failures == 3:
                    self.log.warn(t("log.signin.dump_failed", app=app_name))
                self._wait_for_change(device.serial, poll_interval, gate)
                continue
            dump_failures = 0
            self._capture(device.serial, xml_text, screen)

            if (self._handle_mfa(screen, app_name, state)
                    or self._handle_code_entry(screen, app_name, state)
                    or self._handle_email(screen, session, device, app_name, state)
                    or self._handle_password(screen, session, device, app_name, state)
                    or self._handle_button(screen, device, app_name, state)
                    or screen.login_markers):
                seen_login, clean_polls = True, 0
                self._wait_for_change(device.serial, poll_interval, gate)
                continue

            # Several clean reads in a row, so a page transition is not taken for
            # "done"; more cautious when no sign-in screen was ever seen.
            clean_polls += 1
            if clean_polls >= (3 if seen_login else 5):
                self.log.ok(t("log.signin.done", app=app_name))
                return "auto"
            self._wait_for_change(device.serial, poll_interval, gate)
        return "timeout"

    # ── Screen handlers, shared by both loops. True = this screen was handled.
    def _handle_mfa(self, screen: ScreenAnalysis, app_name: str, state: _State) -> bool:
        if not screen.mfa_detected:
            state.mfa_logged = False
            return False
        if not state.mfa_logged:
            self.log.info(t("log.signin.mfa", app=app_name, hint=screen.mfa_hint))
            state.mfa_logged = True
        return True

    def _handle_code_entry(self, screen: ScreenAnalysis, app_name: str, state: _State) -> bool:
        if not screen.otc_field:
            state.code_logged = False
            return False
        if not state.code_logged:
            self.log.info(t("log.signin.sms_code", app=app_name))
            self.runner.emit_manual_action(app_name, t("manual.sms_code"))
            state.code_logged = True
        return True

    def _handle_email(self, screen, session, device, app_name, state: _State) -> bool:
        fld = screen.email_field
        if not (fld and fld.is_empty):
            return False
        if state.email_attempts < 2:
            state.email_attempts += 1
            self.log.info(t("log.signin.email_field", app=app_name, email=session.email))
            ok, err = self._type_into(device.serial, fld, session.email)
            if ok:
                self.adb.press_key(device.serial, KEY_ENTER)
                self.log.ok(t("log.signin.email_injected", app=app_name))
            else:
                self.log.warn(t("log.signin.email_failed", error=err or "?"))
        return True

    def _handle_password(self, screen, session, device, app_name, state: _State) -> bool:
        fld = screen.password_field
        if not (fld and fld.is_empty):
            return False
        if session.user_password and state.password_attempts < 2:
            state.password_attempts += 1
            self.log.info(t("log.signin.password_field", app=app_name))
            ok, err = self._type_into(device.serial, fld, session.user_password)
            if ok:
                self.adb.press_key(device.serial, KEY_ENTER)
                self.log.ok(t("log.signin.password_injected"))
            else:
                self.log.warn(t("log.signin.password_failed", error=err or "?"))
        elif not session.user_password and not state.manual_logged:
            self.log.info(t("log.signin.password_manual", app=app_name))
            state.manual_logged = True
        return True

    def _handle_button(self, screen, device, app_name, state: _State) -> bool:
        # At most two taps per label: if the screen does not move, stop tapping
        # and leave it to the technician (Confirm button).
        button = screen.action_button
        if not button:
            return False
        label = (button.text or button.content_desc).strip()
        key = label.lower()
        if state.button_clicks.get(key, 0) < 2:
            state.button_clicks[key] = state.button_clicks.get(key, 0) + 1
            self.log.info(t("log.signin.button", app=app_name, label=label))
            self.adb.tap(device.serial, button.center_x, button.center_y)
        elif not state.button_blocked_logged:
            self.log.warn(t("log.signin.button_stuck", app=app_name, label=label))
            state.button_blocked_logged = True
        return True

    # ── Enrollment controller ────────────────────────────────────────────
    def run_enrollment(self, session: SessionConfig, device: DeviceInfo, app_name: str,
                       poll_interval: float = 1.5) -> str:
        """Returns "play_store" or "cancelled". There is deliberately NO timeout
        (ADR-0004): the only exit short of the managed Play Store is Cancel."""
        runner = self.runner
        runner.cancel_gate.clear()
        runner.auth_gate.clear()
        runner.emit({"type": "enrollment", "app": app_name, "active": True})
        runner.pause_poller()
        try:
            return self._enrollment_loop(session, device, app_name, poll_interval)
        finally:
            runner.resume_poller()
            runner.emit({"type": "enrollment", "app": app_name, "active": False})

    def _enrollment_loop(self, session, device, app_name, poll_interval) -> str:
        detector = ScreenDetector(self.organization)
        state = _State()
        serial = device.serial
        gate = self.runner.cancel_gate   # Confirm must never skip the gate
        last_logged = ""
        while not gate.is_set():
            # The gate, robust signal first: the Play Store is the focused window.
            if self.adb.is_play_store_focused(serial):
                self.log.ok(t("log.enroll.gate_reached", app=app_name))
                return "play_store"
            xml_text = self.adb.dump_ui_xml(serial)
            screen = detector.analyze(xml_text) if xml_text else None
            if screen is None:
                self._wait_for_change(serial, poll_interval, gate)
                continue
            if screen.managed_play_store:          # the gate, text fallback
                self.log.ok(t("log.enroll.gate_reached", app=app_name))
                return "play_store"

            self._capture(serial, xml_text, screen)
            signature = screen_signature(screen)
            if signature != last_logged:
                last_logged = signature
                self.log.info(t("log.enroll.screen", app=app_name, screen=describe_screen(screen)))

            # Named screens win over everything, then waiting for the employee,
            # then the generic mechanics. An unrecognised screen never advances.
            if not (self._handle_named_screen(screen, session, device, app_name, state)
                    or self._handle_mfa(screen, app_name, state)
                    or self._handle_code_entry(screen, app_name, state)
                    or self._handle_email(screen, session, device, app_name, state)
                    or self._handle_password(screen, session, device, app_name, state)):
                self._handle_button(screen, device, app_name, state)
            self._wait_for_change(serial, poll_interval, gate)

        self.log.warn(t("log.enroll.cancelled", app=app_name))
        return "cancelled"

    def _tap_named(self, device: DeviceInfo, app_name: str, label_key: str,
                   target: UiField | None) -> None:
        # No target: wait for the next screen change, never guess.
        if target is not None:
            self.log.info(t("log.enroll.tap", app=app_name, label=t(label_key)))
            self.adb.tap(device.serial, target.center_x, target.center_y)

    def _handle_named_screen(self, screen, session, device, app_name, state: _State) -> bool:
        """True as soon as a named screen is recognised, even with no target, so
        the generic mechanics cannot tap the wrong button (e.g. Next instead of
        the "different method" link)."""
        name, targets = screen.named_screen, screen.named_targets
        if not name:
            return False
        if name == "phone_entry":
            return self._handle_phone_entry(screen, session, device, app_name, state)
        if name == "method_dialog":
            if targets.get("phone_option"):
                self._tap_named(device, app_name, "enroll.target.phone_option", targets["phone_option"])
            else:
                self._tap_named(device, app_name, "enroll.target.confirm", targets.get("confirm"))
        elif name == "ownership":
            if targets.get("device_org") and not state.ownership_tapped:
                self._tap_named(device, app_name, "enroll.target.device_org", targets["device_org"])
                state.ownership_tapped = True
            else:
                self._tap_named(device, app_name, "enroll.target.finish", targets.get("finish"))
        else:
            role = {"skip_setup": "skip", "authenticator_other_method": "link",
                    "terms": "accept", "access_setup": "continue"}[name]
            self._tap_named(device, app_name, f"enroll.target.{role}", targets.get(role))
        return True

    def _handle_phone_entry(self, screen, session, device, app_name, state: _State) -> bool:
        targets = screen.named_targets
        if not session.employee_phone:
            if not state.phone_manual_logged:
                self.log.warn(t("log.enroll.no_phone", app=app_name))
                self.runner.emit_manual_action(app_name, t("manual.phone_entry"))
                state.phone_manual_logged = True
            return True
        if targets.get("phone") and not state.phone_injected:
            ok, err = self._type_into(device.serial, targets["phone"], session.employee_phone)
            if ok:
                self.log.ok(t("log.enroll.phone_injected", app=app_name))
            else:
                self.log.warn(t("log.enroll.phone_failed", app=app_name, error=err or "?"))
            state.phone_injected = True
        elif targets.get("sms_checkbox") and not state.sms_checked:
            self._tap_named(device, app_name, "enroll.target.sms_checkbox", targets["sms_checkbox"])
            state.sms_checked = True
        elif targets.get("next"):
            self._tap_named(device, app_name, "enroll.target.next", targets["next"])
        return True


def describe_screen(screen: ScreenAnalysis) -> str:
    """A readable label for the log. On an unrecognised screen it lists the
    visible buttons -- exactly what you need to add the missing keyword."""
    if screen.named_screen:
        return t("screen.named", name=screen.named_screen)
    if screen.otc_field:
        return t("screen.sms_code")
    if screen.mfa_detected:
        return t("screen.mfa")
    if screen.email_field and screen.email_field.is_empty:
        return t("screen.email")
    if screen.password_field and screen.password_field.is_empty:
        return t("screen.password")
    if screen.action_button:
        return t("screen.button", label=(screen.action_button.text or screen.action_button.content_desc).strip())
    if screen.login_markers:
        return t("screen.login")
    return t("screen.unknown", buttons=", ".join(screen.clickable_labels[:8]) or "-")
