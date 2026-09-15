# Screens are fixed from captured ground truth (XML + PNG + ADB log), never from a prose description

Each screen met by the automation used to be fixed from a technician's
**description in prose**: the developer turned it into keywords and tap logic
without ever seeing the real `uiautomator` dump. When a phone got stuck on the
"set up access" screen, nobody could tell which cause it was — the dump failing,
a button not `clickable`, wrong bounds, text inside a WebView — and a repaired
screen could silently break again on the next commit.

Decision (2026-06-17): the tool carries a **diagnostic recorder**. Hooked into
the single point `AdbService._run`, it logs **every ADB command and its raw
output** to `adb.log`, and on **every screen change** in the Detection Loops it
saves the **raw XML**, a **PNG screenshot** and a `trace.jsonl` line with the
`ScreenDetector` verdict and the action taken. Everything goes to
`diag/session_<timestamp>/`, which is gitignored.

Two non-negotiable safeguards, from "Session data lives in memory, never on
disk":
- **Masking**: any string equal to the Session password or phone number is
  replaced *before* anything is written (adb.log, trace, XML). The email stays
  readable: it is not a secret and it helps diagnosis.
- **Local versus git**: `diag/` — including PNGs that show the phone number in
  pixels — stays local. Only **masked XML fixtures** enter git, in `tests/`, each
  with an offline `ScreenDetector` test that locks the recognition of that real
  screen.

Amendment (open-source release, 2026-09): the capture is **off by default** and
enabled with `--diag`. A company downloading the tool must not write screenshots
of its employees to disk without asking for it.

## Considered Options

- **Keep coding from prose** — rejected: it is the direct cause of the
  describe → guess keywords → break on the next screen loop.
- **A "capture now" button** — rejected as the main trigger: the bugs are
  *sequence* bugs; by the time the technician notices, the faulty screen is gone.
- **Log ADB commands in clear** — rejected: `input text` carries the password and
  the phone number.
- **Capture without turning captures into tests** — rejected: a fixed screen
  stays breakable by a later commit.

## Consequences

- Debugging becomes asynchronous and data-driven: a technician runs a real
  session with `--diag`, a contributor reads the XML and the trace.
- `AdbService._run` is the single instrumentation point: nothing escapes it.
- `ScreenDetector` stays pure parsing, so every captured XML replays offline.
