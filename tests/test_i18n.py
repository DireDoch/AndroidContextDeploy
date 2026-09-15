"""Every string the code asks for exists in every locale, with the same placeholders."""
from __future__ import annotations

import json
import re
import string
from pathlib import Path

from androidcontextdeploy.modules import MODULES

ROOT = Path(__file__).resolve().parents[1]
LOCALES = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in (ROOT / "locales").glob("*.json")}

# Keys built at runtime (f-strings) that a grep cannot see.
DYNAMIC = (
    [f"module.{m.NAME}.{part}" for m in MODULES for part in ("title", "description", "run")]
    + [f"device.state.{s}" for s in ("none", "not_ready", "connected", "adb_missing")]
    + [f"app_status.{s}" for s in ("waiting", "opening_store", "installing", "installed", "manual",
                                   "auth_pending", "auth_confirmed", "pinning", "pinned",
                                   "pin_manual", "failed")]
    + [f"enroll.target.{r}" for r in ("skip", "link", "accept", "continue", "phone_option",
                                      "confirm", "device_org", "finish", "sms_checkbox", "next")]
)


def _code_keys() -> set[str]:
    pattern = re.compile(r"""\bt\(\s*["']([a-z_.]+)["']""")
    keys = set(DYNAMIC)
    for path in (ROOT / "src").rglob("*.py"):
        keys |= set(pattern.findall(path.read_text(encoding="utf-8")))
    return keys


def _fields(text: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(text) if name}


def test_english_has_every_key_the_code_uses() -> None:
    missing = sorted(_code_keys() - LOCALES["en"].keys())
    assert not missing, f"add to locales/en.json: {missing}"


def test_translations_match_english() -> None:
    english = LOCALES["en"]
    for language, strings in LOCALES.items():
        assert strings.keys() == english.keys(), \
            f"{language}.json: missing {sorted(english.keys() - strings.keys())}, " \
            f"extra {sorted(strings.keys() - english.keys())}"
        for key, text in strings.items():
            assert _fields(text) == _fields(english[key]), f"{language}.json '{key}': placeholders differ"
