# Roadmap

A shared map, not a task tracker. Milestones carry capability checklists (C1–C12 from `context/mvp.md`). Tick a box when a capability's "done when" is met, in the same PR that finishes it.

Milestones are not strictly sequential. M4 can run alongside M1, and anyone can pick up anything (`context/team.md`).

## Now

### M0 — Foundation and spikes
- [ ] Spikes S1–S3 planned and run, with results in `context/spikes.md`
- [ ] Backend skeleton runs; Docker Compose with Postgres + pgvector
- [ ] Schema from `contracts.md` §3 with `tenant_id` + RLS and the no-overlap constraint
- [ ] Vertical loader, plus a test that loads `demo_coaching` with no core change
- [ ] Agent tools API stubs matching `contracts.md` §1
- [ ] D1 and D2 decided (ADR-0029 / ADR-0030 accepted or rejected)

### M4 — Doctor on WhatsApp (can start in parallel with M1)
- [ ] C8 Doctor control on WhatsApp
- [ ] D5 WhatsApp Business verification started

## Next

### M1 — Answering
- [ ] C1 Phone line and coverage
- [ ] C2 Natural conversation
- [ ] C3 Approved answers only

### M2 — Schedule
- [ ] C4 One shared schedule
- [ ] C7 Receptionist screen

### M3 — Safety (the safety suite is the go-live gate)
- [ ] C5 Patient safety, with the safety suite at 100%
- [ ] C6 Escalation and failover

## Later

### M5 — Pilot-ready
- [ ] C9 Reminders
- [ ] C10 Proof of value (one-week missed-call baseline counted before go-live)
- [ ] C11 Privacy and reliability (consent notice reviewed with our mentor)
- [ ] C12 Clinic setup from config
- [ ] `context/go-live-checklist.md` complete
- [ ] MVP done-criteria in `context/mvp.md` met

### After the pilot
- **Gate 1:** pilot goals met and the clinic agrees to a price. This unlocks backlog Phase 2. Measure the real per-minute cost first (D4).
- **Gate 2:** three or more clinics paying. This unlocks Phase 3.
- **Coaching vertical:** config only, from `verticals/_template/`.
- **Outbound calls and SMS:** blocked on TRAI DLT registration (ADR-0019). The gate is fail-closed.
