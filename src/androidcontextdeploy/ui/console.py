"""The log console: timestamps, coloured levels, auto-scroll."""
from __future__ import annotations

import customtkinter as ctk

from androidcontextdeploy.i18n import t
from androidcontextdeploy.models import LogEvent
from androidcontextdeploy.ui import theme

_LEVEL_COLORS = {"OK": theme.ACCENT_LIGHT, "WARN": theme.WARN,
                 "ERROR": theme.ERROR, "INFO": theme.TEXT}


class ConsolePanel(ctk.CTkFrame):
    def __init__(self, master, banner: str) -> None:
        super().__init__(master, corner_radius=16, fg_color=theme.CARD)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._banner = banner

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=18, pady=(10, 2))
        ctk.CTkLabel(header, text=t("console.title"), font=theme.mono(13, "bold"),
                     text_color=theme.ACCENT_LIGHT).pack(side="left")
        ctk.CTkLabel(header, text="  " + t("console.subtitle"), font=theme.mono(11),
                     text_color=theme.MUTED).pack(side="left")
        ctk.CTkButton(
            header, text=t("console.clear"), width=84, height=26, corner_radius=8,
            fg_color="transparent", border_width=1, border_color=theme.MUTED,
            text_color=theme.TEXT, hover_color=theme.CARD,
            font=ctk.CTkFont(size=12), command=self.clear,
        ).pack(side="right")

        self._textbox = ctk.CTkTextbox(self, corner_radius=10, wrap="word",
                                       fg_color=theme.BG, text_color=theme.TEXT,
                                       font=theme.mono(13))
        self._textbox.grid(row=1, column=0, sticky="nsew", padx=14, pady=(0, 12))
        self._textbox.tag_config("banner", foreground=theme.ACCENT)
        self._textbox.tag_config("system", foreground=theme.MUTED)
        for level, color in _LEVEL_COLORS.items():
            self._textbox.tag_config(level, foreground=color)
        self._print_banner()

    def _print_banner(self) -> None:
        self._textbox.configure(state="normal")
        if self._banner:
            self._textbox.insert("end", self._banner + "\n", "banner")
        self._textbox.insert("end", t("console.ready") + "\n", "system")
        self._textbox.configure(state="disabled")

    def clear(self) -> None:
        self._textbox.configure(state="normal")
        self._textbox.delete("1.0", "end")
        self._textbox.configure(state="disabled")
        self._print_banner()

    def append(self, events: list[LogEvent]) -> None:
        if not events:
            return
        self._textbox.configure(state="normal")
        for event in events:
            self._textbox.insert("end", f"[{event.timestamp}] [{event.level}] {event.message}\n",
                                 event.level)
        self._textbox.see("end")
        self._textbox.configure(state="disabled")

    def append_text(self, lines: list[tuple[str, str]]) -> None:
        """Raw lines with a colour tag ("OK", "WARN", "ERROR", "INFO", "system")."""
        self._textbox.configure(state="normal")
        for text, tag in lines:
            self._textbox.insert("end", text + "\n", tag)
        self._textbox.see("end")
        self._textbox.configure(state="disabled")
