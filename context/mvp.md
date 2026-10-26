# MVP — Clinic Front Desk

**Source of truth for what we are building now.** If another doc disagrees with this one, this one wins. Change it only by team agreement.

## Product

Catalyst is an AI front-desk assistant for small Indian businesses. It answers the phone the way a polite receptionist would. Our team sets it up; the owner controls it from WhatsApp, never from a complicated dashboard.

- **First customer type:** small clinics. The pilot is a dental clinic with two dentists (Doctor A, the owner, and Doctor B) and one receptionist.
- **Next:** coaching institutes. Not built in the MVP, but adding them must need config only, no core-code change.
- **Deferred:** D2C, real estate. **Rejected:** BFSI (ADR-0027).

What discovery told us about the pilot clinic:

- calls are missed whenever the receptionist is with a patient;
- bookings arrive by phone, WhatsApp and walk-in with no single record, so slots get double-booked;
- forgetful patients need repeated manual reminder calls;
- older patients hang up on anything that sounds robotic;
- the owner adopts only what saves time from day one, without learning a new system.

## North star

> A small clinic never misses a patient call. The agent answers, books correctly into one shared schedule, and sends anything medical to a human. The doctor controls everything from WhatsApp.

## The 12 capabilities

Backlog numbers refer to `context/feature-backlog.md`.

| ID | Capability | Backlog | Done when |
|---|---|---|---|
| C1 | Phone line and coverage | 1, 2 | Patients dial the clinic's existing number. Busy, unanswered and after-hours calls forward to the agent (conditional call forwarding). Simultaneous calls are all answered. Pilot mode: missed and after-hours calls only. |
| C2 | Natural conversation | 4, 5, 6, 15, 16, 17, 18 | See below. |
| C3 | Approved answers only | 7, 8 | Answers only from the doctor-approved list. Anything else: says so, takes name and number, logs a callback. |
| C4 | One shared schedule | 31, 32, 33, 34, 36, 38 | See below. |
| C5 | Patient safety | 21, 22, 25, 26, 29, 30 | See below. |
| C6 | Escalation and failover | 23, 24, 27, 28 (simplified), 89 | See below. |
| C7 | Receptionist screen (minimal) | 35, 39, 61, 62, 63, 64, 67 | See below. |
| C8 | Doctor control on WhatsApp | 51, 52, 53, 55, 57, 59 | See below. |
| C9 | Reminders | 41, 50 | WhatsApp reminder before each visit at a clinic-set time. STOP opts out permanently. Service messages only, never promotional. No SMS fallback in the MVP (VERIFY: Indian commercial SMS needs DLT templates). |
| C10 | Proof of value | 81, 82, 83, 85 | Every call tagged: booked, answered, escalated, callback, hung up. Weekly WhatsApp summary to the owner. "Calls saved" measured against a one-week missed-call baseline counted before go-live. Team reviews misunderstood calls weekly and tracks their share. |
| C11 | Privacy and reliability | 84, 86, 90 | See below. |
| C12 | Clinic setup from config | 80 (light) | Team sets up a clinic with one command from config files plus `verticals/clinic/`. The setup form is Phase 2. |

**C2 — natural conversation.** The agent discloses it is the clinic's automated assistant; lets the caller ask for staff at any point; understands Hinglish, Indian names, and dates said either way ("kal shaam 5 baje", "tomorrow 5 pm"); replies in the caller's language and switches mid-call if they do; uses short fillers ("ji", "ek second"); stops talking when interrupted; reads back day, date, time and doctor before confirming a booking. Latency target: under ~1 s (VERIFY on the chosen stack — see D1).

**C4 — one shared schedule.** Books and offers the 2–3 nearest free slots; cancels or moves a booking and the freed slot opens immediately; books a specific doctor when asked; respects leave and holidays. A database constraint allows only one booking per doctor per slot, so no channel can double-book.

**C5 — patient safety.**
- Never gives diagnosis, medicine or dosage advice, even when pushed. Enforced in code by a guard layer, not just the prompt.
- Routine reasons simply book ("daant mein dard hai, appointment chahiye" → booking).
- Only the doctor-approved red-flag list escalates; grey-zone calls count as medical. (Policy change from the old "any symptom escalates" rule — see ADR-0031, Proposed.)
- After hours, gives the doctor-approved emergency instruction.
- A safety suite of 50+ scripted calls must pass at 100%, before go-live and after every prompt or rule change.

**C6 — escalation and failover.** Red-flag calls transfer live to the first contact in the chain. If nobody picks up, an urgent WhatsApp alert goes to the whole backup chain and repeats until someone marks it done. The doctor gets the caller's name, number and a 2-line summary. If the AI or platform fails, the caller is never left in dead air: the system takes a message and creates an urgent callback.

**C7 — receptionist screen.** One responsive web app on the device already at the desk: today's bookings from every channel, tagged by source; one column per doctor; add walk-in and WhatsApp bookings; mark arrived / no-show / done; callback and urgent inbox with "mark done". Big buttons, learnable in 15 minutes. Simple clinic login (OTP, roles, audit log are Phase 2).

**C8 — doctor control on WhatsApp.** The doctor texts e.g. "kal chhutti hai" or "aaj 11 baje se". The system previews the change ("… Sahi hai? Haan/Nahi"), applies it only after "Haan", and replies once it is live. If the parser is unsure, our team handles it manually the same day. "aaj ke appointments?" returns today's schedule plus pending callbacks. A test-call number lets the doctor hear the agent after any change.

**C11 — privacy and reliability.** Transcripts stored; recordings kept only after the caller has been told. Each clinic sees only its own data (`tenant_id` + RLS). DPDP consent notice reviewed with our mentor before go-live. Ops alerted if forwarding breaks, no calls arrive for hours on a weekday, or reminders fail. Deletion requests handled manually by ops in the MVP.

## Telephony design rule

Never transfer or fail over to the clinic number that forwarded the call. Under conditional forwarding that number is busy or unanswered, so sending the call back creates a loop. Transfers and failover go only to separate mobile numbers in the clinic's contact chain. This is also why item 56 (AGENT OFF/ON) stays in Phase 2.

## Decide with the clinic before go-live

Recorded in `context/go-live-checklist.md`: answer mode; backup chain and ring time per phone; red-flag list and after-hours emergency instruction; default voice; consent and recording wording (reviewed with our mentor); the one-week missed-call baseline.

## The MVP is done when

- [ ] the pilot clinic runs on its real number for one week (pending D2);
- [ ] the safety suite passes at 100%;
- [ ] zero double-bookings;
- [ ] the doctor has completed at least one WhatsApp update end to end;
- [ ] the weekly summary has been delivered with a calls-saved figure;
- [ ] a dummy second vertical loads in tests without any change to core code.

## Week-1 spikes

S1 (forwarding into the voice stack), S2 (Hinglish STT comparison), S3 (latency + older listeners). Plans and results: `context/spikes.md`.

## Out of scope for the MVP

Everything in `context/feature-backlog.md` not listed above, including: outbound calls and SMS, AGENT OFF/ON, voice/agent customisation, OTP and roles, the setup form, calendar sync, any non-clinic vertical in production. Open questions live in `context/decisions.md` (D1–D7).
