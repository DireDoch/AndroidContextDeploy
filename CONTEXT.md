# AndroidContextDeploy

A desktop tool a technician runs to prepare an Android phone for an employee
over ADB: device settings, Microsoft Intune enrollment, work-profile apps and
their sign-in, then a checklist of what was done and what is left by hand.
Nothing is installed permanently on the phone.

## Language

### Configuration

**Manifest**:
The user-editable `deploy.json` holding every site-specific value — the
Organization, the Catalog, device settings. Adapting the tool to a new company
must never require editing code.
_Avoid_: config, apps.json, settings file

**Organization**:
The company the phone is enrolled into, as its name appears on the phone's
enrollment screens (e.g. the "Contoso device" ownership choice).
_Avoid_: tenant, company, client

**Catalog**:
The ordered list of apps in the Manifest the tool brings onto the Work Profile,
each with whether it needs sign-in and whether it is pinned. Ships with the
Microsoft defaults (Company Portal, Authenticator, Teams, Outlook, Edge).
_Avoid_: app list, packages

**UI Language**:
The language the technician reads in the tool's window and log. English and
French ship with the tool; more can be dropped in without code.
_Avoid_: locale, phone language

**Phone Language**:
The language the phone's own screens are in, which the Detection Loop must
recognise. Independent of the UI Language; only English and French screens are
recognised today.
_Avoid_: UI language, locale

**Banner**:
The editable ASCII art shown at startup; the tool's name defaults to
AndroidContextDeploy when absent.
_Avoid_: logo, branding file

### Device

**Work Profile**:
The Android Enterprise managed space where company apps live (briefcase icon).
Every app operation targets it.
_Avoid_: work space, pro account

**Company Portal**:
The Microsoft Intune app whose sign-in creates the Work Profile and distributes
the other apps through the managed Play Store.
_Avoid_: internal store, MDM, sideload

### Run

**Session**:
The technician's working context for one phone: work email and password, plus
optionally the employee's personal phone number for SMS MFA. Lives in memory
only, destroyed on close, never written to disk.
_Avoid_: account, profile

**Module**:
One area of work, run in a fixed order — device settings, applications,
final check. Adding a Module is only for what the Manifest cannot express.
Lockdown is deliberately not a Module: it is never run automatically.
_Avoid_: phase, step (in the old three-phase sense), plugin

**Enrollment**:
The one-time Company Portal setup — sign-in, admin activation, policies, MFA,
terms, ownership — that creates the Work Profile. Finished only when the managed
Play Store appears, never on a timer. Lives inside the Applications Step.
_Avoid_: step 1, login

**Injection**:
Typing the email or password into the phone's current field over ADB.
_Avoid_: auto-fill

**Detection Loop**:
Repeatedly reading the phone's UI tree to recognise the current screen and the
fields to fill before any Injection.
_Avoid_: screen monitoring, scan

**Manual Action**:
Something the technician must do *right now* because ADB cannot — typically
opening a Work Profile app — announced live while the run waits. Distinct from
a failure and from a Manual Step.
_Avoid_: error, blocker

### Outcome

**Result**:
What one piece of work inside a Module produced: its name, a kind and a detail.
Kinds are OK, WARNING, ERROR, MANUAL and N/A. Every Module yields one or more
Results, kept in the Session until the end.
_Avoid_: status, outcome, pending issue

**Manual Step**:
A Result of kind MANUAL: work the tool leaves to the technician after the run
(pin an app by hand, sign in where detection gave up). Distinct from a WARNING,
which means something should have worked and did not be verified.
_Avoid_: TODO, reserve

**Checklist**:
The end-of-run list of every Result from every Module, in run order — what was
done and what is left by hand — with a remediation naming the Manifest key to
fix when one applies.
_Avoid_: final diagnostic, summary, report

**Mirror**:
The panel showing the phone's screen live and forwarding the technician's
clicks as touches.
_Avoid_: projection, preview

**Lockdown**:
The explicit final action before handover: hide Developer options, then turn
off USB debugging — which severs ADB for good.
_Avoid_: cleanup, reset, disconnect

## Example dialogue

**Dev**: A new company wants Slack instead of Teams. Code change?

**Tech**: No — remove Teams from the Catalog in the Manifest, add Slack with
sign-in on. The Organization name goes in the Manifest too, so Enrollment picks
"Contoso device" on the ownership screen.

**Dev**: Slack isn't on the phone after five minutes.

**Tech**: That's a Pending Issue, not a failure of the run — usually it isn't
assigned in Intune. And if ADB can't open it in the Work Profile, that's a Manual
Action: I tap it in the Mirror and Injection fills the fields.
