# Sign-in screens are recognised from `uiautomator dump`, not OCR

Blind credential Injection (fixed delays plus the Enter key) broke because the
order and number of fields change from one app to another. Decision
(2026-06-12): a Detection Loop reads the phone's UI tree with
`adb shell uiautomator dump` — class, hint, focus and bounds of every node — and
only types a credential once the matching field is visible and empty. Nothing is
installed on the phone, per ADR-0001.

## Considered Options

- Screenshot plus OCR (the first idea) — rejected as the main mechanism: fragile
  across themes, languages and fonts, slow, and it gives no reliable field
  coordinates. Kept as a documented fallback for a screen that would be invisible
  to the accessibility tree.
- `uiautomator2` (an agent APK on the phone) — rejected: faster reads (~100 ms
  instead of 1–2 s) but it installs an agent on the device, against ADR-0001.
  Revisit only if dump latency becomes a real problem at the workbench.

## Consequences

- Recognition lives in keyword tables. A new manufacturer, Android version or
  Phone Language means new keyword fragments, proven by a recorded dump in the
  tests (see ADR-0005).
