"""Colours and fonts shared by the panels. Change the look here, nowhere else."""
from __future__ import annotations

import sys

import customtkinter as ctk

from androidcontextdeploy.manifest import app_root

BG           = "#111412"
CARD         = "#1a1e1b"
CARD_ALT     = "#232924"
ACCENT       = "#3a9a6a"
ACCENT_HOVER = "#2f7f57"
ACCENT_LIGHT = "#8fd6a8"
TEXT         = "#e8eae6"
MUTED        = "#8c948d"

# State colours, reserved for statuses.
ERROR       = "#d0453a"
WARN        = "#d08a30"
MANUAL      = "#e0a040"
CONFIRM     = "#1f6a3c"
CONFIRM_HOVER = "#185630"
LIVE        = "#22c55e"
OFFLINE     = "#e02020"
INFO        = "#60a5fa"
ACTION      = "#f97316"

KIND_COLORS = {"OK": ACCENT_LIGHT, "WARNING": WARN, "ERROR": ERROR,
               "MANUAL": MANUAL, "N/A": MUTED}

MONO = "Consolas" if sys.platform == "win32" else "DejaVu Sans Mono"
APP_NAME = "AndroidContextDeploy"


def mono(size: int, weight: str = "normal") -> ctk.CTkFont:
    return ctk.CTkFont(family=MONO, size=size, weight=weight)


def load_banner() -> str:
    """banner.txt next to the tool; "" when absent (the plain name is shown)."""
    try:
        return (app_root() / "banner.txt").read_text(encoding="utf-8").rstrip("\n")
    except OSError:
        return ""
