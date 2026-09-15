## What this changes

<!-- What problem does it solve? Link the issue if there is one. -->

## How it was tested

<!-- Which tests cover it. If something cannot be verified in CI - a real phone,
     an Intune tenant, a manufacturer's launcher - say what you tested by hand,
     on which phone model and Android version. -->

- [ ] `python -m pytest` is green
- [ ] Tested on a real phone (model / Android version: )

## Checklist

<!-- Delete what does not apply. -->

- [ ] User-facing text is in **both** `locales/en.json` and `locales/fr.json` (`tests/test_i18n.py` checks this)
- [ ] A failure gives a Result with a `remedy`, not just a log line
- [ ] A new screen comes with a masked XML fixture in `tests/test_detection.py`
- [ ] No password, phone number or real company data in code, fixtures or screenshots
- [ ] New Module appended to `MODULES` in `src/androidcontextdeploy/modules/__init__.py`
- [ ] README or manual updated if behaviour changed
