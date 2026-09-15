# Changelog

Notable changes to this project. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/).

## [Unreleased] — 1.0.0

### Added

- An installable package: `pip install -r requirements.txt -e .` and the
  `androidcontextdeploy` command. `requirements.txt` pins the exact versions CI
  and releases are built with; Dependabot proposes updates every week
  ([ADR-0006](docs/adr/0006-an-installable-package-with-a-pinned-lock.md)).
- Releases publish `SHA256SUMS.txt` and a build provenance attestation, checked
  with `gh attestation verify`.
- An optional `activity` per catalog app in `deploy.json`, replacing the
  launcher activities that were hard-coded for the Microsoft apps.
- CI runs ruff, mypy, and the tests with at least 80 % coverage, including tests
  that open the real window under Xvfb.

### Fixed

- Mirror taps landed up to 334 px off target, depending on the display scaling.
- An unplug that reset the video connection left the Mirror frozen on its last
  frame without a word in the console.
- A literal `%s` in a password was typed as a space.
- A value with accents was reported as typed although Android typed nothing. The
  technician is now asked to type it in the Mirror, and the Checklist notes it.

### Security

- Credentials reach the phone on `adb shell`'s standard input, no longer as
  command-line arguments visible in the computer's process list.

### Changed

- Sample names are generic: Example Corp and example.com.
- The README and the manual cover installing and launching on Windows, Linux
  (udev rules, glibc) and from source.
