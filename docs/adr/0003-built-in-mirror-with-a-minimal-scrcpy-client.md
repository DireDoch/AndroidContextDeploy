# A built-in Mirror with a minimal scrcpy client

The technician must see and control the phone's screen inside the tool, the way
Android Studio mirrors a device. Decision (2026-06-12): embed the scrcpy stream
in a panel of the CustomTkinter window — H.264 decoded in Python, drawn in the
UI, clicks turned into touches. scrcpy pushes a temporary server to
`/data/local/tmp`; no APK is installed, per ADR-0001.

Amendment (2026-06-12, implementation): the PyPI package `py-scrcpy-client`
chosen at first was dropped — it bundles scrcpy-server v1.24 (2022), which
crashes on Android 14+ (`SurfaceControl.createDisplay` removed), and its pinned
dependencies have no wheels for current Python. Instead, `mirror_service.py`
(~200 lines) pushes the official `scrcpy-server-v3.3.4.jar`, started with
`raw_stream=true`: the video socket carries raw H.264 decoded with PyAV, a
second socket carries touches (scrcpy v3 control protocol, generic finger
pointer).

## Considered Options

- MediaProjection — excluded by ADR-0001 (needs an app on the phone).
- scrcpy in its own window — rejected: no development, but not integrated; two
  windows to juggle.
- Re-parenting the scrcpy window (Win32 `SetParent`) — rejected: fragile focus
  and resizing, and Windows-only.
- `py-scrcpy-client` — chosen, then dropped (see the amendment).

## Consequences

- Dependencies: `adbutils` (push and sockets), `av` (H.264), `numpy` (frames).
- The jar lives in `scrcpy_server/` with its Apache-2.0 licence. The version
  string in `mirror_service.py` must match the jar's file name exactly.
- Rendering in Tk tops out around 25 fps (`after(40)`); enough at a workbench.
