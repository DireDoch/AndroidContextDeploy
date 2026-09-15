"""The Manifest: deploy.json, every site-specific value in one editable file.

Adapting the tool to another company is a Manifest edit, never a code edit. The
file is user-written, so it is validated here and a mistake is reported with
the key to fix rather than surfacing later as a KeyError mid-run.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

MANIFEST_NAME = "deploy.json"
SETTING_NAMESPACES = ("system", "secure", "global")


class ManifestError(ValueError):
    pass


@dataclass(slots=True)
class DeviceSetting:
    name: str
    namespace: str
    key: str
    value: str


@dataclass(slots=True)
class AppEntry:
    name: str
    package_id: str
    enrollment: bool = False   # the Company Portal: creates the Work Profile
    sign_in: bool = False      # run the Detection Loop and inject credentials
    pin: bool = False          # put a shortcut on the home screen
    selected: bool = True      # ticked by default in the Applications card
    activity: str = ""         # launcher activity, for phones that cannot resolve it


@dataclass(slots=True)
class Manifest:
    organization: str
    language: str = "auto"
    device_settings: list[DeviceSetting] = field(default_factory=list)
    catalog: list[AppEntry] = field(default_factory=list)


def app_root() -> Path:
    """Where deploy.json, banner.txt, locales/ and scrcpy_server/ live, and where
    diag/ is written: next to the executable when frozen, the repo root otherwise."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def _require_str(data: dict, key: str, where: str) -> str:
    value = data.get(key)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        value = str(value)
    if not isinstance(value, str) or not value.strip():
        raise ManifestError(f"{where}: '{key}' must be a non-empty string.")
    return value.strip()


def parse_manifest(data: object) -> Manifest:
    if not isinstance(data, dict):
        raise ManifestError("deploy.json must contain a JSON object.")

    organization = _require_str(data, "organization", "deploy.json")
    language = str(data.get("language", "auto"))

    settings: list[DeviceSetting] = []
    for i, raw in enumerate(data.get("device_settings", [])):
        where = f"device_settings[{i}]"
        if not isinstance(raw, dict):
            raise ManifestError(f"{where} must be an object.")
        namespace = _require_str(raw, "namespace", where)
        if namespace not in SETTING_NAMESPACES:
            raise ManifestError(
                f"{where}: 'namespace' must be one of {', '.join(SETTING_NAMESPACES)}.")
        settings.append(DeviceSetting(
            name=_require_str(raw, "name", where), namespace=namespace,
            key=_require_str(raw, "key", where), value=_require_str(raw, "value", where)))

    catalog: list[AppEntry] = []
    for i, raw in enumerate(data.get("catalog", [])):
        where = f"catalog[{i}]"
        if not isinstance(raw, dict):
            raise ManifestError(f"{where} must be an object.")
        activity = str(raw.get("activity", "")).strip()
        if activity and "/" not in activity:
            raise ManifestError(f"{where}: 'activity' must look like package/.Activity.")
        catalog.append(AppEntry(
            name=_require_str(raw, "name", where),
            package_id=_require_str(raw, "package_id", where),
            enrollment=bool(raw.get("enrollment", False)),
            sign_in=bool(raw.get("sign_in", False)),
            pin=bool(raw.get("pin", False)),
            selected=bool(raw.get("selected", True)),
            activity=activity,
        ))

    names = [app.name for app in catalog]
    duplicates = sorted({n for n in names if names.count(n) > 1})
    if duplicates:
        raise ManifestError(f"catalog: duplicate name(s): {', '.join(duplicates)}.")
    enrollment = [i for i, app in enumerate(catalog) if app.enrollment]
    if len(enrollment) > 1:
        raise ManifestError("catalog: only one entry can have 'enrollment': true.")
    if enrollment and enrollment[0] != 0:
        # Every other app lives in the Work Profile the enrollment creates.
        raise ManifestError("catalog: the 'enrollment' entry must be the first one.")

    return Manifest(organization, language, settings, catalog)


def load_manifest(path: Path) -> Manifest:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except OSError as exc:
        raise ManifestError(f"Cannot read {path}: {exc.strerror or exc}") from exc
    except json.JSONDecodeError as exc:
        raise ManifestError(
            f"{Path(path).name}, line {exc.lineno}: {exc.msg}.") from exc
    return parse_manifest(data)
