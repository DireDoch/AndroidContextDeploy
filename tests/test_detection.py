"""The Detection Loop and the Enrollment controller, replayed on uiautomator
dumps. No phone needed: ScreenDetector is pure parsing and adb is faked.

To lock in a screen captured with --diag: paste its (masked) XML as a DUMP_*
constant, assert what the detector sees, and run `pytest`.
"""
from __future__ import annotations

import threading
from pathlib import Path

from androidcontextdeploy import i18n
from androidcontextdeploy.adb import AdbService
from androidcontextdeploy.detection import ScreenDetector
from androidcontextdeploy.models import AppLogger, DeviceInfo, SessionConfig
from androidcontextdeploy.runner import WorkflowRunner
from androidcontextdeploy.signin import SignInDriver

i18n.load(Path(__file__).resolve().parents[1], "en")

EMAIL = "alex.martin@contoso.com"
PASSWORD = "S3cret&Pass!"
PHONE = "+1 202 555 0143"


def _wrap(nodes: str) -> str:
    return '<?xml version="1.0" encoding="UTF-8"?><hierarchy rotation="0">' + nodes + "</hierarchy>"


# Microsoft email page in a WebView: the placeholder shows up as text.
DUMP_EMAIL_WEBVIEW = _wrap(
    '<node class="android.webkit.WebView" text="" bounds="[0,0][1080,2200]">'
    '<node class="android.widget.TextView" text="Se connecter" bounds="[80,400][1000,480]"/>'
    '<node class="android.widget.EditText" text="Email, phone, or Skype"'
    ' resource-id="i0116" content-desc="" focused="false" password="false"'
    ' bounds="[80,600][1000,720]"/>'
    '<node class="android.widget.Button" text="Suivant" bounds="[700,800][1000,900]"/>'
    "</node>")
DUMP_EMAIL_FILLED = DUMP_EMAIL_WEBVIEW.replace("Email, phone, or Skype", EMAIL)

DUMP_PASSWORD = _wrap(
    '<node class="android.webkit.WebView" text="" bounds="[0,0][1080,2200]">'
    '<node class="android.widget.TextView" text="Entrez votre mot de passe" bounds="[80,400][1000,480]"/>'
    '<node class="android.widget.EditText" text="" resource-id="i0118"'
    ' password="true" focused="true" bounds="[80,600][1000,720]"/>'
    "</node>")
DUMP_PASSWORD_FILLED = DUMP_PASSWORD.replace('text="" resource-id="i0118"',
                                             'text="••••••••" resource-id="i0118"')

DUMP_MFA = _wrap(
    '<node class="android.widget.TextView" text="Approuver la connexion" bounds="[80,400][1000,480]"/>'
    '<node class="android.widget.TextView" text="Ouvrez votre application Authenticator"'
    ' bounds="[80,500][1000,560]"/>')

DUMP_HOME = _wrap(
    '<node class="android.widget.TextView" text="Home" bounds="[0,0][540,120]"/>'
    '<node class="android.widget.TextView" text="My devices" bounds="[0,200][540,320]"/>')

DUMP_ADD_ACCOUNT = _wrap(
    '<node class="android.widget.TextView" text="Bienvenue" bounds="[0,100][1080,200]"/>'
    '<node class="android.widget.Button" text="Ajouter un compte" clickable="true"'
    ' bounds="[140,1800][940,1920]"/>')

DUMP_ACCOUNT_TYPE = _wrap(
    '<node class="android.widget.TextView" text="Choisissez un type de compte" bounds="[0,100][1080,200]"/>'
    '<node class="android.view.View" text="" content-desc="Compte professionnel ou scolaire"'
    ' clickable="true" bounds="[80,600][1000,720]"/>'
    '<node class="android.view.View" text="" content-desc="Compte personnel"'
    ' clickable="true" bounds="[80,760][1000,880]"/>')

DUMP_EMAIL_NATIVE = _wrap(
    '<node class="android.widget.AutoCompleteTextView" text=""'
    ' resource-id="com.azure.authenticator:id/email_input" password="false"'
    ' focused="true" bounds="[40,300][1040,420]"/>'
    '<node class="android.widget.TextView" text="Sign in" bounds="[40,100][500,180]"/>')

# Captured on a real phone: a lone field whose hint mentions "phone" and "SMS".
# Without the code-field guard the email would be typed into it.
DUMP_OTC_CODE = _wrap(
    '<node class="android.widget.TextView" text="Connectez-vous à votre compte" bounds="[40,200][1040,300]"/>'
    '<node class="android.widget.TextView" text="Entrer le code" bounds="[40,360][1040,420]"/>'
    '<node class="android.widget.EditText" text="" resource-id="idTxtBx_SAOTCC_OTC"'
    ' password="false" focused="true"'
    ' content-desc="Entrer le code Nous avons envoyé un SMS sur votre téléphone'
    ' +X XXXXXXXX43. Veuillez entrer le code pour vous connecter."'
    ' bounds="[40,480][1040,600]"/>'
    '<node class="android.widget.Button" text="Vérifier" clickable="true" bounds="[700,700][1000,800]"/>'
    '<node class="android.widget.Button" text="Se connecter d\'une autre façon"'
    ' clickable="true" bounds="[40,900][1000,1000]"/>')

# ── Enrollment named screens ──────────────────────────────────────────────────
DUMP_SKIP_SETUP = _wrap(
    '<node class="android.widget.TextView" text="Terminer la configuration du compte" bounds="[0,200][1080,300]"/>'
    '<node class="android.widget.Button" text="Ignorer" clickable="true" bounds="[700,1800][1000,1900]"/>'
    '<node class="android.widget.Button" text="Continuer" clickable="true" bounds="[80,1800][680,1900]"/>')

# The "different method" LINK must win over the main Next button.
DUMP_OTHER_METHOD = _wrap(
    '<node class="android.widget.TextView" text="Microsoft Authenticator" bounds="[0,100][1080,200]"/>'
    '<node class="android.widget.TextView" text="Je veux configurer une autre méthode" clickable="true"'
    ' bounds="[80,1400][1000,1480]"/>'
    '<node class="android.widget.Button" text="Suivant" clickable="true" bounds="[700,1700][1000,1800]"/>')

DUMP_METHOD_DIALOG = _wrap(
    '<node class="android.widget.TextView" text="Quelle méthode voulez-vous utiliser ?" bounds="[0,400][1080,500]"/>'
    '<node class="android.view.View" text="Téléphone" clickable="true" bounds="[80,600][1000,720]"/>'
    '<node class="android.widget.Button" text="Confirmer" clickable="true" bounds="[600,900][1000,1000]"/>')
DUMP_METHOD_DIALOG_CONFIRM = _wrap(
    '<node class="android.widget.TextView" text="Quelle méthode voulez-vous utiliser ?" bounds="[0,400][1080,500]"/>'
    '<node class="android.widget.Button" text="Confirmer" clickable="true" bounds="[600,900][1000,1000]"/>')

DUMP_PHONE_ENTRY = _wrap(
    '<node class="android.widget.TextView" text="Téléphone" bounds="[80,300][1000,360]"/>'
    '<node class="android.widget.EditText" text="" resource-id="phoneNumber" password="false"'
    ' bounds="[80,400][1000,520]"/>'
    '<node class="android.widget.CheckBox" text="Envoyez-moi un code par texto" clickable="true"'
    ' bounds="[80,600][1000,680]"/>'
    '<node class="android.widget.Button" text="Suivant" clickable="true" bounds="[700,900][1000,1000]"/>')

# Must target CONTINUER, never SE DÉCONNECTER.
DUMP_ACCESS_SETUP = _wrap(
    '<node class="android.widget.TextView" text="Configuration de l\'accès à Contoso" bounds="[0,200][1080,320]"/>'
    '<node class="android.widget.TextView" text="Créer un profil professionnel" bounds="[120,600][1000,680]"/>'
    '<node class="android.widget.TextView" text="Activer un profil professionnel" bounds="[120,760][1000,840]"/>'
    '<node class="android.widget.Button" text="SE DÉCONNECTER" clickable="true" bounds="[40,1700][520,1800]"/>'
    '<node class="android.widget.Button" text="CONTINUER" clickable="true" bounds="[560,1700][1040,1800]"/>')

DUMP_TERMS = _wrap(
    '<node class="android.widget.TextView" text="Termes d\'utilisation" bounds="[0,100][1080,200]"/>'
    '<node class="android.widget.Button" text="Accepter" clickable="true" bounds="[600,1800][1000,1900]"/>')

# The Organization's device, NEVER the personal one.
DUMP_OWNERSHIP = _wrap(
    '<node class="android.widget.TextView" text="À qui appartient cet appareil ?" bounds="[0,200][1080,300]"/>'
    '<node class="android.view.View" text="CONTOSO device" clickable="true" bounds="[80,500][1000,620]"/>'
    '<node class="android.view.View" text="PERSONAL device" clickable="true" bounds="[80,680][1000,800]"/>'
    '<node class="android.widget.Button" text="Terminer" clickable="true" bounds="[600,1800][1000,1900]"/>')

DUMP_MANAGED_PLAY_STORE = _wrap(
    '<node class="android.widget.TextView" text="Ouvrez la version de Google Play avec badges"'
    ' bounds="[0,200][1080,300]"/>'
    '<node class="android.widget.TextView" text="applications suggérées par Contoso" bounds="[0,320][1080,400]"/>')


def test_detector() -> None:
    d = ScreenDetector("Contoso")

    s = d.analyze(DUMP_EMAIL_WEBVIEW)
    assert s.email_field is not None and s.email_field.is_empty, "placeholder counts as empty"
    assert (s.email_field.center_x, s.email_field.center_y) == (540, 660)
    assert s.password_field is None and s.login_markers and not s.mfa_detected

    assert not d.analyze(DUMP_EMAIL_FILLED).email_field.is_empty, "an address (with @) is filled"

    s = d.analyze(DUMP_PASSWORD)
    assert s.password_field is not None and s.password_field.is_empty and s.email_field is None
    assert not d.analyze(DUMP_PASSWORD_FILLED).password_field.is_empty, "mask dots = typed"

    s = d.analyze(DUMP_MFA)
    assert s.mfa_detected and "approuver" in s.mfa_hint

    s = d.analyze(DUMP_HOME)
    assert not s.login_markers and not s.mfa_detected and s.email_field is None

    assert d.analyze(DUMP_EMAIL_NATIVE).email_field.is_empty

    s = d.analyze(DUMP_ADD_ACCOUNT)
    assert s.action_button.text == "Ajouter un compte"
    assert (s.action_button.center_x, s.action_button.center_y) == (540, 1860)

    s = d.analyze(DUMP_ACCOUNT_TYPE)
    assert "professionnel" in s.action_button.content_desc.lower(), "work account, not personal"

    s = d.analyze(DUMP_OTC_CODE)
    assert s.otc_field is not None
    assert s.email_field is None, "a code field is NEVER an email field"
    assert s.password_field is None

    assert d.analyze("not xml") is None


def test_named_screens() -> None:
    d = ScreenDetector("Contoso")

    s = d.analyze(DUMP_SKIP_SETUP)
    assert s.named_screen == "skip_setup" and s.named_targets["skip"].text == "Ignorer"
    assert {"Ignorer", "Continuer"} <= set(s.clickable_labels)

    s = d.analyze(DUMP_OTHER_METHOD)
    assert s.named_screen == "authenticator_other_method"
    assert "autre" in s.named_targets["link"].text.lower()

    s = d.analyze(DUMP_METHOD_DIALOG)
    assert s.named_screen == "method_dialog"
    assert s.named_targets["phone_option"].text == "Téléphone"
    assert s.named_targets["confirm"].text == "Confirmer"

    s = d.analyze(DUMP_PHONE_ENTRY)
    assert s.named_screen == "phone_entry"
    assert s.named_targets["phone"].resource_id == "phoneNumber"
    assert "texto" in s.named_targets["sms_checkbox"].text.lower()
    assert s.named_targets["next"].text == "Suivant"

    s = d.analyze(DUMP_ACCESS_SETUP)
    assert s.named_screen == "access_setup"
    assert s.named_targets["continue"].center_x == 800, "CONTINUER (right), not SE DÉCONNECTER"

    s = d.analyze(DUMP_TERMS)
    assert s.named_screen == "terms" and s.named_targets["accept"].text == "Accepter"

    s = d.analyze(DUMP_OWNERSHIP)
    assert s.named_screen == "ownership"
    assert s.named_targets["device_org"].text == "CONTOSO device"
    assert s.named_targets["finish"].text == "Terminer"

    # Another Organization never taps Contoso's option -- nor the personal one.
    s = ScreenDetector("Fabrikam").analyze(DUMP_OWNERSHIP)
    assert "device_org" not in s.named_targets

    s = d.analyze(DUMP_MANAGED_PLAY_STORE)
    assert s.managed_play_store and s.named_screen == ""

    s = d.analyze(DUMP_HOME)
    assert s.named_screen == "" and not s.managed_play_store


class FakeAdb:
    """Replays dumps and records every action sent to the phone."""

    def __init__(self, dumps: list[str], play_store_focused: bool = False) -> None:
        self.dumps = list(dumps)
        self.actions: list[tuple] = []
        self.play_store_focused = play_store_focused

    def dump_ui_xml(self, serial):
        return self.dumps.pop(0) if self.dumps else DUMP_HOME

    def get_focused_activity(self, serial):
        return ""     # constant: the loop falls back to poll_interval (fast in tests)

    def is_play_store_focused(self, serial):
        return self.play_store_focused

    def tap(self, serial, x, y):
        self.actions.append(("tap", x, y))
        return True, ""

    def inject_text(self, serial, text):
        self.actions.append(("text", text))
        return True, ""

    def press_key(self, serial, key):
        self.actions.append(("key", key))
        return True, ""


def _driver(adb) -> tuple[SignInDriver, WorkflowRunner, AppLogger]:
    logger = AppLogger()
    runner = WorkflowRunner(adb, logger)
    return SignInDriver(runner, "Contoso"), runner, logger


def _sign_in(dumps, confirm_after=None):
    adb = FakeAdb(dumps)
    driver, runner, logger = _driver(adb)
    if confirm_after is not None:
        threading.Timer(confirm_after, runner.confirm_auth).start()
    outcome = driver.run_sign_in(SessionConfig(EMAIL, PASSWORD), DeviceInfo(connected=True, serial="X"),
                                 "Microsoft Teams", timeout=30, poll_interval=0.01)
    return outcome, adb, " ".join(e.message for e in logger.drain())


def _enroll(dumps, phone=PHONE, play_store_focused=False, cancel_after=None, confirm_after=None):
    adb = FakeAdb(dumps, play_store_focused)
    driver, runner, logger = _driver(adb)
    if cancel_after is not None:
        threading.Timer(cancel_after, runner.cancel_session).start()
    if confirm_after is not None:
        threading.Timer(confirm_after, runner.confirm_auth).start()
    outcome = driver.run_enrollment(SessionConfig(EMAIL, PASSWORD, phone),
                                    DeviceInfo(connected=True, serial="X"),
                                    "Company Portal", poll_interval=0.01)
    return outcome, adb, " ".join(e.message for e in logger.drain())


def test_play_store_focus_signal() -> None:
    assert AdbService.focus_is_play_store(
        "mCurrentFocus=Window{a1b2 u10 com.android.vending/com.google.android.finsky.activities.MainActivity}")
    assert AdbService.focus_is_play_store("mFocusedApp=ActivityRecord{x u10 com.android.vending/.Foo}")
    assert not AdbService.focus_is_play_store(
        "mCurrentFocus=Window{x u10 com.microsoft.windowsintune.companyportal/.MainActivity}")
    assert not AdbService.focus_is_play_store("")


def test_enrollment_full_flow() -> None:
    outcome, adb, messages = _enroll([
        DUMP_ACCESS_SETUP, DUMP_SKIP_SETUP, DUMP_OTHER_METHOD,
        DUMP_METHOD_DIALOG, DUMP_METHOD_DIALOG_CONFIRM,
        DUMP_PHONE_ENTRY, DUMP_PHONE_ENTRY, DUMP_PHONE_ENTRY,   # number, checkbox, Next
        DUMP_MFA, DUMP_MFA, DUMP_TERMS,
        DUMP_OWNERSHIP, DUMP_OWNERSHIP,                          # Contoso, then Finish
        DUMP_MANAGED_PLAY_STORE,                                 # the gate
    ])
    assert outcome == "play_store"
    assert [a[1] for a in adb.actions if a[0] == "text"] == [PHONE]
    taps = [(a[1], a[2]) for a in adb.actions if a[0] == "tap"]
    assert (540, 1440) in taps, "the 'different method' link is tapped"
    assert (850, 1750) not in taps, "the main Next button is NEVER tapped"
    assert (540, 560) in taps, "the Contoso device option is tapped"
    assert (540, 740) not in taps, "the personal device option is NEVER tapped"
    assert "S3cret" not in messages and "0143" not in messages, "no secret in the log"


def test_enrollment_gate_by_focus() -> None:
    outcome, adb, _ = _enroll([DUMP_HOME], play_store_focused=True)
    assert outcome == "play_store" and not adb.actions


def test_enrollment_without_phone_waits_for_the_technician() -> None:
    outcome, adb, messages = _enroll([DUMP_PHONE_ENTRY] * 1000, phone="", cancel_after=0.2)
    assert outcome == "cancelled"
    assert not [a for a in adb.actions if a[0] == "text"]
    assert "no phone number" in messages.lower()


def test_confirm_never_ends_enrollment() -> None:
    outcome, _, _ = _enroll([DUMP_MFA] * 1000, confirm_after=0.1, cancel_after=0.35)
    assert outcome == "cancelled", "only the gate or Cancel ends Enrollment (ADR-0004)"


def test_sign_in_full_flow() -> None:
    outcome, adb, messages = _sign_in([
        DUMP_ADD_ACCOUNT, DUMP_ACCOUNT_TYPE,
        DUMP_EMAIL_WEBVIEW, DUMP_EMAIL_FILLED,
        DUMP_PASSWORD, DUMP_PASSWORD_FILLED,
        DUMP_MFA, DUMP_MFA,
        DUMP_HOME, DUMP_HOME, DUMP_HOME,
    ])
    assert outcome == "auto"
    assert [a[1] for a in adb.actions if a[0] == "text"] == [EMAIL, PASSWORD]
    assert len([a for a in adb.actions if a[0] == "tap"]) == 4, "2 buttons + 2 fields"
    assert "S3cret" not in messages, "the password is NEVER logged"
    assert "MFA" in messages and "Ajouter un compte" in messages


def test_sms_code_screen_injects_nothing() -> None:
    outcome, adb, messages = _sign_in([DUMP_OTC_CODE, DUMP_OTC_CODE, DUMP_HOME, DUMP_HOME, DUMP_HOME])
    assert outcome == "auto" and not adb.actions
    assert "SMS code" in messages


def test_button_taps_are_capped() -> None:
    outcome, adb, messages = _sign_in([DUMP_ADD_ACCOUNT] * 1000, confirm_after=0.15)
    assert outcome == "manual"
    assert len([a for a in adb.actions if a[0] == "tap"]) == 2
    assert "still showing" in messages


def test_confirm_ends_sign_in() -> None:
    assert _sign_in([DUMP_MFA] * 1000, confirm_after=0.15)[0] == "manual"


def test_already_signed_in() -> None:
    outcome, adb, _ = _sign_in([DUMP_HOME] * 10)
    assert outcome == "auto" and not adb.actions


def test_dump_failures_are_reported() -> None:
    outcome, _, messages = _sign_in([""] * 1000, confirm_after=0.15)
    assert outcome == "manual" and "uiautomator" in messages


class ScriptedAdb(AdbService):
    """AdbService whose _run is scripted: no subprocess."""

    def __init__(self, script) -> None:
        super().__init__(adb_command="adb")
        self.calls: list[list] = []
        self._script = script

    def _run(self, args, timeout=15):
        self.calls.append(list(args))
        return self._script(list(args))


def test_open_app_prefers_am_start() -> None:
    def base(args):
        return (True, "com.x/.Main", "") if "resolve-activity" in args else (True, "", "")

    def succeeds(args):
        return (True, "Starting: Intent", "") if "start" in args else base(args)

    def fails(args):
        if "start" in args:
            return False, "Error: Activity class does not exist", ""
        return (True, "", "") if "monkey" in args else base(args)

    adb = ScriptedAdb(succeeds)
    assert adb.open_app("S", "com.x", 0)[0]
    assert not any("monkey" in c for c in adb.calls)

    adb = ScriptedAdb(fails)
    assert adb.open_app("S", "com.x", 0)[0], "monkey fallback on the primary user"
    assert any("monkey" in c for c in adb.calls)

    adb = ScriptedAdb(fails)
    assert not adb.open_app("S", "com.x", 10)[0]
    assert not any("monkey" in c for c in adb.calls), "no monkey on a Work Profile"
    assert any("--user" in c for c in adb.calls)


def test_is_installed_matches_the_exact_package() -> None:
    adb = ScriptedAdb(lambda args: (True, "package:com.microsoft.teamsbeta", ""))
    assert not adb.is_installed("S", "com.microsoft.teams")
