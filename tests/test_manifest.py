"""deploy.json: the shipped file is valid, and a mistake names the key to fix."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from androidcontextdeploy.manifest import ManifestError, app_root, load_manifest, parse_manifest

ROOT = Path(__file__).resolve().parents[1]


def test_shipped_manifest_is_valid() -> None:
    manifest = load_manifest(ROOT / "deploy.json")
    assert manifest.organization
    assert manifest.catalog[0].enrollment
    assert manifest.device_settings


def _base(**changes) -> dict:
    data = {
        "organization": "Example Corp",
        "device_settings": [{"name": "Timeout", "namespace": "system",
                             "key": "screen_off_timeout", "value": 600000}],
        "catalog": [{"name": "Company Portal", "package_id": "com.x", "enrollment": True},
                    {"name": "Teams", "package_id": "com.y"}],
    }
    data.update(changes)
    return data


def test_numbers_become_strings_and_defaults_apply() -> None:
    manifest = parse_manifest(_base())
    assert manifest.device_settings[0].value == "600000"
    assert manifest.language == "auto"
    assert manifest.catalog[1].selected and not manifest.catalog[1].sign_in


@pytest.mark.parametrize("changes, message", [
    ({"organization": ""}, "'organization'"),
    ({"device_settings": [{"name": "x", "namespace": "vendor", "key": "k", "value": "v"}]},
     "device_settings[0]: 'namespace'"),
    ({"catalog": [{"name": "A", "package_id": ""}]}, "catalog[0]: 'package_id'"),
    ({"catalog": [{"name": "A", "package_id": "a"}, {"name": "A", "package_id": "b"}]}, "duplicate"),
    ({"catalog": [{"name": "A", "package_id": "a"},
                  {"name": "B", "package_id": "b", "enrollment": True}]}, "must be the first"),
])
def test_invalid_manifest_names_the_key(changes, message) -> None:
    with pytest.raises(ManifestError, match=message.replace("[", r"\[").replace("]", r"\]")):
        parse_manifest(_base(**changes))


def test_json_syntax_error_gives_the_line(tmp_path) -> None:
    path = tmp_path / "deploy.json"
    path.write_text('{\n  "organization": "Example Corp",\n}', encoding="utf-8")
    with pytest.raises(ManifestError, match="line 3"):
        load_manifest(path)


def test_app_root() -> None:
    assert (app_root() / "deploy.json").exists(), "not frozen: the repo root"
    sys.frozen = True
    try:
        assert app_root() == Path(sys.executable).resolve().parent
    finally:
        del sys.frozen


def test_locale_files_are_valid_json() -> None:
    for path in (ROOT / "locales").glob("*.json"):
        json.loads(path.read_text(encoding="utf-8"))


def test_activity_is_optional_and_must_name_a_component() -> None:
    manifest = parse_manifest(_base(catalog=[{"name": "Teams", "package_id": "com.y", "activity": "com.y/.Main"}]))
    assert manifest.catalog[0].activity == "com.y/.Main"
    with pytest.raises(ManifestError, match="activity"):
        parse_manifest(_base(catalog=[{"name": "Teams", "package_id": "com.y", "activity": "Main"}]))
