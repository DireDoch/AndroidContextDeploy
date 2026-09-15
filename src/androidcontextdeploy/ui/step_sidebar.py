"""Vertical progress sidebar: one line per Module, its state, and the apps of
the Applications Module unfolding underneath with a spinner on the one at work."""
from __future__ import annotations

import customtkinter as ctk

from androidcontextdeploy.i18n import t
from androidcontextdeploy.ui import theme

_SPINNER = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

# app status -> (glyph, colour, spinning?)
_APP_STATUS = {
    "waiting":        ("○", theme.MUTED, False),
    "opening_store":  ("",  theme.INFO, True),
    "installing":     ("",  theme.INFO, True),
    "manual":         ("👉", theme.ACTION, False),
    "installed":      ("✓", theme.ACCENT_LIGHT, False),
    "auth_pending":   ("",  theme.ACTION, True),
    "auth_confirmed": ("✓", theme.ACCENT_LIGHT, False),
    "pinning":        ("",  theme.INFO, True),
    "pinned":         ("✓", theme.ACCENT_LIGHT, False),
    "pin_manual":     ("⚠", theme.WARN, False),
    "failed":         ("✗", theme.ERROR, False),
}


class StepSidebar(ctk.CTkFrame):
    def __init__(self, master, steps: list[tuple[str, str]]) -> None:
        super().__init__(master, corner_radius=12, fg_color=theme.CARD_ALT)
        self._keys = [key for key, _ in steps]
        self._running = False
        self._current = ""
        self._completed: set[str] = set()
        self._issues: set[str] = set()
        self._spinning: dict[str, ctk.CTkLabel] = {}
        self._frame = 0
        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self, text=t("sidebar.title"), font=theme.mono(11, "bold"),
                     text_color=theme.MUTED, anchor="w").grid(
            row=0, column=0, sticky="ew", padx=14, pady=(10, 0))
        self._remaining = ctk.CTkLabel(self, text="", font=ctk.CTkFont(size=11),
                                       text_color=theme.MUTED, anchor="w")
        self._remaining.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 6))

        self._glyphs: dict[str, ctk.CTkLabel] = {}
        self._names: dict[str, ctk.CTkLabel] = {}
        self._holders: dict[str, ctk.CTkFrame] = {}
        self._app_rows: dict[str, tuple[ctk.CTkLabel, ctk.CTkLabel]] = {}
        row = 2
        for key, label in steps:
            line = ctk.CTkFrame(self, fg_color="transparent")
            line.grid(row=row, column=0, sticky="ew", padx=10, pady=1)
            line.grid_columnconfigure(1, weight=1)
            self._glyphs[key] = ctk.CTkLabel(line, text="○", width=18, font=theme.mono(13, "bold"),
                                             text_color=theme.MUTED)
            self._glyphs[key].grid(row=0, column=0, sticky="w", padx=(4, 6))
            self._names[key] = ctk.CTkLabel(line, text=label, anchor="w",
                                            font=ctk.CTkFont(size=13), text_color=theme.MUTED)
            self._names[key].grid(row=0, column=1, sticky="ew")
            holder = ctk.CTkFrame(self, fg_color="transparent")
            holder.grid(row=row + 1, column=0, sticky="ew", padx=(28, 10))
            holder.grid_columnconfigure(1, weight=1)
            holder.grid_remove()
            self._holders[key] = holder
            row += 2
        self.grid_rowconfigure(row, minsize=8)
        self._animate()

    def _animate(self) -> None:
        glyph = _SPINNER[self._frame % len(_SPINNER)]
        for label in self._spinning.values():
            label.configure(text=glyph)
        self._frame += 1
        self.after(90, self._animate)

    def set_states(self, completed: set[str], current: str, issues: set[str]) -> None:
        self._completed, self._current, self._issues = set(completed), current, set(issues)
        for key in self._keys:
            glyph, name = self._glyphs[key], self._names[key]
            self._spinning.pop(f"step:{key}", None)
            if key in self._completed:
                color = theme.WARN if key in self._issues else theme.ACCENT_LIGHT
                glyph.configure(text="⚠" if key in self._issues else "✓", text_color=color)
                name.configure(text_color=color)
            elif key == current:
                name.configure(text_color=theme.TEXT)
                if self._running:
                    glyph.configure(text_color=theme.ACCENT)
                    self._spinning[f"step:{key}"] = glyph
                else:
                    glyph.configure(text="▶", text_color=theme.ACCENT)
            else:
                glyph.configure(text="○", text_color=theme.MUTED)
                name.configure(text_color=theme.MUTED)
        done = len(self._completed & set(self._keys))
        self._remaining.configure(text=t("sidebar.progress", done=done, total=len(self._keys)))

    def set_running(self, running: bool) -> None:
        self._running = running
        self.set_states(self._completed, self._current, self._issues)

    def build_apps(self, key: str, app_names: list[str]) -> None:
        holder = self._holders.get(key)
        if holder is None:
            return
        for widget in holder.winfo_children():
            widget.destroy()
        self._app_rows.clear()
        for i, name in enumerate(app_names):
            glyph = ctk.CTkLabel(holder, text="○", width=16, font=theme.mono(12, "bold"),
                                 text_color=theme.MUTED)
            glyph.grid(row=i, column=0, sticky="w", padx=(0, 6), pady=1)
            label = ctk.CTkLabel(holder, text=name, anchor="w", font=ctk.CTkFont(size=12),
                                 text_color=theme.MUTED)
            label.grid(row=i, column=1, sticky="ew", pady=1)
            self._app_rows[name] = (glyph, label)
        holder.grid() if app_names else holder.grid_remove()

    def set_app_status(self, app_name: str, status: str) -> None:
        if app_name not in self._app_rows:
            return
        glyph, label = self._app_rows[app_name]
        symbol, color, spinning = _APP_STATUS.get(status, ("○", theme.MUTED, False))
        if spinning:
            glyph.configure(text_color=color)
            self._spinning[f"app:{app_name}"] = glyph
        else:
            self._spinning.pop(f"app:{app_name}", None)
            glyph.configure(text=symbol, text_color=color)
        label.configure(text_color=color)

    def clear_apps(self) -> None:
        for key in self._keys:
            self.build_apps(key, [])
        for key in [k for k in self._spinning if k.startswith("app:")]:
            self._spinning.pop(key)
