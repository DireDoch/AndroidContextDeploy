# A desktop tool driven over ADB, with no companion app on the phone

The project once had two directions: an Android app built with Chaquopy, and a
Python desktop tool. Decision (2026-06-12): the product is **the desktop tool
only**. The phone is driven 100% over ADB from the technician's computer —
screen detection, credential Injection and the interactive Mirror included. No
app is developed for, or installed on, the phone. That rules out
MediaProjection and AccessibilityService on the device.

## Considered Options

- Desktop tool plus an Android companion app (MediaProjection) — rejected: two
  codebases, an app to deploy on every phone, and maintenance out of proportion
  for a workbench tool.
- A full Android app with Chaquopy — rejected: throws away working code and
  makes the technician's side harder, not easier.

## Consequences

- Every future capability — screen detection, mirroring — must be achievable
  with ADB alone.
