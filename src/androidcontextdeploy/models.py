"""Plain data passed between the ADB layer, the Modules and the UI."""
from __future__ import annotations

import queue
from dataclasses import dataclass, field
from datetime import datetime


@dataclass(slots=True)
class SessionConfig:
    email: str
    user_password: str = ""
    # The employee's personal number, used once for SMS MFA during Enrollment.
    # Memory only, like the password. Empty -> the technician types it by hand.
    employee_phone: str = ""


@dataclass(slots=True)
class DeviceInfo:
    connected: bool = False
    # "none" | "not_ready" | "connected" | "adb_missing" -> device.state.* strings
    state: str = "none"
    detail: str = ""
    model: str = "N/A"
    serial: str = "N/A"
    battery_level: str = "N/A"
    # Work Profile user id (Android Enterprise). 0 = primary user, when no
    # managed profile exists yet. Every app operation targets this id.
    work_user_id: int = 0


@dataclass(slots=True)
class LogEvent:
    level: str
    message: str
    timestamp: str = field(default_factory=lambda: datetime.now().strftime("%H:%M:%S"))


class AppLogger:
    """Thread-safe log: workers put, the UI thread drains."""

    def __init__(self) -> None:
        self._events: queue.Queue[LogEvent] = queue.Queue()

    def info(self, message: str) -> None:
        self._events.put(LogEvent("INFO", message))

    def ok(self, message: str) -> None:
        self._events.put(LogEvent("OK", message))

    def warn(self, message: str) -> None:
        self._events.put(LogEvent("WARN", message))

    def error(self, message: str) -> None:
        self._events.put(LogEvent("ERROR", message))

    def drain(self) -> list[LogEvent]:
        items: list[LogEvent] = []
        while True:
            try:
                items.append(self._events.get_nowait())
            except queue.Empty:
                return items


KINDS = ("OK", "WARNING", "ERROR", "MANUAL", "N/A")


@dataclass(slots=True)
class Result:
    """What one piece of work inside a Module produced. See CONTEXT.md."""
    name: str
    kind: str                 # one of KINDS
    detail: str = ""
    remedy: str = ""          # names the fix, ideally the deploy.json key


@dataclass(slots=True)
class UiField:
    """A field or button found in the phone's UI tree."""
    center_x: int
    center_y: int
    text: str = ""
    resource_id: str = ""
    content_desc: str = ""
    hint: str = ""
    is_password: bool = False
    focused: bool = False
    is_empty: bool = True


@dataclass(slots=True)
class ScreenAnalysis:
    """What one `uiautomator dump` of the current screen contains."""
    email_field: UiField | None = None
    password_field: UiField | None = None
    action_button: UiField | None = None
    # One-time code field (SMS/OTP). The employee types it; the tool never
    # injects anything here, least of all the email.
    otc_field: UiField | None = None
    mfa_detected: bool = False
    mfa_hint: str = ""
    login_markers: bool = False
    # Enrollment screens the controller handles before the generic mechanics.
    # "" outside Enrollment; see detection.ScreenDetector._detect_named_screen.
    named_screen: str = ""
    named_targets: dict[str, UiField] = field(default_factory=dict)
    # Text fallback for "the managed Play Store is showing" (the Enrollment gate).
    managed_play_store: bool = False
    # Visible clickable labels, logged on unrecognised screens so a
    # contributor knows which keyword is missing.
    clickable_labels: list[str] = field(default_factory=list)
