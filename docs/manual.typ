// AndroidContextDeploy manual.
//
// Build with:  typst compile docs/manual.typ
//
// Diagrams are CeTZ and console output is styled text, so they cannot drift
// from the source. Screenshots live in docs/images/.

#import "@preview/cetz:0.3.4"
#import cetz.draw as d

// ---------------------------------------------------------------------------
// Palette and page setup
// ---------------------------------------------------------------------------

#let accent = rgb("#1f6a4a")
#let accentDark = rgb("#143f2d")
#let accentLight = rgb("#e6f3ec")
#let grey = rgb("#5a6472")
#let greyLight = rgb("#f0f2f5")
#let okGreen = rgb("#2e7d32")
#let warnOrange = rgb("#b26a00")
#let warnBox = rgb("#fff6e5")
#let errRed = rgb("#c62828")

#set document(title: "AndroidContextDeploy - Manual", author: "AndroidContextDeploy")
#set page(paper: "a4", margin: (x: 2.2cm, y: 2.4cm), numbering: "1", number-align: center)
#set text(font: ("Libertinus Serif", "DejaVu Serif"), size: 10.5pt, lang: "en")
#set par(justify: true, leading: 0.65em)
#show link: it => text(fill: accent, it)

#set heading(numbering: "1.1")
#show heading.where(level: 1): it => {
  pagebreak(weak: true)
  block(width: 100%, inset: (bottom: 8pt), stroke: (bottom: 1.2pt + accent))[
    #text(fill: grey, size: 9pt, weight: "bold", tracking: 1pt)[
      CHAPTER #counter(heading).display("1")
    ]
    #linebreak()
    #text(fill: accentDark, size: 20pt, weight: "bold")[#it.body]
  ]
  v(6pt)
}
#show heading.where(level: 2): it => {
  v(8pt)
  text(fill: accent, size: 13pt, weight: "bold")[#it]
  v(2pt)
}
#show heading.where(level: 3): it => {
  v(6pt)
  text(fill: accentDark, size: 11pt, weight: "bold")[#it]
  v(1pt)
}

#show raw.where(block: false): it => box(
  fill: greyLight, inset: (x: 3pt, y: 0pt), outset: (y: 3pt), radius: 2pt,
  text(font: ("DejaVu Sans Mono",), size: 9pt, it),
)
#show raw.where(block: true): it => block(
  fill: greyLight, inset: 9pt, radius: 3pt, width: 100%,
  stroke: (left: 2pt + accent),
  text(font: ("DejaVu Sans Mono",), size: 8.5pt, it),
)
#show figure.caption: it => text(size: 9pt, fill: grey, it)

// ---------------------------------------------------------------------------
// Callouts, console, screenshots
// ---------------------------------------------------------------------------

#let callout(title, body, fill: accentLight, stroke: accent) = block(
  width: 100%, fill: fill, radius: 3pt, inset: 9pt, stroke: (left: 2.5pt + stroke),
)[
  #text(weight: "bold", fill: stroke, size: 9.5pt)[#title] \
  #body
]
#let tip(body) = callout("TIP", body)
#let warn(body) = callout("CAUTION", body, fill: warnBox, stroke: warnOrange)
#let note(body) = callout("NOTE", body, fill: greyLight, stroke: grey)

#let cFg = rgb("#dcdcdc")
#let cGreen = rgb("#8fd6a8")
#let cYellow = rgb("#e0a040")
#let cRed = rgb("#f26d6d")
#let cDim = rgb("#9a9a9a")
#let cline(s, fill: cFg) = text(fill: fill, s.replace(" ", "\u{00A0}"))
#let console(..lines, size: 7.6pt) = block(
  width: 100%, fill: rgb("#111412"), radius: 3pt, inset: 9pt,
  {
    set par(justify: false, leading: 0.6em)
    text(font: ("DejaVu Sans Mono",), size: size, fill: cFg, lines.pos().join(linebreak()))
  },
)

#let shot(file, caption, width: 100%) = figure(
  block(stroke: 0.6pt + grey, radius: 2pt, clip: true, image("images/" + file, width: width)),
  caption: caption,
)

// ---------------------------------------------------------------------------
// CeTZ helpers
// ---------------------------------------------------------------------------

#let dnode(pos, body, w: 4.2, h: 0.9, fill: accentLight, stroke: accent) = {
  let (x, y) = pos
  d.rect((x - w / 2, y - h / 2), (x + w / 2, y + h / 2), radius: 0.12, fill: fill, stroke: 0.9pt + stroke)
  d.content((x, y), body)
}
#let arrow(from, to, colour: accent, ..args) = d.line(from, to,
  mark: (end: "stealth", fill: colour), stroke: 0.9pt + colour, ..args)
#let dlabel(pos, body, size: 7pt, fill: grey) = d.content(pos, text(size: size, fill: fill, body))
#let small(body) = text(size: 7.5pt, fill: grey, body)

// ---------------------------------------------------------------------------
// Title page
// ---------------------------------------------------------------------------

#page(numbering: none)[
  #v(4.2cm)
  #align(center)[
    #text(size: 32pt, weight: "bold", fill: accentDark)[AndroidContextDeploy]
    #v(4pt)
    #text(size: 13pt, fill: grey)[Phone preparation, Intune enrollment and quick device diagnostics]
    #v(1.2cm)
    #line(length: 45%, stroke: 1pt + accent)
    #v(1.2cm)
    #text(size: 11pt, fill: grey)[
      Technician's manual \
      #v(2pt)
      What the tool does, what it leaves to you, \
      and how to extend it
    ]
    #v(1.4cm)
    #block(width: 78%, stroke: 0.6pt + grey, radius: 2pt, clip: true,
      image("images/interface.png", width: 100%))
  ]
  #v(1fr)
  #align(center)[
    #text(size: 9pt, fill: grey)[Built with Typst from `docs/manual.typ` · MIT licence]
  ]
]

#page(numbering: none)[
  #text(size: 16pt, weight: "bold", fill: accentDark)[Contents]
  #v(8pt)
  #outline(title: none, depth: 2, indent: 1.2em)
]

#counter(page).update(1)

= Introduction

== Why this tool exists

A company phone straight out of the box is not a finished phone. Before an
employee can use it, somebody has to enroll it with the Company Portal, let
Intune create the Work Profile, find four or five apps in the managed Play Store,
sign each of them in with an address typed on a tiny keyboard, wait for an SMS
code that arrives on the employee's own phone, drag icons to the home screen and
change the settings nobody remembers until the battery is flat by noon.

None of that is hard. It is slow, it is the same on every phone, and it is easy to
get slightly wrong: the fifth phone of the day gets a different treatment from
the first, and nobody can say afterwards which apps were actually signed in.

AndroidContextDeploy is the answer to that. The phone sits on the desk, plugged
into a computer and *mirrored* in a window. The tool applies the settings, walks
the Enrollment screens it knows, types the credentials wherever a sign-in field
appears, waits patiently on the screens it must not touch, and ends with a
*Checklist* of what was done and what is still left by hand.

#warn[
  It does not take the technician out of the loop, and it is not meant to.
  Android Enterprise forbids some actions over ADB, and multi-factor
  authentication belongs to the employee. The tool does everything around those
  moments, and tells you clearly when one has arrived.
]

== The ways to launch it

#v(0.2cm)
#align(center)[
  #set text(size: 8.5pt)
  #cetz.canvas({
    dnode((0, 0), box(width: 12.4cm)[
      #text(font: ("DejaVu Sans Mono",), size: 8.5pt, weight: "bold")[AndroidContextDeploy.exe] #h(1fr)
      #text(size: 8pt)[Windows release: unzip, double-click]], w: 13.4, h: 1.0)
    dnode((0, -1.25), box(width: 12.4cm)[
      #text(font: ("DejaVu Sans Mono",), size: 8.5pt, weight: "bold")[./AndroidContextDeploy] #h(1fr)
      #text(size: 8pt)[Linux release: untar, run]], w: 13.4, h: 1.0, fill: greyLight, stroke: grey)
    dnode((0, -2.5), box(width: 12.4cm)[
      #text(font: ("DejaVu Sans Mono",), size: 8.5pt, weight: "bold")[python main.py] #h(1fr)
      #text(size: 8pt)[From a clone, for development]], w: 13.4, h: 1.0, fill: warnBox, stroke: warnOrange)
  })
]
#v(0.2cm)

*The releases* are the normal way for a technician. They are built by GitHub
Actions for every tagged version and carry everything, `adb` included: nothing to
install. `deploy.json`, `banner.txt` and `locales/` sit next to the executable
and can be edited without rebuilding.

*From source* is for development: `pip install -r requirements.txt`, then
`python main.py`. It needs Python 3.11 or later with Tk.

Every form accepts two options:

#table(
  columns: (auto, 1fr), stroke: none, inset: (x: 4pt, y: 5pt),
  fill: (_, row) => if calc.odd(row) { greyLight },
  [`--lang fr`], [Force the UI Language. Without it: `language` in `deploy.json`, then the system locale.],
  [`--diag`], [Capture every screen and every `adb` command to `diag/`, password and phone number masked. Chapter 7 explains what it is for.],
)

== What this manual covers

- *Chapter 2* — running the tool, and every feature it offers.
- *Chapter 3* — what it deliberately leaves to you.
- *Chapter 4* — how the project is put together, in diagrams.
- *Chapter 5* — the technologies it stands on, explained simply.
- *Chapter 6* — Enrollment, the hardest part, in depth.
- *Chapter 7* — extending it: an app, a setting, a language, a screen, a Module.
- *Chapter 8* — reading the Checklist and the console when something goes wrong.

= Quick start and every feature

== Before you run it

#table(
  columns: (auto, 1fr), stroke: none, inset: (x: 4pt, y: 5pt),
  fill: (_, row) => if calc.odd(row) { greyLight },
  [*Computer*], [Windows 10/11 or a Linux desktop, one free USB port.],
  [*Phone*], [Android, with *USB debugging* on and this computer allowed.],
  [*Intune*], [A tenant where the apps of the Catalog are *assigned* to the employee. The tool never talks to Intune; the phone does.],
  [*The manifest*], [`deploy.json` names *your* Organization, apps and settings. The shipped file is a generic Microsoft example for "Contoso".],
  [*The employee*], [Nearby, with their own phone, for MFA.],
)

== Connecting the phone

The Mirror panel shows the three steps as long as no phone is plugged in:

+ *Settings → About phone → Software information:* tap *Build number* seven
  times. Developer options appear.
+ *Settings → Developer options:* turn on *USB debugging*.
+ Plug the cable in and tap *Allow* on the phone.

Within four seconds the device card turns green, the model, serial and battery
appear, and the phone's screen shows up live in the Mirror.

== The window at a glance

#shot("interface.png", [The window before a Session: device card and Modules on the left, the Session
form and the console in the centre, the Mirror on the right.])

#table(
  columns: (auto, 1fr), stroke: none, inset: (x: 4pt, y: 4pt),
  fill: (_, row) => if calc.odd(row) { greyLight },
  [*Left rail*], [Banner, device card (state, model, serial, battery, Work Profile user), Session summary, and the Modules with their progress.],
  [*Centre*], [The Session form, then one card per Module, then the Checklist. Below: the console.],
  [*Right*], [The Mirror. Clicks and drags on it are touches on the phone.],
)

== Starting a Session

#grid(columns: (1fr, 1fr), gutter: 12pt,
  shot("session-form.png", [The Session form.]),
  [
    #v(0.4cm)
    Type the employee's *work email* and *password*. The *personal phone* is
    optional: when given, Enrollment types it on the SMS MFA screen; when not,
    that screen becomes a Manual Action.

    These three values live *in memory only*. They are never written to disk,
    never logged, and they are gone when the window closes or a new Session
    starts.

    The title names the Organization from `deploy.json`, so a technician can see
    at a glance which manifest is loaded.
  ],
)

== The Modules

A Session runs three *Modules* in order. Each has its own card with a run button;
the sidebar ticks each one off, green when everything went well, orange when a
Result needs a look.

=== Device settings

Applies every entry of `device_settings` with `settings put`, then *reads each
one back*. A setting only counts as OK when the phone reports the expected value:
some manufacturers silently ignore a key, and the Checklist should say so rather
than pretend.

#console(
  cline("[22:10:59] [OK] Screen timeout: 10 minutes: confirmed on the phone.", fill: cGreen),
  cline("[22:10:59] [OK] Manual brightness: confirmed on the phone.", fill: cGreen),
  cline("[22:10:59] [WARN] Brightness level: system/screen_brightness: phone reports 102, expected 160", fill: cYellow),
)

=== Applications

#shot("applications-card.png", [The Applications card: tick the apps for this phone. The order is the order of the Catalog.])

For each ticked app, four steps:

+ *Store.* Its page opens in the managed Play Store, unless Intune already pushed it.
+ *Installed.* The tool waits, up to five minutes, until the app exists in the Work Profile.
+ *Sign-in.* The Company Portal goes through Enrollment (chapter 6); every other
  app goes through the Detection Loop: it reads the screen, types the email and
  password into the right fields, taps *Next* or *Add account*, waits for MFA.
+ *Pinned.* A shortcut goes on the home screen.

The first app is always the Company Portal: its Enrollment creates the Work
Profile the others live in.

=== Manual Action, Confirm and Cancel

#shot("applications-running.png", [Mid-run: Teams needs to be opened by hand. The banner says so, the sidebar
marks it orange, and Confirm is available.])

Android Enterprise does not let ADB open an app inside the Work Profile. When that
happens the card shows an orange *ACTION REQUIRED* banner naming the app: tap its
icon in the Mirror. The tool is already watching; as soon as a sign-in field
appears it types into it.

*Confirm* ends a sign-in loop that is stuck on a screen the tool does not know.
*Cancel the session* is the only way to stop Enrollment (chapter 6).

=== Injection

#grid(columns: (1.05fr, 1fr), gutter: 12pt,
  shot("mirror-injection.png", [A real Microsoft sign-in page on the phone: the tool found the email field and typed into it.]),
  [
    #v(0.3cm)
    *Injection* is the tool typing a credential into the field on the phone's
    screen. It only happens once the Detection Loop has *recognised* the field —
    by its id (`i0116` is Microsoft's email box), its hint, or its place on a
    sign-in screen — and seen that it is empty.

    Two rules are never broken:

    - the *password* is never logged, and neither is the phone number;
    - a *one-time code field* is never typed into, even though its hint mentions
      "phone": that code belongs to the employee.

    #console(
      cline("[INFO] Microsoft Teams: email field found."),
      cline("       Typing alex.martin@contoso.com."),
      cline("[OK] Email typed into Microsoft Teams.", fill: cGreen),
    )
  ],
)

=== Final check and the Checklist

The last Module reads the phone once more: is the Work Profile there, are the
ticked apps still installed. Then the Checklist appears — every Result from every
Module, in the order they ran.

#shot("checklist-card.png", [The Checklist. MANUAL rows are what is left to do by hand.])

#table(
  columns: (auto, 1fr), stroke: none, inset: (x: 4pt, y: 4pt),
  fill: (_, row) => if calc.odd(row) { greyLight },
  text(fill: okGreen, weight: "bold")[OK], [Done and verified on the phone.],
  text(fill: warnOrange, weight: "bold")[WARNING], [Something should have worked and could not be verified. The line under it names the fix.],
  text(fill: errRed, weight: "bold")[ERROR], [Something failed that blocks handover (no Work Profile, Enrollment cancelled).],
  text(fill: warnOrange, weight: "bold")[MANUAL], [Yours to do: a pin, a sign-in the tool gave up on, Lockdown.],
  text(fill: grey, weight: "bold")[N/A], [Does not apply to this phone (an app not ticked). Its absence is correct.],
)

The same Checklist is printed in the console, so it can be copied into a ticket.

=== Lockdown

The *Lockdown & unplug* button hides Developer options, reads that back, and turns
USB debugging off — in that order, because the last command cuts ADB for good. It
asks for confirmation, stops the Mirror first, and turns the Lockdown row of the
Checklist to OK. It is never run automatically.

=== The Mirror

The Mirror is the phone's screen at up to 30 frames per second, drawn at its
real aspect ratio. A click is a tap, a drag is a swipe. The two buttons in its
corner make it wider or fold it away. If it cannot start, the rest of the tool
works exactly the same; the console says why.

=== The console

#shot("console.png", [The console: every action and its result, coloured by level.])

`INFO` is what the tool is doing, `OK` what it verified, `WARN` what needs a
look, `ERROR` what failed. *Clear* empties it; the Checklist at the end repeats
everything that matters.

=== Diagnostic capture

Started with `--diag`, the tool writes every screen it sees to
`diag/session_<date>/`: the raw XML, a PNG, and a line explaining what it thought
the screen was and what it was about to do, plus a log of every `adb` command.
The password and phone number are masked before anything is written.

#warn[
  The PNGs can still show personal data *in pixels*. `diag/` never leaves the
  computer on its own; check it before sharing any part of it. Share the XML,
  not the PNGs.
]

=== Languages and branding

The window follows the *UI Language*: English and French ship, and any
`locales/<code>.json` next to the tool becomes available. The phone's own
screens are a different matter — see chapter 7.

The banner is `banner.txt`: paste your own ASCII art, or delete the file and the
plain name is shown.

= What stays manual

The tool automates everything ADB can do reliably. What remains is either
forbidden to ADB by Android, or a secret only the employee has.

#table(
  columns: (auto, 1fr, auto), stroke: none, inset: (x: 5pt, y: 5pt),
  fill: (_, row) => if row == 0 { accentLight } else if calc.even(row) { greyLight },
  [*Step*], [*Why*], [*Who*],
  [Device settings], [`settings put`, read back.], text(fill: okGreen)[tool],
  [Opening the store page], [An intent on the managed Play Store.], text(fill: okGreen)[tool],
  [Typing email and password], [Injection into a recognised field.], text(fill: okGreen)[tool],
  [Enrollment screens it knows], [Continue, Skip, Accept, "Contoso device", Phone method…], text(fill: okGreen)[tool],
  [Pinning to the home screen], [A launcher broadcast. Some launchers refuse it.], text(fill: okGreen)[tool, or you],
  [Opening a Work Profile app], [Android Enterprise refuses it to ADB (`SecurityException`).], text(fill: warnOrange)[you],
  [Approving MFA], [It happens on the employee's authenticator.], text(fill: warnOrange)[employee],
  [Typing the SMS code], [It arrives on the employee's phone.], text(fill: warnOrange)[employee],
  [A screen the tool does not know], [It waits rather than guess. Act in the Mirror.], text(fill: warnOrange)[you],
  [Lockdown], [Irreversible at the desk: a button, never a step.], text(fill: warnOrange)[you],
)

Two words keep this clear in the code and in this manual:

- a *Manual Action* is something to do *now*, announced by the orange banner while
  the tool waits;
- a *Manual Step* is a `MANUAL` row of the Checklist: something left *after* the
  run.

#tip[
  Thanks to Microsoft single sign-on, usually only the Company Portal asks for a
  real sign-in; the apps after it reuse the session. The Detection Loop simply
  finds nothing to type and moves on.
]

= How the project is put together

== Context — who talks to whom

#align(center)[
  #set text(size: 8.5pt)
  #cetz.canvas({
    dnode((0, 0), text(fill: white)[*Technician* \ #text(size: 7.5pt)[at a computer]], w: 3.0, h: 1.3, fill: accent, stroke: accentDark)
    dnode((5, 0), [*AndroidContextDeploy* \ #small[desktop tool]], w: 4.4, h: 1.3)
    dnode((5, 2.3), [`deploy.json` \ #small[Organization, apps, settings]], w: 4.4, h: 1.1, fill: greyLight, stroke: grey)
    dnode((10.2, 0), [*Phone* \ #small[USB debugging]], w: 3.0, h: 1.3, fill: greyLight, stroke: grey)
    dnode((10.2, -2.4), [*Intune / managed Play Store* \ #small[assigns and pushes apps]], w: 4.4, h: 1.2, fill: greyLight, stroke: grey)
    arrow((1.5, 0), (2.8, 0))
    dlabel((2.15, 0.3), [drives])
    arrow((5, 1.75), (5, 0.65), colour: grey)
    dlabel((5.6, 1.2), [reads])
    arrow((7.2, 0), (8.7, 0))
    dlabel((7.95, 0.3), [ADB])
    arrow((10.2, -0.65), (10.2, -1.8), colour: grey)
    dlabel((10.9, -1.2), [enrolls])
  })
]

The tool never talks to Intune. It remote-controls the phone, and the phone
enrolls itself. That is why an app that is not *assigned* in Intune can never be
fixed from the tool's side.

== Containers — the pieces inside

#align(center)[
  #set text(size: 8.5pt)
  #cetz.canvas({
    dnode((0, 0), [`app.py` + `ui/` \ #small[the window, UI thread]], w: 4.0, h: 1.1)
    dnode((5.4, 0), [`runner.py` \ #small[one Module at a time]], w: 3.6, h: 1.1)
    dnode((10.6, 0), [`modules/` \ #small[settings, apps, final check]], w: 4.0, h: 1.1)
    dnode((10.9, -2.1), [`signin.py` + `detection.py` \ #small[Detection Loop, Enrollment]], w: 5.2, h: 1.1)
    dnode((5.4, -2.1), [`adb.py` \ #small[the only place adb runs]], w: 3.6, h: 1.1, fill: warnBox, stroke: warnOrange)
    dnode((0, -2.1), [`mirror_service.py` \ #small[scrcpy client]], w: 4.0, h: 1.1)
    dnode((5.4, -4.2), [*Phone* \ #small[`adb` · `scrcpy-server`]], w: 4.4, h: 1.1, fill: greyLight, stroke: grey)
    dnode((0, -4.2), [`diagnostics.py` \ #small[`--diag` only]], w: 4.0, h: 1.1, fill: greyLight, stroke: grey)
    arrow((2.0, 0.15), (3.6, 0.15))
    arrow((3.6, -0.15), (2.0, -0.15), colour: grey)
    dlabel((2.8, 0.5), [run])
    dlabel((2.8, -0.5), [events (queue)])
    arrow((7.2, 0), (8.6, 0))
    arrow((10.6, -0.55), (10.6, -1.55))
    arrow((8.4, -2.1), (7.2, -2.1))
    arrow((9.2, -0.55), (6.6, -1.55))
    arrow((5.4, -2.65), (5.4, -3.65))
    arrow((2.0, -2.1), (3.6, -2.1), colour: grey)
    arrow((0, -2.65), (0, -3.65), colour: grey)
    dlabel((0.9, -3.15), [screens])
    arrow((2.0, -2.5), (4.0, -3.8), colour: grey)
  })
]

Three rules keep the pieces apart, and they are what make the project testable:

- *The UI thread never calls adb.* Modules run in the runner's thread and talk
  back through a queue that `app.py` drains every 150 ms.
- *Only `adb.py` runs adb.* Tests replace it with a fake phone; `--diag` hooks the
  single `_run` method and sees every command.
- *`detection.py` is pure parsing.* It gets XML, it returns what is on the screen.
  No phone is needed to test it.

== The folder tree

```
deploy.json          the manifest: Organization, device_settings, catalog
banner.txt           the startup banner
locales/en.json      UI Language strings (fr.json, …)
main.py              entry point: --diag, --lang
build.py             PyInstaller bundle and archive
scrcpy_server/       scrcpy-server jar for the Mirror (Apache-2.0)
src/androidcontextdeploy/
  app.py             the window: Session, queues, wiring, Lockdown
  runner.py          runs one Module off the UI thread, keeps every Result
  modules/           __init__.py (MODULES, Context), device_settings.py,
                     applications.py, final_check.py
  adb.py             AdbService, DeviceMonitor
  detection.py       ScreenDetector and the keyword tables
  signin.py          SignInDriver: Detection Loop and Enrollment
  mirror_service.py  scrcpy client: H.264 in, touches out
  diagnostics.py     DiagnosticRecorder, DiagnosticPoller (--diag)
  manifest.py        deploy.json: load, validate, app_root()
  i18n.py            t("key")
  models.py          SessionConfig, DeviceInfo, Result, UiField, ScreenAnalysis
  ui/                passive panels: rail, sidebar, form, cards, console, mirror
tests/               pytest; a fake phone and recorded screens
docs/                manual.typ, images/, adr/
```

== Sequence — one app through the Applications Module

#align(center)[
  #set text(size: 8.5pt)
  #cetz.canvas({
    let cols = (0, 3.3, 6.6, 9.9, 13.2)
    let names = ([Technician], [`app.py`], [`applications`], [`signin.py`], [`adb` → phone])
    for (i, x) in cols.enumerate() {
      dnode((x, 0), names.at(i), w: 2.8, h: 0.7)
      d.line((x, -0.35), (x, -9.4), stroke: (paint: grey, dash: "dashed", thickness: 0.6pt))
    }
    let msg(y, a, b, body, back: false) = {
      arrow((cols.at(a), y), (cols.at(b), y), colour: if back { grey } else { accent })
      dlabel(((cols.at(a) + cols.at(b)) / 2, y + 0.22), body)
    }
    msg(-1.0, 0, 1, [Set up applications])
    msg(-1.7, 1, 2, [`runner.run_module` (thread)])
    msg(-2.4, 2, 4, [`is_installed` / `open_play_store`])
    msg(-3.1, 2, 4, [`wait_for_package`])
    msg(-3.8, 2, 4, [`open_app` → refused])
    msg(-4.5, 2, 1, [event: Manual Action], back: true)
    msg(-5.2, 1, 0, [orange banner], back: true)
    msg(-5.9, 0, 4, [taps the icon in the Mirror])
    msg(-6.6, 2, 3, [`run_sign_in`])
    msg(-7.3, 3, 4, [`dump_ui_xml` → `tap` → `inject_text`])
    msg(-8.0, 3, 2, [`"auto"`], back: true)
    msg(-8.7, 2, 1, [Results + event: finished], back: true)
  })
]

= The technologies, explained simply

== ADB — the cable that talks

*Android Debug Bridge* is Google's tool for talking to an Android phone from a
computer. With USB debugging on, `adb shell` runs a command *on the phone* as a
limited user. Almost everything this tool does is one of a handful of commands:

#table(
  columns: (auto, 1fr), stroke: none, inset: (x: 4pt, y: 4pt),
  fill: (_, row) => if calc.odd(row) { greyLight },
  [`settings put system screen_off_timeout 600000`], [Change an Android setting.],
  [`pm list packages --user 10`], [List the apps of user 10 — the Work Profile.],
  [`am start -a VIEW -d market://details?id=…`], [Open an app's page in the Play Store.],
  [`uiautomator dump`], [Write the current screen's UI tree as XML.],
  [`input tap 540 596` / `input text '…'`], [Touch the screen, type text.],
  [`settings put global adb_enabled 0`], [Turn USB debugging off (Lockdown).],
)

In Python it is simply a subprocess: `AdbService._run` builds the command, runs
it with a timeout, and returns `(ok, stdout, stderr)`. The `adb` binary itself
comes from the `adbutils` package, so a release needs nothing installed.

== uiautomator — reading a screen without looking at it

Android keeps, for accessibility, a tree of everything on screen. `uiautomator
dump` writes it out. A Microsoft sign-in page looks like this, trimmed:

```xml
<node class="android.widget.TextView" text="Sign in" bounds="[80,400][1000,480]"/>
<node class="android.widget.EditText" resource-id="i0116" text=""
      focused="true" password="false" bounds="[40,540][1040,652]"/>
<node class="android.widget.Button" text="Next" clickable="true"
      bounds="[780,800][1040,880]"/>
```

`ScreenDetector` reads that tree and answers questions: is there an empty email
field, and where is its centre? Is this an MFA screen? Which button leads on?
It works by *keywords*: short lowercase fragments such as `"sign in"`,
`"se connecter"`, `"i0116"`. That is why a screen in a new language, or a new
manufacturer's wording, is fixed by adding fragments — never by guessing
coordinates.

== Android Enterprise and the Work Profile

A company phone keeps company apps in a separate, managed space: the *Work
Profile*, a second Android user (often `user 10`) whose apps carry a briefcase
icon. The *Company Portal* creates it during Enrollment, and *Intune* then
decides which apps it receives through the *managed Play Store*.

For this tool, two consequences matter. Every app command needs `--user 10`,
found by looking for the managed-profile flag in `pm list users`. And ADB is
*not allowed* to launch an app inside that profile — hence the Manual Action.

== scrcpy, H.264 and PyAV — the Mirror

*scrcpy* is an open-source screen mirroring project. Its small server, a `.jar`,
is pushed to `/data/local/tmp` and started with `app_process`: nothing is
installed. It sends the screen as an *H.264* video stream on one socket and
accepts touch events on another.

*PyAV* (Python bindings to FFmpeg) decodes that stream into frames; *numpy* holds
them; *Pillow* turns the latest one into an image the window can draw, about 25
times a second. A click becomes a 32-byte touch message in scrcpy's control
protocol.

== CustomTkinter, threads and queues — the window

*Tkinter* is the GUI toolkit that ships with Python; *CustomTkinter* gives it a
modern look. Tk has one hard rule: only the thread that created the window may
touch it. Anything slow — every adb call — therefore runs in another thread.

#align(center)[
  #set text(size: 8.5pt)
  #cetz.canvas({
    dnode((0, 0), [*UI thread* \ #small[`after(150)`: drain queues, update panels]], w: 5.2, h: 1.1)
    dnode((7.2, 0), [*Module thread* \ #small[adb calls, loops, `time.sleep`]], w: 5.2, h: 1.1, fill: warnBox, stroke: warnOrange)
    dnode((3.6, -2.0), [`queue.Queue` \ #small[events, log lines, device state]], w: 4.4, h: 1.0, fill: greyLight, stroke: grey)
    arrow((7.2, -0.55), (5.0, -1.5), colour: warnOrange)
    dlabel((7.0, -1.2), [`put`])
    arrow((2.2, -1.5), (0, -0.55))
    dlabel((0.5, -1.2), [`get_nowait`])
  })
]

A Module never knows the window exists: it calls `ctx.runner.emit_progress(…)`,
which puts a small dictionary on a queue. The UI thread picks it up on its next
tick. That separation is also what lets tests run a Module with no window at all.

== JSON — the manifest and the languages

`deploy.json` and `locales/*.json` are plain JSON: data, never code. The
manifest is *validated* when the tool starts — a missing `package_id`, an
unknown `namespace`, an Enrollment app that is not first — and a mistake is shown
with the exact key to fix before anything touches a phone. Strings go through
`t("key", app="Teams")`, which looks the key up in the current language, falls
back to English, and fills the `{app}` placeholder.

== PyInstaller — from Python to an executable

#align(center)[
  #set text(size: 8.5pt)
  #cetz.canvas({
    dnode((0, 0), [`main.py` + `src/` \ #small[+ Python + libraries]], w: 3.4, h: 1.1)
    dnode((4.8, 0), [*PyInstaller* \ #small[`build.py 1.0.0`]], w: 3.4, h: 1.1, fill: warnBox, stroke: warnOrange)
    dnode((10.6, 0.8), [`AndroidContextDeploy(.exe)` \ #small[+ `_internal/`, adb inside]], w: 6.0, h: 1.0)
    dnode((10.6, -0.8), [`deploy.json` · `banner.txt` · `locales/` \ #small[copied next to it, editable]], w: 6.0, h: 1.0, fill: greyLight, stroke: grey)
    arrow((1.7, 0), (3.1, 0))
    arrow((6.5, 0.2), (7.6, 0.8))
    arrow((6.5, -0.2), (7.6, -0.8))
  })
]

PyInstaller collects a Python program, the interpreter and every library into a
folder with a launcher. The build is *onedir* (a folder, not a single file) so it
starts instantly. GitHub Actions runs `build.py` on Windows and on Ubuntu for
every `v*` tag and attaches both archives to the release.

== pytest and fakes — tests without a phone

A test that needs a real phone is a test nobody runs. The tests replace
`AdbService` with a *fake*: a small class with the same method names that
returns recorded screens and remembers what it was asked to tap and type.

```python
outcome, adb, log = _sign_in([DUMP_EMAIL_WEBVIEW, DUMP_EMAIL_FILLED,
                              DUMP_PASSWORD, DUMP_PASSWORD_FILLED,
                              DUMP_HOME, DUMP_HOME, DUMP_HOME])
assert [a[1] for a in adb.actions if a[0] == "text"] == [EMAIL, PASSWORD]
assert "S3cret" not in log          # the password is never logged
```

`python -m pytest` runs the whole suite in a few seconds, on Linux or Windows.

= Enrollment in depth

== What Enrollment is

Enrollment is the Company Portal's first run: sign-in, the "set up access"
screens, admin activation, policies, MFA setup, the terms, the ownership choice.
When it finishes, the phone has a Work Profile and Intune starts pushing apps.
Everything after it depends on it, which is why it is always the first entry of
the Catalog.

== The gate: the managed Play Store, never a timer

The generic Detection Loop decides a sign-in is over when the sign-in screen has
gone. For Enrollment that is badly wrong: the sign-in screen disappears long
before the policies, the MFA and the terms. So Enrollment has exactly *one* exit:

#align(center)[
  #set text(size: 8.5pt)
  #cetz.canvas({
    let y = 0
    dnode((0, 0), [Read focused window \ #small[`dumpsys window`, ~100 ms]], w: 4.4, h: 1.0)
    dnode((0, -1.7), [Play Store focused?], w: 4.4, h: 0.8, fill: warnBox, stroke: warnOrange)
    dnode((6.2, -1.7), text(fill: white)[*Enrollment done* \ #text(size: 7.5pt)[re-read the Work Profile id]], w: 4.0, h: 1.0, fill: accent, stroke: accentDark)
    dnode((0, -3.4), [`uiautomator dump` → ScreenDetector], w: 4.4, h: 0.8)
    dnode((0, -5.1), [Named screen → tap its target \ #small[else MFA / code → wait \ else email, password, button]], w: 5.2, h: 1.3)
    dnode((6.2, -5.1), [*Cancel the session* \ #small[the only other exit]], w: 4.0, h: 1.0, fill: warnBox, stroke: errRed)
    arrow((0, -0.5), (0, -1.3))
    arrow((2.2, -1.7), (4.2, -1.7))
    dlabel((3.2, -1.45), [yes])
    arrow((0, -2.1), (0, -3.0))
    dlabel((0.35, -2.55), [no])
    arrow((0, -3.8), (0, -4.45))
    d.line((-2.6, -5.1), (-3.2, -5.1), (-3.2, 0), (-2.2, 0), stroke: 0.9pt + accent, mark: (end: "stealth", fill: accent))
    dlabel((-3.55, -2.5), [loop], size: 7pt)
  })
]

If the employee walks away mid-MFA, the tool waits — for an hour if it has to.
That is deliberate (ADR-0004): a timeout would stop good Enrollments during a slow
policy push, and a half-finished Enrollment leaves no Work Profile and every
following app on the wrong user. *Confirm* does not bypass the gate; only *Cancel
the session* does, and the Checklist records it as an ERROR.

== The named screens

Before the generic mechanics, `ScreenDetector` checks for the Enrollment screens
it knows, most specific first. Recognising one also stops the generic mechanics
from tapping the wrong button on it.

#table(
  columns: (auto, 1fr), stroke: none, inset: (x: 5pt, y: 5pt),
  fill: (_, row) => if row == 0 { accentLight } else if calc.even(row) { greyLight },
  [*Screen (key)*], [*What the tool does*],
  [Ownership (`ownership`)], [Taps the option containing the *Organization* from `deploy.json` ("Contoso device"), *never* "Personal", then Finish.],
  [Method dialog (`method_dialog`)], [Taps *Phone*, then *Confirm*.],
  [Phone entry (`phone_entry`)], [Types the Session's personal phone, ticks "Text me a code", taps Next. No number: Manual Action.],
  [Authenticator (`authenticator_other_method`)], [Taps the "set up a different method" *link*, not the big Next button.],
  [Terms (`terms`)], [Accept.],
  [Access setup (`access_setup`)], [Continue — *never* "Sign out", which sits right next to it.],
  [Finish account setup (`skip_setup`)], [Skip.],
)

A screen that matches nothing is logged with the buttons it shows, and the tool
waits for the next screen change. It never taps something it does not recognise.

== Why the Organization matters

The ownership screen is the one place where a wrong tap is expensive: choosing
"Personal" enrolls the phone as a personal device, with different policies. The
detector only taps an option containing the `organization` string from
`deploy.json`. A manifest that says "Contoso" on a Fabrikam phone taps nothing,
and the technician chooses in the Mirror.

= Extending it

== First: does it need code at all?

Most of what a company needs is data, and data lives in `deploy.json`. An entry
gets a sidebar row, a progress line, console lines and a Checklist row with a
remediation — for free.

*An app.* Find its id in its Play Store address (`…/details?id=com.Slack`):

```json
{ "name": "Slack", "package_id": "com.Slack", "sign_in": true, "pin": true }
```

*An Android setting.* Any key `settings get` can read:

```json
{ "name": "Stay awake while charging", "namespace": "global",
  "key": "stay_on_while_plugged_in", "value": "3" }
```

Find a key by changing the setting by hand and comparing
`adb shell settings list system` (or `secure`, `global`) before and after.

== Adding a UI Language

+ Copy `locales/en.json` to `locales/es.json`.
+ Translate the *values*. Keep the keys, and keep every `{placeholder}` as it is.
+ Run `python -m pytest`: `tests/test_i18n.py` fails on a missing key or a
  changed placeholder.
+ Start with `--lang es`, or set `"language": "es"` in `deploy.json`.

In a release, drop the file into `locales/` next to the executable. No rebuild.

== Teaching it a new screen

This is the contribution the tool needs most, because every manufacturer,
Android version, Phone Language and Intune configuration words its screens a
little differently.

+ *Capture.* Run with `--diag` and reproduce until the tool is stuck. The console
  names the screen as *UNRECOGNISED* and lists its buttons.
+ *Find it.* In `diag/session_…/`, `trace.jsonl` numbers the screens; open the
  matching `NNN.xml`. The password and phone number are already masked; replace
  any other personal text (names, the email) with Contoso values.
+ *Lock it in a test.* Paste the XML into `tests/test_detection.py` as a
  `DUMP_…` constant and assert what the detector should see — it fails.
+ *Teach it.* Add the short fragments to the right keyword table in
  `detection.py` (for instance `_ACCESS_SETUP_KEYWORDS` for a Spanish
  "configurar el acceso"). The test turns green.
+ *Send it.* Open a pull request with the fixture and the keywords. Never the PNG.

```python
DUMP_ACCESS_SETUP_ES = _wrap(
    '<node class="android.widget.TextView" text="Configurar el acceso a Contoso" .../>'
    '<node class="android.widget.Button" text="CONTINUAR" clickable="true"'
    ' bounds="[560,1700][1040,1800]"/>')

def test_access_setup_in_spanish() -> None:
    s = ScreenDetector("Contoso").analyze(DUMP_ACCESS_SETUP_ES)
    assert s.named_screen == "access_setup"
```

#note[
  Keywords are short *fragments*, lowercase, matched anywhere in the screen's
  text. Prefer `"configurar el acceso"` to the whole sentence: a comma or an
  apostrophe changed by an update should not break recognition.
]

== Adding a Module

Write a Module only when `deploy.json` cannot express the need — reading battery
health, checking the Android security patch level, setting a wallpaper.

=== The four steps

+ Create `src/androidcontextdeploy/modules/my_module.py` from the template below.
+ Append it to `MODULES` in `modules/__init__.py`, where it should run.
+ Add `module.my_module.title`, `.description` and `.run`, and your result
  strings, to *both* `locales/en.json` and `locales/fr.json`.
+ Add a test with a fake phone, as in `tests/test_modules.py`.

=== The template

```python
"""Reports the Android security patch level, and warns when it is old."""
from __future__ import annotations

from datetime import date

from androidcontextdeploy.i18n import t
from androidcontextdeploy.models import Result

NAME = "security_patch"
MAX_AGE_DAYS = 120


def run(ctx) -> list[Result]:
    ctx.runner.emit_progress(0.5, t("progress.security_patch"))
    patch = ctx.adb.get_prop(ctx.device.serial, "ro.build.version.security_patch")
    if not patch:
        return [Result(t("module.security_patch.title"), "WARNING",
                       t("result.security_patch.unknown"))]
    age = (date.today() - date.fromisoformat(patch)).days
    if age > MAX_AGE_DAYS:
        return [Result(t("module.security_patch.title"), "WARNING",
                       t("result.security_patch.old", patch=patch, days=age),
                       t("remedy.security_patch"))]
    return [Result(t("module.security_patch.title"), "OK", patch)]
```

=== What the template is showing you

- *`NAME`* is the key for its strings and its sidebar row.
- *`run(ctx)`* gets everything through `ctx`: `ctx.adb` for the phone,
  `ctx.device.serial`, `ctx.manifest`, `ctx.apps`, `ctx.session`, `ctx.log`,
  `ctx.runner` for progress. It never imports the UI.
- *It returns Results*, at least one. A problem is a `WARNING` or `ERROR` Result
  with a `remedy`, not an exception: the run goes on and the Checklist shows it.
  An unexpected exception is still caught by the runner and becomes an `ERROR`.
- *It only calls methods of `AdbService`.* If the command you need is not there,
  add a method to `adb.py` — never call `subprocess` from a Module.

=== Testing it

```python
def test_old_patch_is_a_warning() -> None:
    phone = FakePhone()
    phone.get_prop = lambda serial, prop: "2024-01-05"
    results = security_patch.run(_ctx(phone))
    assert results[0].kind == "WARNING" and results[0].remedy
```

== Building a release

```bash
pip install -r requirements.txt pyinstaller
python build.py 1.0.0
```

Or push a tag: `git tag v1.0.0 && git push --tags`. GitHub Actions builds the
Windows zip and the Linux tarball and attaches them to the release.

= Troubleshooting

== Reading the Checklist

Start with the `ERROR` rows, then `WARNING`, then `MANUAL`. Every row that needs
something carries a line starting with an arrow: that is the fix, usually naming
the `deploy.json` key or the Intune assignment.

#console(
  cline("  [OK     ] Screen timeout: 10 minutes   system/screen_off_timeout = 600000", fill: cGreen),
  cline("  [WARNING] Microsoft Outlook            Not installed after 5 minutes", fill: cYellow),
  cline("                                         -> Assign it to this user in Intune, or untick /", fill: cYellow),
  cline("                                            remove catalog \"Microsoft Outlook\" in deploy.json.", fill: cYellow),
  cline("  [MANUAL ] Microsoft Teams              installed (user 10) · signed in", fill: cYellow),
  cline("                                         -> pin to the home screen by hand", fill: cYellow),
  cline("  [ERROR  ] Work Profile                 No Work Profile on the phone", fill: cRed),
  cline("  [N/A    ] Microsoft Edge               Not ticked for this phone.", fill: cDim),
)

== Common problems

#table(
  columns: (auto, 1fr), stroke: none, inset: (x: 5pt, y: 5pt),
  fill: (_, row) => if row == 0 { accentLight } else if calc.even(row) { greyLight },
  [*Symptom*], [*What to do*],
  [A `deploy.json` error at start], [The message names the key and the line. Fix it; nothing ran.],
  [No device detected], [Check the cable (a charge-only cable carries no data), USB debugging, and the *Allow* prompt on the phone.],
  [Device not ready (`unauthorized`)], [Unplug, plug back, tap *Allow*. Tick "Always allow from this computer".],
  [`adb unavailable`], [Another adb server may hold the port: close Android Studio or scrcpy, or point `ADB_COMMAND` at the same adb they use.],
  [Mirror unavailable], [See the console line. Everything else works without it.],
  [An app never installs], [It is not assigned in Intune for this user, or the Work Profile does not exist yet. Check the Work Profile row first.],
  [The tool does not open an app], [Expected in a Work Profile: follow the orange banner and tap it in the Mirror.],
  [Stuck on a screen during Enrollment], [It waits by design. Act in the Mirror. If the screen should be known, capture it with `--diag` (chapter 7).],
  [Typed into the wrong field], [Stop with Confirm or Cancel, fix by hand, and report the screen with its XML.],
  [Pinning always fails], [Some launchers refuse shortcut broadcasts. It stays a Manual Step; set `"pin": false` to stop trying.],
  [A setting always WARNs], [The key is read-only or renamed on that manufacturer. Remove it from `device_settings`.],
)

== Getting more detail

The console holds every action; select and copy it into an issue. For a screen
problem, run again with `--diag`: `trace.jsonl` says, screen by screen, what the
detector believed and what the tool did, and `adb.log` has every command with its
raw output. That is almost always enough to fix it without ever seeing the phone.
