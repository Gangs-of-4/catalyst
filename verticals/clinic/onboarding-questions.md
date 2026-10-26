# Onboarding questions — clinic

> **DRAFT, team to review.** Answers go into tenant config and `context/go-live-checklist.md` (roles only, never real names or numbers in the repo).

## Clinic
1. Clinic name as the agent should say it.
2. Address and nearest landmark.
3. Hours per weekday; lunch break; weekly off; known holidays.

## Doctors and services
4. Doctors (Doctor A, Doctor B, …): days and hours for each.
5. Can patients choose a doctor? Any doctor-specific services?
6. Default slot length (and which services need longer — data only for now, item 37 is Phase 2).

## Calls and chain
7. Answer mode for the pilot (default: missed and after-hours only).
8. Backup chain in order, separate mobiles only — e.g. Doctor A, Doctor B, the receptionist — and ring time for each. Confirm none of them is the clinic number being forwarded.
9. Which numbers may send WhatsApp commands?

## Knowledge (approved answers, C3)
10. Top questions callers ask: hours, location, fees for common visits, parking, payment modes, what to bring. Exact approved answers.
11. Anything the agent must never say.

## Safety (C5)
12. Review and approve the red-flag list (`escalation-rules.yaml`). Add or remove items.
13. Routine reasons that should just book.
14. The exact after-hours emergency instruction.

## Reminders (C9)
15. When should reminders go out (e.g. the evening before)?

## Consent and voice
16. Consent and recording wording (to review with our mentor).
17. Default voice.

## Baseline (C10)
18. How will we count one week of missed calls before go-live (phone's missed-call log, receptionist tally)?
