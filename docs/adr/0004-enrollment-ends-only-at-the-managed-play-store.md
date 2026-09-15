# Enrollment ends only when the managed Play Store shows, never on a timer

The generic Detection Loop considers a sign-in finished as soon as the sign-in
screen disappears, and moves on after a timeout. For Enrollment — the Company
Portal, first in the Catalog — that jumps ahead far too early: the sign-in
screen is gone long before admin activation, policies, MFA, the terms and the
ownership choice. Decision (2026-06-16): for Enrollment only, the **single**
condition to move on to the next app is the **managed Play Store showing**
(robust signal: the focused package from `dumpsys window`; fallback: a short
bilingual text fragment). When it is stuck — the employee is away, no SMS code,
MFA abandoned — the tool **waits indefinitely** and says so. The only way out
without reaching the managed Play Store is an explicit "Cancel the session",
which stops the Applications Module. "Confirm" does not bypass the gate.

## Considered Options

- **Bounded timeout, then stop** (~30 min without a screen change) — rejected: a
  long but legitimate pause (the employee looking for their phone, a slow policy
  push) would stop a good Enrollment. A recoverable manual wait costs less than
  an Enrollment cut in half.
- **Keep the generic timeout-then-continue** — rejected: that was precisely the
  bug. A half-finished Enrollment leaves no Work Profile, and every following app
  lands on the wrong user.

## Consequences

- Enrollment can block forever by design; it is bounded by a human, not a clock.
  Do not "fix" the missing timeout.
- The Work Profile user id is read again after Enrollment: the value read when
  the phone was plugged in predates the profile.
