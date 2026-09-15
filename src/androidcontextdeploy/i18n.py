"""UI Language: every string the technician reads lives in locales/<lang>.json.

Adding a language is copying locales/en.json and translating the values -- no
code. A key missing from a translation falls back to English, then to the key
itself, so an incomplete file degrades instead of crashing.
"""
from __future__ import annotations

import json
import locale
from pathlib import Path

_strings: dict[str, str] = {}
_fallback: dict[str, str] = {}


def _read(path: Path) -> dict[str, str]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def load(root: Path, language: str = "auto") -> str:
    """Load locales/<language>.json. "auto" follows the system locale.
    Returns the language actually used."""
    global _strings, _fallback
    folder = Path(root) / "locales"
    if language == "auto":
        # "fr_CA" on Linux/macOS, "French_Canada" on Windows.
        system = (locale.getlocale()[0] or "").lower()
        language = "fr" if system.startswith("fr") else "en"
    if not (folder / f"{language}.json").exists():
        language = "en"
    _fallback = _read(folder / "en.json")
    _strings = _fallback if language == "en" else _read(folder / f"{language}.json")
    return language


def t(key: str, **values: object) -> str:
    text = _strings.get(key) or _fallback.get(key) or key
    return text.format(**values) if values else text
