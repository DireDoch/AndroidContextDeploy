"""Reading the phone's screen (ADR-0002). Pure parsing: no adb call in here, so
every captured dump can be replayed offline as a test fixture.

The keyword tables are the Phone Language support: lowercase fragments, English
and French today. Teaching the tool a new screen or a new Phone Language is
adding fragments here plus a fixture in tests/test_detection.py (manual, ch. 7).
Match short defensive fragments, never a whole sentence.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from androidcontextdeploy.models import ScreenAnalysis, UiField

# ── Sign-in fields and buttons (Microsoft pages, native and WebView) ─────────
_EMAIL_ID_HINTS = ("email", "courriel", "username", "loginfmt", "i0116", "account")
_EMAIL_TEXT_HINTS = ("email", "courriel", "adresse", "phone", "téléphone", "telephone", "skype")
_PASSWORD_ID_HINTS = ("password", "passwd", "pwd", "i0118", "motdepasse", "mot_de_passe")
_PASSWORD_TEXT_HINTS = ("mot de passe", "password")
# One-time code field. Microsoft exposes it as `idTxtBx_SAOTCC_OTC` with a hint
# mentioning "phone" and "SMS" -- it must be recognised BEFORE the email field.
_CODE_FIELD_ID_HINTS = ("otc", "saotcc", "otp", "verificationcode", "otccode")
_CODE_FIELD_TEXT_HINTS = (
    "entrer le code", "entrez le code", "saisir le code", "saisissez le code",
    "enter the code", "enter code", "code de vérification", "code de verification",
    "verification code", "envoyé un sms", "envoye un sms", "sent you a text",
    "code pour vous connecter", "code to sign in", "we texted you",
)
_MFA_KEYWORDS = (
    "approuver la connexion", "approve sign in", "approve sign-in",
    "approuvez la demande", "approve the request",
    "entrez le numéro", "enter the number",
    "vérifiez votre identité", "verify your identity",
    "vérification en deux étapes", "two-step verification",
    "code de vérification", "verification code",
    "authentification multifacteur", "multifactor",
    "notification a été envoyée", "notification was sent",
    "ouvrez votre application authenticator", "open your authenticator app",
)
_LOGIN_KEYWORDS = (
    "se connecter", "sign in", "connexion", "login",
    "entrez votre mot de passe", "enter your password", "enter password",
    "rester connecté", "stay signed in",
)
# Buttons the loop taps to reach the email sign-in. Order = priority.
_ACTION_BUTTON_KEYWORDS = (
    "ajouter un compte", "add account", "add an account",
    "compte professionnel ou scolaire", "work or school account",
    "se connecter avec un autre compte", "utiliser un autre compte", "use another account",
    "se connecter avec microsoft", "sign in with microsoft",
    "se connecter avec une adresse e-mail", "sign in with email", "connexion avec e-mail",
    "se connecter", "sign in", "connexion",
    "commencer", "get started",
    "autoriser", "allow",
    "activer", "enable",
    "suivant", "next",
    "continuer", "continue",
    "accepter", "accept",
    "terminer", "terminé", "termine", "fait", "done", "finish",
    # "Stay signed in?" -> Yes. Last, so it only wins on a Yes/No screen.
    "oui", "yes",
)

# ── Enrollment named screens ──────────────────────────────────────────────────
_SKIP_SETUP_KEYWORDS = (
    "terminer la configuration", "finir la configuration",
    "finish setting up", "finish account setup", "set up your account",
    "configuration du compte",
)
_SKIP_BUTTON_KEYWORDS = ("ignorer", "skip", "plus tard", "later", "pas maintenant", "not now")
_OTHER_METHOD_KEYWORDS = (
    "configurer une autre méthode", "configurer une autre methode",
    "utiliser une autre méthode", "utiliser une autre methode",
    "set up a different method", "use a different method",
    "i want to set up a different", "i want to use a different",
    "another method", "autre méthode", "autre methode",
)
_METHOD_DIALOG_KEYWORDS = (
    "quelle méthode", "quelle methode", "which method",
    "choisir une méthode", "choisir une methode", "choose a method",
    "méthode voulez-vous", "method would you like",
)
_PHONE_OPTION_KEYWORDS = ("téléphone", "telephone", "phone")
_CONFIRM_KEYWORDS = ("confirmer", "confirm")
_SMS_CHECKBOX_KEYWORDS = (
    "code par texto", "code par sms", "un code par texte",
    "envoyez-moi un code", "envoyez moi un code",
    "text me a code", "send me a code", "receive a code by text",
)
_PHONE_FIELD_KEYWORDS = ("téléphone", "telephone", "phone", "numéro", "numero", "mobile", "cellulaire")
_ACCESS_SETUP_KEYWORDS = (
    "configuration de l'accès", "configuration de l'acces",
    "configurons votre appareil", "set up access", "setting up access",
    "activer un profil professionnel", "créer un profil professionnel",
    "creer un profil professionnel", "mettre à jour les paramètres",
    "mettre a jour les parametres", "activer le profil professionnel",
    "create a work profile", "activate your work profile",
)
_CONTINUE_KEYWORDS = ("continuer", "continue", "commencer", "get started", "suivant", "next")
_SIGNOUT_EXCLUDE = (
    "se déconnecter", "se deconnecter", "déconnexion", "deconnexion",
    "sign out", "log out", "logout", "disconnect",
)
_TERMS_KEYWORDS = (
    "termes d'utilisation", "conditions d'utilisation", "conditions générales",
    "conditions generales", "terms of use", "terms and conditions",
)
_ACCEPT_KEYWORDS = ("accepter", "j'accepte", "accept", "i agree", "agree")
# Ownership screen: "<Organization> device" vs "Personal device". The
# Organization's own wording comes from deploy.json.
_OWNERSHIP_SCREEN_KEYWORDS = (
    "personal device", "appareil personnel",
    "à qui appartient", "a qui appartient", "who owns", "owns this device",
)
_PERSONAL_KEYWORDS = ("personnel", "personal")
_FINISH_KEYWORDS = ("terminé", "termine", "terminer", "finish", "done", "fait")
_NEXT_KEYWORDS = ("suivant", "next")
# Enrollment gate, text fallback (the robust signal is the focused package).
_MANAGED_PLAY_STORE_KEYWORDS = (
    "badges", "suggested by", "suggested for you",
    "suggérées par", "suggerees par", "suggérée par", "suggeree par",
)

_BOUNDS_RE = re.compile(r"\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]")
_EDITABLE_CLASS_HINTS = ("edittext", "autocompletetextview")
_PASSWORD_MASK_RE = re.compile(r"^[•·*.]+$")


class ScreenDetector:
    def __init__(self, organization: str = "") -> None:
        self._org = organization.strip().lower()

    def analyze(self, xml_text: str) -> ScreenAnalysis | None:
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return None
        analysis = ScreenAnalysis()
        texts: list[str] = []
        emails: list[UiField] = []
        passwords: list[UiField] = []
        codes: list[UiField] = []
        editable: list[UiField] = []
        clickable: list[UiField] = []

        for node in root.iter("node"):
            text = node.get("text", "") or ""
            desc = node.get("content-desc", "") or ""
            texts += [s.lower() for s in (text, desc) if s]
            node_class = (node.get("class", "") or "").lower()
            if any(h in node_class for h in _EDITABLE_CLASS_HINTS):
                fld = self._build_field(node)
                if fld is None:
                    continue
                editable.append(fld)
                # Code first: its hint says "phone", which would make it an email field.
                if self._is_code_field(fld):
                    codes.append(fld)
                elif fld.is_password or self._matches(fld, _PASSWORD_ID_HINTS, _PASSWORD_TEXT_HINTS):
                    passwords.append(fld)
                elif self._matches(fld, _EMAIL_ID_HINTS, _EMAIL_TEXT_HINTS):
                    emails.append(fld)
            elif (node.get("clickable", "") or "").lower() == "true" and (text or desc):
                button = self._build_field(node)
                if button is not None:
                    clickable.append(button)

        screen_text = " | ".join(texts)
        analysis.login_markers = any(k in screen_text for k in _LOGIN_KEYWORDS)
        analysis.mfa_hint = next((k for k in _MFA_KEYWORDS if k in screen_text), "")
        analysis.mfa_detected = bool(analysis.mfa_hint)

        # Microsoft shows one field at a time: a lone unidentified field on a
        # sign-in screen is the email. Never when a code field is present.
        if (not emails and not passwords and not codes and len(editable) == 1
                and analysis.login_markers and not editable[0].is_password):
            emails.append(editable[0])

        analysis.email_field = self._pick(emails)
        analysis.password_field = self._pick(passwords)
        analysis.otc_field = self._pick(codes)
        analysis.action_button = self._find_clickable(clickable, _ACTION_BUTTON_KEYWORDS)
        if analysis.email_field:
            analysis.email_field.is_empty = self._email_empty(analysis.email_field)
        if analysis.password_field:
            analysis.password_field.is_empty = self._password_empty(analysis.password_field)

        analysis.managed_play_store = any(k in screen_text for k in _MANAGED_PLAY_STORE_KEYWORDS)
        analysis.named_screen, analysis.named_targets = self._detect_named_screen(
            screen_text, clickable, editable)
        seen: set[str] = set()
        for button in clickable:
            label = (button.text or button.content_desc).strip()
            if label and label.lower() not in seen:
                seen.add(label.lower())
                analysis.clickable_labels.append(label)
        return analysis

    def _detect_named_screen(self, screen_text: str, clickable: list[UiField],
                             editable: list[UiField]) -> tuple[str, dict[str, UiField]]:
        """Most specific first; the first match wins. ("", {}) when none."""
        targets: dict[str, UiField] = {}

        # Ownership: the Organization's option, NEVER the personal one.
        org_keys = (f"{self._org} device", f"appareil {self._org}") if self._org else ()
        if any(k in screen_text for k in _OWNERSHIP_SCREEN_KEYWORDS + org_keys):
            if self._org:
                org = self._find_clickable(clickable, (self._org,), exclude=_PERSONAL_KEYWORDS)
                if org:
                    targets["device_org"] = org
            finish = self._find_clickable(clickable, _FINISH_KEYWORDS)
            if finish:
                targets["finish"] = finish
            if targets:
                return "ownership", targets

        if any(k in screen_text for k in _METHOD_DIALOG_KEYWORDS):
            for role, keys in (("phone_option", _PHONE_OPTION_KEYWORDS), ("confirm", _CONFIRM_KEYWORDS)):
                if found := self._find_clickable(clickable, keys):
                    targets[role] = found
            return "method_dialog", targets

        if any(k in screen_text for k in _SMS_CHECKBOX_KEYWORDS):
            if found := self._find_clickable(clickable, _SMS_CHECKBOX_KEYWORDS):
                targets["sms_checkbox"] = found
            if found := self._pick_phone_field(editable):
                targets["phone"] = found
            if found := self._find_clickable(clickable, _NEXT_KEYWORDS):
                targets["next"] = found
            return "phone_entry", targets

        # Authenticator: the "different method" LINK wins over the main Next button.
        if link := self._find_clickable(clickable, _OTHER_METHOD_KEYWORDS):
            return "authenticator_other_method", {"link": link}

        if any(k in screen_text for k in _TERMS_KEYWORDS) and (
                accept := self._find_clickable(clickable, _ACCEPT_KEYWORDS)):
            return "terms", {"accept": accept}

        if any(k in screen_text for k in _ACCESS_SETUP_KEYWORDS) and (
                cont := self._find_clickable(clickable, _CONTINUE_KEYWORDS, exclude=_SIGNOUT_EXCLUDE)):
            return "access_setup", {"continue": cont}

        if any(k in screen_text for k in _SKIP_SETUP_KEYWORDS) and (
                skip := self._find_clickable(clickable, _SKIP_BUTTON_KEYWORDS)):
            return "skip_setup", {"skip": skip}

        return "", {}

    @staticmethod
    def _find_clickable(nodes: list[UiField], keywords: tuple[str, ...],
                        exclude: tuple[str, ...] = ()) -> UiField | None:
        """First node whose label contains a keyword (keyword order = priority)."""
        for keyword in keywords:
            for node in nodes:
                label = f"{node.text} {node.content_desc}".lower()
                if keyword in label and not any(x in label for x in exclude):
                    return node
        return None

    @staticmethod
    def _pick_phone_field(editable: list[UiField]) -> UiField | None:
        for fld in editable:
            identity = f"{fld.resource_id} {fld.content_desc} {fld.hint} {fld.text}".lower()
            if any(h in identity for h in _PHONE_FIELD_KEYWORDS):
                return fld
        return editable[0] if editable else None

    @staticmethod
    def _build_field(node: ET.Element) -> UiField | None:
        match = _BOUNDS_RE.match(node.get("bounds", "") or "")
        if not match:
            return None
        x1, y1, x2, y2 = (int(g) for g in match.groups())
        if x2 <= x1 or y2 <= y1:        # off-screen or collapsed
            return None
        return UiField(
            center_x=(x1 + x2) // 2, center_y=(y1 + y2) // 2,
            text=node.get("text", "") or "",
            resource_id=node.get("resource-id", "") or "",
            content_desc=node.get("content-desc", "") or "",
            hint=node.get("hint", "") or "",
            is_password=(node.get("password", "") or "").lower() == "true",
            focused=(node.get("focused", "") or "").lower() == "true")

    @staticmethod
    def _is_code_field(fld: UiField) -> bool:
        identity = f"{fld.resource_id} {fld.content_desc} {fld.hint} {fld.text}".lower()
        return any(h in identity for h in _CODE_FIELD_ID_HINTS + _CODE_FIELD_TEXT_HINTS)

    @staticmethod
    def _matches(fld: UiField, id_hints: tuple[str, ...], text_hints: tuple[str, ...]) -> bool:
        identity = f"{fld.resource_id} {fld.content_desc} {fld.hint}".lower()
        if any(h in identity for h in id_hints):
            return True
        # In a WebView the placeholder shows up as the field's text.
        text = fld.text.lower()
        return "@" not in text and any(h in text for h in text_hints)

    @staticmethod
    def _pick(candidates: list[UiField]) -> UiField | None:
        return next((f for f in candidates if f.focused), candidates[0] if candidates else None)

    @staticmethod
    def _email_empty(fld: UiField) -> bool:
        text = fld.text.strip().lower()
        # A WebView placeholder ("Email, phone, or Skype") still means empty.
        return not text or ("@" not in text and any(h in text for h in _EMAIL_TEXT_HINTS))

    @staticmethod
    def _password_empty(fld: UiField) -> bool:
        text = fld.text.strip()
        if not text:
            return True
        if _PASSWORD_MASK_RE.match(text):    # mask dots: already typed
            return False
        return any(h in text.lower() for h in _PASSWORD_TEXT_HINTS)


def screen_signature(screen: ScreenAnalysis) -> str:
    """Content identity of a screen, to log and capture each screen once. The
    focused window is often null during transitions; the content is not."""
    action = ""
    if screen.action_button:
        action = (screen.action_button.text or screen.action_button.content_desc).strip()
    return "|".join([
        screen.named_screen,
        "mfa" if screen.mfa_detected else "",
        "otc" if screen.otc_field else "",
        "email" if screen.email_field and screen.email_field.is_empty else "",
        "pwd" if screen.password_field and screen.password_field.is_empty else "",
        action,
        "login" if screen.login_markers else "",
        "store" if screen.managed_play_store else "",
        "·".join(screen.clickable_labels[:6]),
    ])
