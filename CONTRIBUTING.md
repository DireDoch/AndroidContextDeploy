# Contributing

Ideas are genuinely welcome, and they do not have to come with code.

This started as one technician's tool for one fleet of phones, which means the
parts that felt obvious to me may well be wrong for you. If your phones need
something mine never did, that is worth an issue — even if it is only a sentence
describing what you do by hand today.

## Things that are always useful

- **A step you still do by hand on every phone.** Say what it is; the how can be
  worked out.
- **A screen the tool does not recognise.** Enrollment and sign-in screens differ
  by manufacturer, Android version, Phone Language and Intune configuration. Run
  with `--diag`, get stuck, and attach the masked `NNN.xml` of that screen. That
  one file is usually the whole fix.
- **A Phone Language.** The detector reads English and French screens. Spanish,
  Portuguese, German… each needs real captured screens, which only someone with
  such a phone can provide.
- **A UI Language.** Copy `locales/en.json` to `locales/<code>.json` and
  translate the values. No code.
- **A place where the Checklist told you nothing useful.** A failure that does
  not name its fix is a bug in this project.
- **Bug reports.** Include the console lines and the phone model.

No contribution is too small, and "I tried this and it did not work" is a
perfectly good contribution.

## Before you write code

Check whether you need code at all. Most of what a company needs is **an app or
an Android setting**, and that is one entry in `deploy.json`:

```json
{ "name": "Slack", "package_id": "com.Slack", "sign_in": true, "pin": true }
```

```json
{ "name": "Stay awake while charging", "namespace": "global",
  "key": "stay_on_while_plugged_in", "value": "3" }
```

Each entry gets a progress line, a sidebar row, a log line and a Checklist row
with a remediation — for free. Write a Module only when `deploy.json` genuinely
cannot express what you need. Chapter 7 of [the manual](docs/manual.pdf) walks
through both, with a Module template to copy.

## Setting up

```bash
git clone https://github.com/DireDoch/AndroidContextDeploy.git
cd AndroidContextDeploy
python -m venv .venv
.venv/bin/pip install -r requirements.txt pytest      # Windows: .venv\Scripts\pip
.venv/bin/python -m pytest
.venv/bin/python main.py                               # add --diag to capture screens
```

Python 3.11 or later, with Tk (`python -m tkinter` opens a window). The tests
need no phone: adb is faked and every screen is a recorded XML dump. CI runs them
on Ubuntu and Windows for every pull request.

## What a change should come with

- **A test.** Fake the phone — see `FakePhone` in `tests/test_modules.py` and
  `FakeAdb` in `tests/test_detection.py`. A test that needs a real phone is a
  test nobody will run.
- **Both languages.** Anything a technician reads goes through `t("key")` and
  lives in `locales/en.json` and `locales/fr.json`. Never hardcode it.
  `tests/test_i18n.py` fails when a key or a placeholder is missing.
- **A remediation, not just an error.** A Result that can fail carries a `remedy`
  naming the fix, ideally the `deploy.json` key. "Not found" helps nobody;
  "assign it in Intune, or remove catalog 'Slack' from deploy.json" does.
- **No personal data, ever.** No real email, password, phone number, company name
  or screenshot of a real account in code, fixtures, issues or docs. Use
  `contoso.com` and `+1 202 555 01xx`.

## House style

- **adb only runs through `AdbService`** (`src/androidcontextdeploy/adb.py`).
  That is what makes the diagnostic capture and the fakes see everything.
- **`ScreenDetector` stays pure parsing.** No adb call in `detection.py`, so every
  captured screen can be replayed as a test.
- **A Module never touches the UI.** It returns Results and reports progress
  through `ctx.runner`; `app.py` decides how that looks.
- **A failure is recorded and the run continues.** The technician needs the whole
  Checklist, not a crash at step two.
- **Enrollment has no timeout, on purpose** ([ADR-0004](docs/adr/0004-enrollment-ends-only-at-the-managed-play-store.md)).
  Do not "fix" that.
- **No adb binary in git.** It ships inside the `adbutils` package; a local one
  can go in `platform-tools/` (gitignored).
- Comments explain *why*, not *what*.

## Pull requests

Fork, branch, keep `python -m pytest` green, and open a PR describing what problem
it solves. Small and focused beats large and complete.

If a change cannot be verified in CI — anything needing a real phone, an Intune
tenant or a particular launcher — say so in the PR and describe what you tested,
on which phone.
