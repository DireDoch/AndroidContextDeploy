# Security policy

## What this tool does to a phone

AndroidContextDeploy is worth being careful with, because it drives a phone over
USB debugging with an employee's credentials in hand:

- It **types the employee's email, password and, optionally, personal phone
  number** into the phone with `adb shell input text`.
- It **changes Android settings** listed in `deploy.json` with `settings put`.
- It **pushes `scrcpy-server`** to `/data/local/tmp` to mirror the screen and
  send touches. Nothing is installed as an app.
- It **taps buttons** on sign-in and Enrollment screens it recognises.
- **Lockdown** hides Developer options and turns USB debugging off.

## What it does with credentials

The email, password and phone number live **in memory only** for the Session.
They are never written to disk, never logged — the password and phone number are
masked even in the diagnostic capture — and they are gone when the window closes.

## The diagnostic capture holds personal data

`--diag` writes every screen the tool sees to `diag/`: raw XML, a PNG and an ADB
log. The password and phone number are masked in the text files, but **a PNG
can show personal data in pixels**. `diag/` is gitignored and never sent
anywhere. Review it before you share any part of it; share the masked XML, not
the PNGs.

## The manifest is trusted input

Every key in `deploy.json` ends up in an `adb shell` command on a phone:
`device_settings` go straight to `settings put`, including the `global`
namespace. **Treat the manifest as trusted input.** Do not run a manifest you did
not write or review.

## Reporting a vulnerability

If you find something that could be used to harm a phone, leak a credential or
expose a user, please report it privately rather than opening a public issue:

- Use GitHub's [private vulnerability
  reporting](https://github.com/DireDoch/AndroidContextDeploy/security/advisories/new)
  on this repository.

Please include what an attacker could achieve, and the smallest set of steps that
shows it. I maintain this in my own time, so I cannot promise a response window,
but I will acknowledge what I receive and credit you in the fix unless you prefer
otherwise.

## Supported versions

This project has no release branches. Fixes land on `main`; use the latest
release or commit.
