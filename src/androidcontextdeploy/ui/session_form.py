"""Session form: work email, password (eye toggle), optional personal phone."""
from __future__ import annotations

import tkinter as tk
from collections.abc import Callable

import customtkinter as ctk

from androidcontextdeploy.i18n import t
from androidcontextdeploy.ui import theme


class SessionFormPanel(ctk.CTkFrame):
    def __init__(self, master, organization: str,
                 on_start: Callable[[str, str, str], None]) -> None:
        super().__init__(master, fg_color="transparent")
        self._on_start = on_start
        self._password_visible = False
        self.email_var = tk.StringVar()
        self.password_var = tk.StringVar()
        self.phone_var = tk.StringVar()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        card = ctk.CTkFrame(self, corner_radius=16, fg_color=theme.CARD_ALT, width=520)
        card.grid(row=1, column=0)
        card.grid_columnconfigure(0, weight=1, minsize=480)

        ctk.CTkLabel(card, text=t("form.eyebrow"), font=theme.mono(12, "bold"),
                     text_color=theme.MUTED, anchor="w").grid(
            row=0, column=0, sticky="ew", padx=28, pady=(24, 0))
        ctk.CTkLabel(card, text=t("form.title", organization=organization),
                     font=ctk.CTkFont(size=20, weight="bold"),
                     text_color=theme.ACCENT_LIGHT, anchor="w").grid(
            row=1, column=0, sticky="ew", padx=28, pady=2)
        ctk.CTkLabel(card, text=t("form.subtitle"), text_color=theme.MUTED,
                     font=ctk.CTkFont(size=12), anchor="w").grid(
            row=2, column=0, sticky="ew", padx=28, pady=(0, 14))

        self._build_field(card, 3, t("form.email"), self.email_var, t("form.email_placeholder"))
        self._password_entry = self._build_field(card, 4, t("form.password"),
                                                 self.password_var, "••••••••", password=True)
        phone = self._build_field(card, 5, t("form.phone"), self.phone_var, t("form.phone_placeholder"))
        phone.bind("<Return>", lambda _e: self._submit())

        self._start_btn = ctk.CTkButton(
            card, text=t("form.start"), command=self._submit, corner_radius=12, height=46,
            fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER, text_color=theme.TEXT,
            font=ctk.CTkFont(size=15, weight="bold"), state="disabled")
        self._start_btn.grid(row=6, column=0, sticky="ew", padx=28, pady=(18, 6))

        self._validation = ctk.CTkLabel(card, text=t("form.hint"), text_color=theme.MUTED,
                                        font=ctk.CTkFont(size=12), wraplength=460,
                                        anchor="w", justify="left")
        self._validation.grid(row=7, column=0, sticky="ew", padx=28, pady=(0, 22))

        for var in (self.email_var, self.password_var):
            var.trace_add("write", lambda *_: self._update_start_button())

    def _build_field(self, parent, row: int, label: str, variable: tk.StringVar,
                     placeholder: str, password: bool = False) -> ctk.CTkEntry:
        box = ctk.CTkFrame(parent, corner_radius=10, fg_color=theme.CARD,
                           border_width=1, border_color=theme.MUTED)
        box.grid(row=row, column=0, sticky="ew", padx=28, pady=(0, 10))
        box.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(box, text=label, text_color=theme.MUTED, font=ctk.CTkFont(size=11)).grid(
            row=0, column=0, columnspan=2, sticky="w", padx=14, pady=(8, 0))
        entry = ctk.CTkEntry(box, textvariable=variable, placeholder_text=placeholder,
                             show="•" if password else "", width=10, border_width=0,
                             fg_color="transparent", text_color=theme.TEXT,
                             placeholder_text_color=theme.MUTED, font=theme.mono(13))
        entry.grid(row=1, column=0, sticky="ew", padx=(10, 0), pady=(0, 8))
        if password:
            self._eye_btn = ctk.CTkButton(box, text="👁", width=36, height=28, corner_radius=8,
                                          fg_color="transparent", hover_color=theme.CARD_ALT,
                                          text_color=theme.MUTED, font=ctk.CTkFont(size=15),
                                          command=self._toggle_password)
            self._eye_btn.grid(row=1, column=1, padx=(2, 8), pady=(0, 8))
        else:
            box.grid_columnconfigure(1, minsize=46)
        return entry

    def _toggle_password(self) -> None:
        self._password_visible = not self._password_visible
        self._password_entry.configure(show="" if self._password_visible else "•")
        self._eye_btn.configure(text_color=theme.ACCENT_LIGHT if self._password_visible else theme.MUTED)

    def _update_start_button(self) -> None:
        filled = bool(self.email_var.get().strip()) and bool(self.password_var.get().strip())
        self._start_btn.configure(state="normal" if filled else "disabled")

    def _submit(self) -> None:
        if self._start_btn.cget("state") != "disabled":
            self._on_start(self.email_var.get().strip(), self.password_var.get().strip(),
                           self.phone_var.get().strip())

    def set_validation(self, text: str, is_error: bool = False) -> None:
        self._validation.configure(text=text, text_color=theme.ERROR if is_error else theme.MUTED)

    def reset(self) -> None:
        for var in (self.email_var, self.password_var, self.phone_var):
            var.set("")
        if self._password_visible:
            self._toggle_password()
        self.set_validation(t("form.hint"))
