```
   _           _         _    _  ___         _           _   ___           _
  /_\  _ _  __| |_ _ ___(_)__| |/ __|___ _ _| |_ _____ _| |_|   \ ___ _ __| |___ _  _
 / _ \| ' \/ _` | '_/ _ \ / _` | (__/ _ \ ' \  _/ -_) \ /  _| |) / -_) '_ \ / _ \ || |
/_/ \_\_||_\__,_|_| \___/_\__,_|\___\___/_||_\__\___/_\_\\__|___/\___| .__/_\___/\_, |
                                                                     |_|         |__/
```

<div align="center">

# AndroidContextDeploy

**Phone preparation, Intune enrollment and quick device diagnostics for Android**

[![Tests](https://github.com/DireDoch/AndroidContextDeploy/actions/workflows/tests.yml/badge.svg)](https://github.com/DireDoch/AndroidContextDeploy/actions/workflows/tests.yml)
[![Manual](https://img.shields.io/badge/manual-PDF-1f4e79)](docs/manual.pdf)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

</div>

---

## Where this comes from

This is a spin-off of a tool I wrote on the job as an IT technician, where
company phones were handed to employees week after week — each one needing the
same Intune enrollment, the same Microsoft apps, the same sign-ins, and the same
settings nobody remembers to change until the battery is flat by noon.

None of it is hard. All of it is slow: a phone is fifteen screens of Company
Portal enrollment, four apps to find in the managed Play Store, four sign-ins with
an address typed on a tiny keyboard, an SMS code that arrives on somebody else's
phone, and icons to drag to the home screen. Miss one and nobody finds out until
the employee calls.

The tool never took the technician out of the loop — Android does not allow it,
and MFA should not. What it changed is that the phone sits on the desk plugged
into a computer, mirrored in a window, while the tool types the credentials,
taps through the screens it knows, waits patiently on the ones it must not
touch, and finishes with a **checklist of what was done and what is still left
by hand**.

AndroidContextDeploy is that idea, rebuilt in the open: the company-specific
parts moved out into a manifest you edit, the screens it recognises covered by
tests replayed from real captures, and the whole thing documented well enough
that somebody who has never touched ADB can extend it.

> 📖 **[Read the manual (PDF)](docs/manual.pdf)** — what the tool does, what it
> leaves to you, how the pieces fit together, and how to extend it.
> Source in [`docs/manual.typ`](docs/manual.typ), built with
> [Typst](https://typst.app/).

![The main window: the Session form, the Modules, the console and the Mirror](docs/images/interface.png)

## What it does

A technician plugs a phone in with USB debugging on, types the employee's email
and password, and runs three **Modules** in order:

| Module | What it does |
|---|---|
| **Device settings** | Applies every Android setting listed in `deploy.json` (screen timeout, brightness…) and reads each one back from the phone. |
| **Applications** | Enrolls the phone with the **Company Portal** (which creates the Work Profile), then brings each ticked app from the managed Play Store, signs it in and pins it to the home screen. |
| **Final check** | Confirms the Work Profile and the apps are there, and shows the **Checklist**. |

While it works, the phone is **mirrored live** in the window: you see every
screen, and your clicks are sent to the phone as touches. Nothing is installed on
the phone.

> [!WARNING]
> The tool drives a phone with an employee's credentials. Read
> [SECURITY.md](SECURITY.md) and `deploy.json` before the first real phone.

### What stays with you

ADB is powerful, not almighty, and some steps belong to a human on purpose:

- **Opening a Work Profile app.** Android Enterprise refuses to let ADB launch it.
  The tool shows *ACTION REQUIRED — open Microsoft Teams*; you tap the icon in the
  Mirror, and from the sign-in screen on, it types the email and password itself.
- **MFA.** Approving a sign-in or typing an SMS code is the employee's. The tool
  waits — Enrollment waits forever, by design, until the managed Play Store shows.
- **Lockdown.** Turning USB debugging off is irreversible at the desk, so it is a
  button you press, never a step that runs.

### The Checklist at the end

Every Result from every Module, in the order it ran, with the fix when something
needs one:

![The Checklist: every Result, with what is left by hand](docs/images/checklist-card.png)

`OK`, `WARNING` and `ERROR` speak for themselves. `MANUAL` is yours to do;
`N/A` does not apply to this phone, so its absence is correct rather than a
problem.

## Requirements

- **To run a release:** Windows 10/11 or a Linux desktop. Nothing to install —
  adb ships inside.
- **To run from source:** Python 3.11+ with Tk, then
  `pip install -r requirements.txt`.
- **The phone:** Android with *USB debugging* on and this computer allowed.
- **For Enrollment:** a Microsoft Intune tenant, with the apps assigned to the
  employee.

## Usage

Download the zip (Windows) or tarball (Linux) from
[Releases](https://github.com/DireDoch/AndroidContextDeploy/releases), unpack it,
and run `AndroidContextDeploy.exe` / `./AndroidContextDeploy`.

Or from a clone:

```bash
pip install -r requirements.txt
python main.py
```

| Option | Effect |
|---|---|
| *(none)* | Normal run. Nothing is written to disk. |
| `--lang fr` | Force the UI Language (`en`, `fr`, or any file in `locales/`). Defaults to `deploy.json`, then the system locale. |
| `--diag` | Capture every screen (XML + PNG) and every adb command to `diag/`, password and phone number masked. For teaching the tool a new screen. |

`adb` is looked up in this order: the `ADB_COMMAND` environment variable,
`platform-tools/` next to the tool, `adb` on your `PATH`, then the copy bundled
with the `adbutils` package.

## Configuration

Everything company-specific lives in `deploy.json`, next to the executable.
Editing it never needs a rebuild.

```json
{
  "organization": "Contoso",
  "language": "auto",
  "device_settings": [
    { "name": "Screen timeout: 10 minutes", "namespace": "system",
      "key": "screen_off_timeout", "value": "600000" }
  ],
  "catalog": [
    { "name": "Company Portal", "package_id": "com.microsoft.windowsintune.companyportal",
      "enrollment": true, "sign_in": true, "pin": true },
    { "name": "Microsoft Teams", "package_id": "com.microsoft.teams",
      "sign_in": true, "pin": true },
    { "name": "Microsoft Edge", "package_id": "com.microsoft.emmx", "selected": false }
  ]
}
```

| Key | Meaning |
|---|---|
| `organization` | Your company as its name appears on the phone's ownership screen ("*Contoso* device"). Enrollment taps that option, never "Personal". |
| `language` | UI Language: `auto`, `en`, `fr`… |
| `device_settings[]` | `name` shown to the technician, and an Android `settings put <namespace> <key> <value>`. `namespace` is `system`, `secure` or `global`. |
| `catalog[]` | The apps, in the order they are set up. `package_id` is the Play Store id. |
| `catalog[].enrollment` | The Company Portal. At most one, and it must come first. |
| `catalog[].sign_in` | Run the Detection Loop and type the credentials. |
| `catalog[].pin` | Put a shortcut on the home screen. |
| `catalog[].selected` | Ticked by default (default `true`). |

A mistake in the file is reported on start with the key to fix, before anything
touches a phone.

## Branding

The startup banner is read from `banner.txt`. To use your own, generate ASCII
art at [patorjk.com/software/taag](https://patorjk.com/software/taag/) and paste
it in. Delete the file and the plain name is shown instead.

## Languages

There are two different languages, and they are not the same thing:

- **UI Language** — what the technician reads. English and French ship; adding
  one is copying `locales/en.json` to `locales/<code>.json` and translating the
  values. No code, no rebuild.
- **Phone Language** — what the phone's own screens are in. The detector
  recognises **English and French** screens. Another language needs keywords
  proven by real captured screens: see [CONTRIBUTING.md](CONTRIBUTING.md).

## Tests

```bash
pip install pytest
python -m pytest
```

No phone needed: adb is faked and every screen is a recorded, masked XML dump.
Every pull request runs the suite on Ubuntu and Windows, and compiles
`docs/manual.typ` so the manual cannot rot while nobody rebuilds it.

## Building

```bash
pip install pyinstaller
python build.py 1.0.0
```

Produces `dist/AndroidContextDeploy/` and an archive. Pushing a `v*` tag builds
both the Windows and the Linux bundle on GitHub Actions and attaches them to the
release.

## Structure

```
deploy.json                      <- apps, settings, organization (edit this)
banner.txt                       <- startup banner (editable)
locales/                         <- UI Languages: en.json, fr.json
main.py                          <- entry point (--diag, --lang)
build.py                         <- PyInstaller bundle
scrcpy_server/                   <- scrcpy-server jar for the Mirror (Apache-2.0)
src/androidcontextdeploy/
  app.py                         <- the window: Session, queues, wiring
  runner.py                      <- runs a Module off the UI thread, keeps Results
  modules/                       <- device_settings, applications, final_check
  adb.py                         <- the only place that runs adb
  detection.py                   <- reads a screen dump (pure parsing)
  signin.py                      <- the Detection Loop and Enrollment
  mirror_service.py              <- the scrcpy client
  diagnostics.py                 <- --diag capture, masked
  manifest.py / i18n.py / models.py
  ui/                            <- passive CustomTkinter panels
tests/                           <- pytest, no phone needed
docs/
  manual.typ / manual.pdf        <- the manual
  adr/                           <- why things are the way they are
```

## Documentation

- **[The manual (PDF)](docs/manual.pdf)** — what the tool does, what it leaves to
  you, the architecture in diagrams, ADB and the other technologies explained
  simply, Enrollment in depth, how to extend it, and troubleshooting.
  Rebuild it with `typst compile docs/manual.typ`.
- **[docs/adr/](docs/adr/)** — the decisions a newcomer would otherwise try to
  "fix": no app on the phone, no timeout on Enrollment, no OCR.
- **[CONTEXT.md](CONTEXT.md)** — the vocabulary: Module, Result, Work Profile,
  Enrollment, Manual Action…

## Contributing

**Ideas are genuinely welcome, and they do not have to come with code.**

This started as one technician's tool for one fleet, so the parts that felt
obvious to me may well be wrong for you. If your phones need something mine
never did, that is worth an issue — even if it is only a sentence describing
what you do by hand today.

Always useful: a step you still do by hand, a screen the tool does not recognise
(run with `--diag` and attach the masked XML), a Phone Language or UI Language, a
place where the Checklist told you nothing useful, or a plain bug report.

No contribution is too small, and "I tried this and it did not work" is a
perfectly good contribution.

See **[CONTRIBUTING.md](CONTRIBUTING.md)** for how to set up, what a change
should come with, and the house style — plus [SECURITY.md](SECURITY.md) if you
have found something that should not be reported in public.

## License

MIT — see [LICENSE](LICENSE). Do what you like with it.
`scrcpy_server/scrcpy-server-v3.3.4.jar` is from
[scrcpy](https://github.com/Genymobile/scrcpy), Apache-2.0 — see
[scrcpy_server/LICENSE](scrcpy_server/LICENSE).
