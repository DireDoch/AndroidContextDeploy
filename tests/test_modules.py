"""Modules against a fake phone: each returns Results the Checklist can show."""
from __future__ import annotations

from pathlib import Path

from androidcontextdeploy import i18n
from androidcontextdeploy.manifest import parse_manifest
from androidcontextdeploy.models import AppLogger, DeviceInfo, SessionConfig
from androidcontextdeploy.modules import MODULES, Context, applications, device_settings, final_check
from androidcontextdeploy.runner import WorkflowRunner

i18n.load(Path(__file__).resolve().parents[1], "en")


class FakePhone:
    """Settings that stick unless listed in `ignored`; apps that are installed or not."""

    def __init__(self, installed=(), ignored=(), work_user=10, pin_ok=True) -> None:
        self.settings: dict[tuple[str, str], str] = {}
        self.installed = set(installed)
        self.ignored = set(ignored)
        self.work_user = work_user
        self.pin_ok = pin_ok
        self.recorder = None
        self.opened: list[tuple[str, str]] = []

    def put_setting(self, serial, namespace, key, value):
        if key not in self.ignored:
            self.settings[(namespace, key)] = value
        return True, ""

    def get_setting(self, serial, namespace, key):
        return self.settings.get((namespace, key), "")

    def get_work_user_id(self, serial):
        return self.work_user

    def is_installed(self, serial, package_id, user=0):
        return package_id in self.installed

    def wait_for_package(self, serial, package_id, user=0, timeout=0, poll_interval=0):
        return package_id in self.installed

    def open_play_store(self, serial, package_id, user=0):
        return True, ""

    def open_app(self, serial, package_id, user=0, activity=""):
        self.opened.append((package_id, activity))
        return False, "permission to access user"   # a Work Profile app: Manual Action

    def pin_to_home(self, serial, package_id, name, user=0, activity=""):
        return self.pin_ok, ""


MANIFEST = parse_manifest({
    "organization": "Example Corp",
    "device_settings": [
        {"name": "Timeout", "namespace": "system", "key": "screen_off_timeout", "value": "600000"},
        {"name": "Brightness", "namespace": "system", "key": "screen_brightness", "value": "160"},
    ],
    "catalog": [
        {"name": "Teams", "package_id": "com.microsoft.teams", "pin": True},
        {"name": "Outlook", "package_id": "com.microsoft.office.outlook"},
        {"name": "Edge", "package_id": "com.microsoft.emmx", "selected": False},
    ],
})


def _ctx(phone, manifest=MANIFEST) -> Context:
    logger = AppLogger()
    return Context(session=SessionConfig("alex.martin@example.com", "x"),
                   device=DeviceInfo(connected=True, serial="X", work_user_id=10),
                   manifest=manifest, apps=[a for a in manifest.catalog if a.selected],
                   adb=phone, runner=WorkflowRunner(phone, logger), log=logger)


def test_every_module_has_the_contract() -> None:
    for module in MODULES:
        assert isinstance(module.NAME, str) and callable(module.run)


def test_device_settings_reads_back_what_the_phone_kept() -> None:
    results = device_settings.run(_ctx(FakePhone(ignored={"screen_brightness"})))
    assert [(r.name, r.kind) for r in results] == [("Timeout", "OK"), ("Brightness", "WARNING")]
    assert "device_settings[1]" in results[1].remedy


def test_applications_results_cover_every_catalog_entry() -> None:
    phone = FakePhone(installed={"com.microsoft.teams"}, pin_ok=False)
    results = {r.name: r for r in applications.run(_ctx(phone))}
    assert results["Teams"].kind == "MANUAL", "installed but the pin is left by hand"
    assert results["Outlook"].kind == "WARNING" and "Intune" in results["Outlook"].remedy
    assert results["Edge"].kind == "N/A", "unselected apps still appear in the Checklist"


def test_final_check_reports_profile_apps_and_lockdown() -> None:
    manifest = parse_manifest({
        "organization": "Example Corp",
        "catalog": [{"name": "Company Portal", "package_id": "cp", "enrollment": True},
                    {"name": "Teams", "package_id": "com.microsoft.teams"}],
    })
    results = final_check.run(_ctx(FakePhone(installed={"cp"}, work_user=0), manifest))
    kinds = [r.kind for r in results]
    assert kinds == ["ERROR", "WARNING", "MANUAL"], kinds
    assert "Teams" in results[1].detail


def test_a_crashing_module_becomes_an_error_result() -> None:
    class Broken:
        NAME = "device_settings"

        @staticmethod
        def run(ctx):
            raise RuntimeError("boom")

    ctx = _ctx(FakePhone())
    ctx.runner._busy = True
    ctx.runner._execute(Broken, ctx)
    assert ctx.runner.results[-1].kind == "ERROR" and not ctx.runner.busy
    assert ctx.runner.drain_events()[-1]["kinds"] == ["ERROR"]


def _signing_manifest():
    return parse_manifest({
        "organization": "Example Corp",
        "catalog": [{"name": "Company Portal", "package_id": "cp", "enrollment": True, "sign_in": True},
                    {"name": "Teams", "package_id": "com.microsoft.teams", "sign_in": True,
                     "activity": "com.microsoft.teams/.Main"}],
    })


def _driver(enrollment: str, sign_in: str, hand_typed: set[str]):
    class Driver:
        def __init__(self, runner, organization) -> None:
            self.hand_typed = hand_typed

        def run_enrollment(self, *args):
            return enrollment

        def run_sign_in(self, *args, **kwargs):
            return sign_in
    return Driver


def test_sign_in_outcomes_and_hand_typed_credentials_reach_the_checklist(monkeypatch) -> None:
    monkeypatch.setattr(applications, "OPEN_DELAY", 0)
    monkeypatch.setattr(applications, "SignInDriver", _driver("play_store", "timeout", {"Teams"}))
    phone = FakePhone(installed={"cp", "com.microsoft.teams"})
    results = {r.name: r for r in applications.run(_ctx(phone, _signing_manifest()))}
    assert results["Company Portal"].kind == "OK"
    assert results["Teams"].kind == "MANUAL"
    assert "sign in by hand" in results["Teams"].remedy and "typed by hand" in results["Teams"].remedy
    assert ("com.microsoft.teams", "com.microsoft.teams/.Main") in phone.opened, "the catalog activity is used"


def test_a_cancelled_enrollment_stops_the_apps_after_it(monkeypatch) -> None:
    monkeypatch.setattr(applications, "OPEN_DELAY", 0)
    monkeypatch.setattr(applications, "SignInDriver", _driver("cancelled", "auto", set()))
    phone = FakePhone(installed={"cp", "com.microsoft.teams"})
    results = {r.name: r for r in applications.run(_ctx(phone, _signing_manifest()))}
    assert results["Company Portal"].kind == "ERROR"
    assert results["Teams"].kind == "N/A"


def test_an_empty_selection_is_one_not_applicable_row() -> None:
    manifest = parse_manifest({"organization": "Example Corp", "catalog": []})
    assert [r.kind for r in applications.run(_ctx(FakePhone(), manifest))] == ["N/A"]
