"""Right panel: the Mirror (ADR-0003). Shows the stream at the phone's aspect
ratio and turns clicks and drags into touches in stream coordinates."""
from __future__ import annotations

from typing import Callable

import customtkinter as ctk
from PIL import Image

from androidcontextdeploy.i18n import t
from androidcontextdeploy.ui import theme


class MirrorPanel(ctk.CTkFrame):
    SIZES = {"compact": 56, "normal": 360, "large": 560}   # column width in px

    def __init__(self, master, on_touch: Callable[[float, float, str], None],
                 on_resize: Callable[[str], None]) -> None:
        super().__init__(master, corner_radius=16, fg_color=theme.CARD, width=360)
        self._on_touch = on_touch
        self._on_resize = on_resize
        self._size_state = "normal"
        self._image: ctk.CTkImage | None = None
        self._display_size = (0, 0)
        self._frame_size = (0, 0)
        self._streaming = False
        self.grid_propagate(False)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 2))
        header.grid_columnconfigure(0, weight=1)
        self._title = ctk.CTkLabel(header, text=t("mirror.title"), font=theme.mono(13, "bold"),
                                   text_color=theme.ACCENT_LIGHT, anchor="w")
        self._title.grid(row=0, column=0, sticky="ew")
        style = dict(width=28, height=26, corner_radius=8, fg_color="transparent", border_width=1,
                     border_color=theme.MUTED, text_color=theme.TEXT, hover_color=theme.CARD,
                     font=ctk.CTkFont(size=14))
        self._btn_enlarge = ctk.CTkButton(header, text="⤢", command=self._toggle_enlarge, **style)
        self._btn_enlarge.grid(row=0, column=1, padx=(4, 2))
        self._btn_min = ctk.CTkButton(header, text="–", command=self._toggle_minimize, **style)
        self._btn_min.grid(row=0, column=2)

        self._screen = ctk.CTkFrame(self, corner_radius=22, fg_color=theme.BG,
                                    border_width=2, border_color=theme.CARD_ALT)
        self._screen.grid(row=1, column=0, sticky="nsew", padx=18, pady=(6, 8))
        self._screen.grid_columnconfigure(0, weight=1)
        self._screen.grid_rowconfigure(0, weight=1)

        self._placeholder = ctk.CTkFrame(self._screen, fg_color="transparent")
        self._placeholder.grid(row=0, column=0, sticky="nsew")
        self._placeholder.grid_columnconfigure(0, weight=1)
        self._placeholder.grid_rowconfigure((0, 4), weight=1)
        self._icon = ctk.CTkLabel(self._placeholder, text="📵", font=ctk.CTkFont(size=44))
        self._icon.grid(row=1, column=0, pady=(0, 4))
        self._state = ctk.CTkLabel(self._placeholder, text=t("mirror.no_device"), justify="center",
                                   font=ctk.CTkFont(size=15, weight="bold"),
                                   text_color=theme.MUTED, wraplength=280)
        self._state.grid(row=2, column=0)
        # How the tool talks to the phone: ADB over USB debugging.
        self._instructions = ctk.CTkLabel(self._placeholder, text=t("mirror.instructions"),
                                          justify="left", anchor="w", font=ctk.CTkFont(size=12),
                                          text_color=theme.TEXT, wraplength=300)
        self._instructions.grid(row=3, column=0, padx=18, pady=(14, 0), sticky="w")

        self._video = ctk.CTkLabel(self._screen, text="", fg_color=theme.BG)
        self._video.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        self._video.bind("<Button-1>", lambda e: self._touch(e, "down"))
        self._video.bind("<B1-Motion>", lambda e: self._touch(e, "move"))
        self._video.bind("<ButtonRelease-1>", lambda e: self._touch(e, "up"))
        self._placeholder.tkraise()

        self._footer = ctk.CTkLabel(self, text=t("mirror.footer.waiting"), font=theme.mono(10),
                                    text_color=theme.MUTED)
        self._footer.grid(row=2, column=0, pady=(0, 12))

    def _toggle_minimize(self) -> None:
        self._apply_size("normal" if self._size_state == "compact" else "compact")

    def _toggle_enlarge(self) -> None:
        self._apply_size("normal" if self._size_state == "large" else "large")

    def _apply_size(self, state: str) -> None:
        self._size_state = state
        for widget in (self._screen, self._footer, self._title, self._btn_enlarge):
            widget.grid_remove() if state == "compact" else widget.grid()
        self._btn_min.configure(text="▣" if state == "compact" else "–")
        self.configure(width=self.SIZES[state])
        self._on_resize(state)

    def _show_state(self, icon: str, text: str, color: str, footer: str, instructions: bool) -> None:
        self._streaming = False
        self._icon.configure(text=icon)
        self._state.configure(text=text, text_color=color)
        self._footer.configure(text=footer)
        self._instructions.grid() if instructions else self._instructions.grid_remove()
        self._placeholder.tkraise()

    def set_disconnected(self) -> None:
        self._show_state("📵", t("mirror.no_device"), theme.MUTED, t("mirror.footer.waiting"), True)

    def set_connecting(self) -> None:
        self._show_state("📱", t("mirror.connecting"), theme.ACCENT_LIGHT, t("mirror.footer.connecting"), False)

    def set_unavailable(self, reason: str) -> None:
        self._show_state("📱", t("mirror.unavailable", reason=reason), theme.WARN,
                         t("mirror.footer.unavailable"), False)

    def show_frame(self, frame) -> None:
        """Draw a BGR numpy frame at the phone's aspect ratio."""
        height, width = frame.shape[0], frame.shape[1]
        # Scale with the SAME reference the touch mapping uses (_video), or
        # every tap lands systematically off.
        avail_w, avail_h = self._video.winfo_width(), self._video.winfo_height()
        if avail_w <= 1 or avail_h <= 1:          # not measured yet (first frame)
            avail_w = max(self._screen.winfo_width() - 8, 1)
            avail_h = max(self._screen.winfo_height() - 8, 1)
        scale = min(avail_w / width, avail_h / height)
        display = (max(int(width * scale), 1), max(int(height * scale), 1))
        picture = Image.fromarray(frame[:, :, ::-1])
        self._image = ctk.CTkImage(light_image=picture, dark_image=picture, size=display)
        self._video.configure(image=self._image)
        self._frame_size, self._display_size = (width, height), display
        if not self._streaming:
            self._streaming = True
            self._footer.configure(text=t("mirror.footer.live"))
            self._video.tkraise()

    def _touch(self, event, action: str) -> None:
        disp_w, disp_h = self._display_size
        if not self._streaming or disp_w <= 0 or disp_h <= 0:
            return
        # The image is centred in the label: remove the margins first.
        ratio_x = (event.x - (self._video.winfo_width() - disp_w) / 2) / disp_w
        ratio_y = (event.y - (self._video.winfo_height() - disp_h) / 2) / disp_h
        if action == "down" and not (0 <= ratio_x <= 1 and 0 <= ratio_y <= 1):
            return
        frame_w, frame_h = self._frame_size
        self._on_touch(min(max(ratio_x, 0.0), 1.0) * frame_w,
                       min(max(ratio_y, 0.0), 1.0) * frame_h, action)
