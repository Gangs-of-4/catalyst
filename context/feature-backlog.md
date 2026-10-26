# Feature Backlog

All 100 items from the team's backlog, with phases. Item numbers are stable — reference them in PRs and in `context/mvp.md`.

- **MVP** — the 12 capabilities in `context/mvp.md`.
- **Phase 2** — unlocks after **Gate 1**: pilot goals met and the clinic agrees to a price.
- **Phase 3** — unlocks after **Gate 2**: three or more clinics paying.
- **Paid add-ons** — after Phase 2.

Adding an idea: append it under the right phase with the next free number (101+), one line, and say which capability it extends if any. `/align <idea>` can help.

## MVP

Per-item titles for MVP items live in the team's original backlog; this file groups them by capability. Add titles here when convenient.

| Capability | Items |
|---|---|
| C1 Phone line and coverage | 1, 2 |
| C2 Natural conversation | 4, 5, 6, 15, 16, 17, 18 |
| C3 Approved answers only | 7, 8 |
| C4 One shared schedule | 31, 32, 33, 34, 36 *(moved into MVP: choose a doctor)*, 38 |
| C5 Patient safety | 21, 22, 25, 26, 29, 30 |
| C6 Escalation and failover | 23, 24, 27, 28 *(simplified)*, 89 |
| C7 Receptionist screen | 35, 39, 61, 62, 63, 64, 67 |
| C8 Doctor control on WhatsApp | 51, 52, 53 *(moved into MVP: auto-understood updates)*, 55 *(moved into MVP: preview before live)*, 57 *(moved into MVP: today's schedule on WhatsApp)*, 59 |
| C9 Reminders | 41, 50 |
| C10 Proof of value | 81, 82, 83, 85 |
| C11 Privacy and reliability | 84, 86, 90 |
| C12 Clinic setup from config | 80 *(light version: CLI from config; full form is Phase 2)* |

## Phase 2 (after Gate 1)

- 3 Answer-mode switch
- 9 Location on WhatsApp
- 10 Dropped-call recovery
- 11 Male or female voice
- 12 Indian voice library
- 13 Custom agent name
- 14 Speed and tone
- 19 Patience mode for older callers
- 37 Service-based slot length *(the data model supports it from the MVP)*
- 42 Reminder timing options
- 43 Reply to confirm, cancel or move
- 44 Reminder call for non-responders *(an outbound call — check TRAI/DLT first; stays behind the fail-closed DLT gate, ADR-0019)*
- 45 Calling frequency and quiet hours
- 46 Booking confirmation message
- 47 Confirmation tracker
- 54 Voice-note updates
- 56 AGENT OFF/ON *(needs a forwarding design without loops — see the telephony rule in `mvp.md`)*
- 58 Calendar sync
- 65 Home-screen app with alerts
- 66 Hindi or English interface
- 68 Patient search and history
- 71 Agent customisation panel: profile
- 72 Agent customisation panel: greeting editor
- 73 Agent customisation panel: FAQ editor
- 74 Agent customisation panel: services and fees
- 75 Agent customisation panel: hours
- 76 Agent customisation panel: escalation settings
- 77 Agent customisation panel: message templates
- 78 Agent customisation panel: feature switches
- 80 Clinic setup form *(the light config-file version is MVP C12)*
- 87 Delete, export and leave tooling
- 88 OTP login, roles and audit log *(moved from MVP)*

## Phase 3 (after Gate 2)

- 20 Greet returning patients by name
- 40 Waitlist auto-fill
- 48 Treatment follow-ups and recalls
- 49 No-show rebooking nudge
- 60 Voice-assistant shortcut commands
- 69 Live call banner and take-over
- 70 Works on slow internet
- 79 Change history and undo

## Paid add-ons (after Phase 2)

- 91 Custom wake word
- 92 Cloned voice *(written consent required; still discloses it's automated)*
- 93 WhatsApp chat booking
- 94 Website and Instagram assistant
- 95 UPI advance booking fee
- 96 More Indian languages
- 97 Analytics Pro
- 98 Caller-mood detection
- 99 Google review requests *(sent to every patient, never only happy ones)*
- 100 Multi-branch and software links

## Guardrails (from the team)

- Voice gender is the clinic's choice and is never pitched as a fix for the trust gap.
- Automated messages and calls go only to patients about their own appointments, never for marketing.

## Later verticals

- Coaching institutes — next vertical after clinics (ADR-0028). Config only: `verticals/coaching/`.
- D2C, real estate — deferred. Outbound lead follow-up for these stays behind TRAI DLT registration (ADR-0019).
