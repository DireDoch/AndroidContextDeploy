"""Left rail: Banner, device card, session summary, progress sidebar."""
from __future__ import annotations

from collections.abc import Callable

import customtkinter as ctk

from androidcontextdeploy.i18n import t
from androidcontextdeploy.models import DeviceInfo
from androidcontextdeploy.ui import theme
from androidcontextdeploy.ui.step_sidebar import StepSidebar


class RailPanel(ctk.CTkFrame):
    def __init__(self, master, steps: list[tuple[str, str]],
                 on_new_session: Callable[[], None]) -> None:
        super().__init__(master, corner_radius=16, fg_color=theme.CARD, width=290)
        self.grid_propagate(False)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)

        # The banner is too wide for the rail at a readable size: it opens the
        # console instead, and the rail shows the plain name.
        ctk.CTkLabel(
            self, text=theme.APP_NAME, font=theme.mono(16, "bold"),
            text_color=theme.ACCENT_LIGHT, anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(20, 4))

        card = ctk.CTkFrame(self, corner_radius=12, fg_color=theme.CARD_ALT)
        card.grid(row=1, column=0, sticky="ew", padx=12, pady=(14, 8))
        card.grid_columnconfigure(1, weight=1)
        self._dot = ctk.CTkFrame(card, width=12, height=12, corner_radius=6,
                                 fg_color=theme.OFFLINE)
        self._dot.grid(row=0, column=0, sticky="w", padx=(14, 8), pady=(12, 6))
        self._status = ctk.CTkLabel(card, text=t("device.state.none"), anchor="w",
                                    wraplength=210, justify="left",
                                    font=ctk.CTkFont(size=13, weight="bold"),
                                    text_color=theme.TEXT)
        self._status.grid(row=0, column=1, sticky="ew", padx=(0, 14), pady=(12, 6))
        self._model = self._info_row(card, 1, t("device.model"))
        self._serial = self._info_row(card, 2, t("device.serial"))
        self._battery = self._info_row(card, 3, t("device.battery"))
        self._profile = self._info_row(card, 4, t("device.work_profile"))
        card.grid_rowconfigure(5, minsize=8)

        self._session_card = ctk.CTkFrame(self, corner_radius=12, fg_color=theme.CARD_ALT)
        self._session_card.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 8))
        self._session_card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self._session_card, text=t("rail.session"), font=theme.mono(11, "bold"),
                     text_color=theme.MUTED, anchor="w").grid(
            row=0, column=0, sticky="ew", padx=14, pady=(10, 0))
        self._session_email = ctk.CTkLabel(self._session_card, text="", anchor="w",
                                           font=theme.mono(12), wraplength=230,
                                           text_color=theme.ACCENT_LIGHT, justify="left")
        self._session_email.grid(row=1, column=0, sticky="ew", padx=14, pady=(2, 6))
        self._new_session_btn = ctk.CTkButton(
            self._session_card, text=t("rail.new_session"), height=30, corner_radius=8,
            fg_color="transparent", border_width=1, border_color=theme.MUTED,
            text_color=theme.TEXT, hover_color=theme.CARD, font=ctk.CTkFont(size=12),
            command=on_new_session)
        self._new_session_btn.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 12))
        self._session_card.grid_remove()

        self.steps = StepSidebar(self, steps)
        self.steps.grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 8))

    @staticmethod
    def _info_row(parent: ctk.CTkFrame, row: int, label: str) -> ctk.CTkLabel:
        ctk.CTkLabel(parent, text=label, text_color=theme.MUTED,
                     font=ctk.CTkFont(size=12)).grid(row=row, column=0, sticky="w",
                                                     padx=(14, 6), pady=3)
        value = ctk.CTkLabel(parent, text="N/A", anchor="e", text_color=theme.TEXT,
                             font=theme.mono(12))
        value.grid(row=row, column=1, sticky="ew", padx=(0, 14), pady=3)
        return value

    def update_device(self, info: DeviceInfo) -> None:
        self._dot.configure(fg_color=theme.LIVE if info.connected else theme.OFFLINE)
        self._status.configure(text=t(f"device.state.{info.state}", detail=info.detail))
        self._model.configure(text=info.model)
        self._serial.configure(text=info.serial)
        self._battery.configure(text=info.battery_level)
        self._profile.configure(
            text=f"user {info.work_user_id}" if info.work_user_id else ("-" if info.connected else "N/A"))

    def show_session(self, email: str) -> None:
        self._session_email.configure(text=f"✓ {email}")
        self._session_card.grid()

    def clear_session(self) -> None:
        self._session_email.configure(text="")
        self._session_card.grid_remove()

    def set_new_session_enabled(self, enabled: bool) -> None:
        self._new_session_btn.configure(state="normal" if enabled else "disabled")
