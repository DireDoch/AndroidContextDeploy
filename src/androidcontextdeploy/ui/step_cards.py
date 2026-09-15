"""Module cards: only the current Module's card is visible, then the Checklist.

Every Module gets a generic card (title, description, progress, run button)
from its locale strings. The Applications card adds the app checkboxes, the
Manual Action banner, Confirm and Cancel. The last card is the Checklist.
"""
from __future__ import annotations

import tkinter as tk
from collections.abc import Callable

import customtkinter as ctk

from androidcontextdeploy.i18n import t
from androidcontextdeploy.models import Result
from androidcontextdeploy.ui import theme

_STATUS_COLORS = {
    "waiting": theme.MUTED, "opening_store": theme.INFO, "installing": theme.WARN,
    "installed": theme.ACCENT_LIGHT, "manual": theme.ACTION, "auth_pending": theme.ACTION,
    "auth_confirmed": theme.ACCENT_LIGHT, "pinning": theme.INFO, "pinned": theme.ACCENT_LIGHT,
    "pin_manual": theme.WARN, "failed": theme.ERROR,
}
_KIND_MARKS = {"OK": "✓", "WARNING": "!", "ERROR": "✗", "MANUAL": "✋", "N/A": "–"}


class StepCardsPanel(ctk.CTkFrame):
    def __init__(self, master, module_names: list[str], status_var: tk.StringVar,
                 on_run: Callable[[], None], on_confirm_auth: Callable[[], None],
                 on_cancel_session: Callable[[], None], on_lockdown: Callable[[], None],
                 on_new_device: Callable[[], None]) -> None:
        super().__init__(master, corner_radius=14, fg_color=theme.CARD_ALT)
        self._status_var = status_var
        self._on_run = on_run
        self._bars: dict[str, ctk.CTkProgressBar] = {}
        self._run_buttons: dict[str, ctk.CTkButton] = {}
        self._app_labels: dict[str, ctk.CTkLabel] = {}
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._cards: dict[str, ctk.CTkFrame] = {}
        for name in module_names:
            card = self._card()
            self._run_button(card, name)
            if name == "applications":
                self._build_applications(card, on_confirm_auth, on_cancel_session)
            else:
                self._header(card, name)
                self._progress(card, name)
            self._cards[name] = card
        self._cards["checklist"] = self._build_checklist(on_lockdown, on_new_device)

    # ── Building blocks ──────────────────────────────────────────────────
    def _card(self) -> ctk.CTkFrame:
        card = ctk.CTkFrame(self, corner_radius=14, fg_color=theme.CARD_ALT)
        card.grid(row=0, column=0, sticky="nsew")
        return card

    @staticmethod
    def _header(parent, name: str) -> None:
        ctk.CTkLabel(parent, text=t(f"module.{name}.title"), font=ctk.CTkFont(size=18, weight="bold"),
                     text_color=theme.ACCENT_LIGHT).pack(anchor="w", padx=22, pady=(18, 4))
        ctk.CTkLabel(parent, text=t(f"module.{name}.description"), text_color=theme.MUTED,
                     justify="left", wraplength=640, font=ctk.CTkFont(size=13)).pack(
            anchor="w", padx=22, pady=(0, 8))

    def _progress(self, parent, name: str) -> None:
        ctk.CTkLabel(parent, textvariable=self._status_var, text_color=theme.MUTED,
                     font=theme.mono(11), wraplength=680, anchor="w", justify="left").pack(
            anchor="w", fill="x", padx=22, pady=(2, 1))
        bar = ctk.CTkProgressBar(parent, height=10, corner_radius=5, fg_color=theme.CARD,
                                 progress_color=theme.ACCENT)
        bar.pack(fill="x", padx=22, pady=(0, 10))
        bar.set(0)
        self._bars[name] = bar

    def _run_button(self, card, name: str) -> None:
        button = ctk.CTkButton(card, text=t(f"module.{name}.run"), command=self._on_run,
                               corner_radius=14, height=56, fg_color=theme.ACCENT,
                               hover_color=theme.ACCENT_HOVER, text_color=theme.TEXT,
                               font=ctk.CTkFont(size=17, weight="bold"), state="disabled")
        button.pack(fill="x", side="bottom", padx=18, pady=(6, 16))
        self._run_buttons[name] = button

    def _build_applications(self, card, on_confirm_auth, on_cancel_session) -> None:
        self._manual_banner = ctk.CTkLabel(card, text="", font=ctk.CTkFont(size=15, weight="bold"),
                                           text_color=theme.TEXT, fg_color=theme.ACTION,
                                           corner_radius=10, justify="left", wraplength=620,
                                           anchor="w")
        self._apps_scroll = ctk.CTkScrollableFrame(card, fg_color="transparent", corner_radius=0)
        self._apps_scroll.pack(fill="both", expand=True)
        scroll = self._apps_scroll

        self._header(scroll, "applications")
        header_widgets = scroll.winfo_children()
        self._progress(scroll, "applications")
        progress_widgets = scroll.winfo_children()[len(header_widgets):]
        self._checks_frame = ctk.CTkFrame(scroll, corner_radius=12, fg_color=theme.CARD)
        self._confirm_btn = ctk.CTkButton(scroll, text=t("apps.confirm"), height=44, corner_radius=12,
                                          fg_color=theme.CONFIRM, hover_color=theme.CONFIRM_HOVER,
                                          text_color=theme.TEXT, command=on_confirm_auth,
                                          state="disabled")
        self._cancel_btn = ctk.CTkButton(scroll, text=t("apps.cancel"), height=40, corner_radius=12,
                                         fg_color=theme.CARD, hover_color=theme.ERROR,
                                         text_color=theme.ACTION, command=on_cancel_session,
                                         state="disabled")
        self._status_frame = ctk.CTkFrame(scroll, corner_radius=12, fg_color=theme.CARD)

        # (widget, pack options, hidden while running). While the Module runs only
        # the status, the bar, Confirm and Cancel stay; the detail is in the sidebar.
        self._apps_layout = (
            [(w, dict(anchor="w", padx=22, pady=(18, 4) if i == 0 else (0, 8)), True)
             for i, w in enumerate(header_widgets)]
            + [(w, w.pack_info(), False) for w in progress_widgets]
            + [(self._checks_frame, dict(fill="x", padx=18, pady=(0, 8)), True),
               (self._confirm_btn, dict(anchor="w", padx=18, pady=(0, 8)), False),
               (self._cancel_btn, dict(anchor="w", padx=18, pady=(0, 8)), False),
               (self._status_frame, dict(fill="x", padx=18, pady=(0, 14)), True)])
        self.set_applications_running(False)

    def _build_checklist(self, on_lockdown, on_new_device) -> ctk.CTkFrame:
        card = self._card()
        ctk.CTkLabel(card, text=t("checklist.title"), font=ctk.CTkFont(size=20, weight="bold"),
                     text_color=theme.TEXT).pack(anchor="w", padx=22, pady=(18, 0))
        self._summary = ctk.CTkLabel(card, text="", text_color=theme.MUTED, font=ctk.CTkFont(size=13))
        self._summary.pack(anchor="w", padx=22, pady=(0, 8))

        buttons = ctk.CTkFrame(card, fg_color="transparent")
        buttons.pack(side="bottom", fill="x", padx=18, pady=(6, 16))
        buttons.grid_columnconfigure((0, 1), weight=1)
        self._lock_btn = ctk.CTkButton(buttons, text=t("checklist.lockdown"), command=on_lockdown,
                                       corner_radius=14, height=48, fg_color=theme.WARN,
                                       hover_color=theme.ERROR, text_color=theme.TEXT,
                                       font=ctk.CTkFont(size=15, weight="bold"))
        self._lock_btn.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ctk.CTkButton(buttons, text=t("checklist.new_device"), command=on_new_device,
                      corner_radius=14, height=48, fg_color=theme.ACCENT,
                      hover_color=theme.ACCENT_HOVER, text_color=theme.TEXT,
                      font=ctk.CTkFont(size=15, weight="bold")).grid(row=0, column=1, sticky="ew", padx=(6, 0))
        ctk.CTkLabel(card, text=t("checklist.lockdown_hint"), text_color=theme.MUTED,
                     font=ctk.CTkFont(size=11)).pack(side="bottom", pady=(0, 2))

        self._rows = ctk.CTkScrollableFrame(card, fg_color=theme.CARD, corner_radius=12)
        self._rows.pack(fill="both", expand=True, padx=18, pady=(0, 6))
        self._rows.grid_columnconfigure(2, weight=1)
        return card

    # ── Orchestrator API ─────────────────────────────────────────────────
    def show(self, name: str) -> None:
        if name in self._cards:
            self._cards[name].tkraise()

    def show_checklist(self, results: list[Result]) -> None:
        for widget in self._rows.winfo_children():
            widget.destroy()
        for row, result in enumerate(results):
            color = theme.KIND_COLORS.get(result.kind, theme.TEXT)
            ctk.CTkLabel(self._rows, text=_KIND_MARKS.get(result.kind, "?"), width=22,
                         text_color=color, font=theme.mono(14, "bold")).grid(
                row=row, column=0, sticky="nw", padx=(10, 4), pady=4)
            ctk.CTkLabel(self._rows, text=result.name, anchor="w", text_color=theme.TEXT,
                         font=ctk.CTkFont(size=13, weight="bold")).grid(
                row=row, column=1, sticky="nw", padx=4, pady=4)
            detail = result.detail + (f"\n→ {result.remedy}" if result.remedy else "")
            ctk.CTkLabel(self._rows, text=f"{result.kind}   {detail}", anchor="w", justify="left",
                         wraplength=430, text_color=color, font=ctk.CTkFont(size=12)).grid(
                row=row, column=2, sticky="nw", padx=(8, 10), pady=4)
        counts = {kind: sum(r.kind == kind for r in results) for kind in theme.KIND_COLORS}
        self._summary.configure(text=t("checklist.summary", ok=counts["OK"], warning=counts["WARNING"],
                                       error=counts["ERROR"], manual=counts["MANUAL"], na=counts["N/A"]))
        self.show("checklist")

    def set_lock_enabled(self, enabled: bool) -> None:
        self._lock_btn.configure(state="normal" if enabled else "disabled")

    def set_progress(self, name: str, value: float) -> None:
        if name in self._bars:
            self._bars[name].set(max(0.0, min(1.0, value)))

    def reset_progress(self) -> None:
        for bar in self._bars.values():
            bar.set(0)

    def set_run_enabled(self, enabled: bool) -> None:
        for button in self._run_buttons.values():
            button.configure(state="normal" if enabled else "disabled")

    def set_confirm_enabled(self, enabled: bool) -> None:
        self._confirm_btn.configure(state="normal" if enabled else "disabled")

    def set_cancel_enabled(self, enabled: bool) -> None:
        self._cancel_btn.configure(state="normal" if enabled else "disabled")

    def set_manual_action(self, text: str) -> None:
        if not text:
            self._manual_banner.pack_forget()
            return
        self._manual_banner.configure(text=f"  ⚠  {t('apps.action_required')}\n  {text}")
        # A CTkScrollableFrame lives on a canvas, so pack(before=...) fails on it:
        # unpack the scroll, pack the banner on top, repack the scroll below.
        self._apps_scroll.pack_forget()
        self._manual_banner.pack(side="top", fill="x", padx=14, pady=(12, 4), ipady=8)
        self._apps_scroll.pack(side="top", fill="both", expand=True)

    def set_applications_running(self, running: bool) -> None:
        for widget, options, hide_on_run in self._apps_layout:
            widget.pack_forget()
            if not (running and hide_on_run):
                widget.pack(**{k: v for k, v in options.items() if k != "in"})

    def build_app_checkboxes(self, entries: list[tuple[str, tk.BooleanVar]]) -> None:
        for widget in self._checks_frame.winfo_children():
            widget.destroy()
        for label, variable in entries:
            ctk.CTkCheckBox(self._checks_frame, text=label, variable=variable,
                            checkmark_color=theme.TEXT, fg_color=theme.ACCENT,
                            hover_color=theme.ACCENT_HOVER, text_color=theme.TEXT).pack(
                anchor="w", padx=16, pady=6)

    def build_app_statuses(self, app_names: list[str]) -> None:
        for widget in self._status_frame.winfo_children():
            widget.destroy()
        self._app_labels.clear()
        if not app_names:
            ctk.CTkLabel(self._status_frame, text=t("apps.statuses_hint"), text_color=theme.MUTED,
                         font=ctk.CTkFont(size=12)).pack(anchor="w", padx=14, pady=8)
        for name in app_names:
            label = ctk.CTkLabel(self._status_frame, text=f"  {name}  — {t('app_status.waiting')}",
                                 anchor="w", text_color=theme.MUTED, font=ctk.CTkFont(size=13))
            label.pack(anchor="w", padx=14, pady=4)
            self._app_labels[name] = label

    def set_app_status(self, app_name: str, status: str) -> None:
        if app_name in self._app_labels:
            self._app_labels[app_name].configure(text=f"  {app_name}  — {t(f'app_status.{status}')}",
                                                 text_color=_STATUS_COLORS.get(status, theme.MUTED))
