# Glossary

| Term | Meaning |
|---|---|
| **Agent** | The AI assistant that answers calls. |
| **Agent tools API** | The nine backend endpoints the voice layer calls (`contracts.md` §1). |
| **Answer mode** | Which calls the agent takes. Pilot: missed and after-hours only. |
| **Backup chain / contact chain** | Ordered list of separate mobile numbers for live transfer and urgent alerts. Never includes the forwarding clinic number. |
| **Block** | A time a resource can't be booked: leave, a break or a holiday. |
| **Callback** | An inbox item for staff to call someone back, e.g. an unanswered question or a failover. |
| **Conditional call forwarding** | Phone setting that forwards calls only when busy, unanswered or unreachable. |
| **Custom-LLM mode** | A managed voice platform sending its LLM calls to our endpoint, so our guard runs. |
| **DLT** | TRAI's Distributed Ledger Technology registration, needed for commercial outbound calls and SMS in India. |
| **DPDP** | India's Digital Personal Data Protection Act. |
| **Escalation** | Handing a call to a human because of a red flag, a grey-zone call or a caller request. |
| **Gate 1 / Gate 2** | Gate 1: pilot goals met and the clinic agrees a price (unlocks Phase 2). Gate 2: three or more paying clinics (unlocks Phase 3). |
| **Grey zone** | A call that might be medical but isn't on the red-flag list. Treated as medical, so it escalates. |
| **Guard layer** | Code in `backend/src/safety/` that blocks diagnosis, medicine or dosage advice in any LLM reply before it's spoken. |
| **Pilot clinic** | Our first customer. Referred to only as "the pilot clinic", "Doctor A", "Doctor B" and "the receptionist". |
| **Pilot number** | The phone number the clinic forwards to (D2). |
| **Red flag** | A doctor-approved phrase or situation that must escalate (`escalation-rules.yaml`). |
| **Resource** | Anything bookable, e.g. a doctor. Generic name, so verticals reuse the model. |
| **RLS** | Postgres Row Level Security. Each tenant sees only its own rows. |
| **Safety suite** | 50+ scripted calls that must pass at 100% before go-live and after any prompt or rule change. |
| **Source** | Where a booking came from: `phone`, `whatsapp` or `walk_in`. |
| **Tenant** | One client business (one clinic). |
| **Vertical** | A customer type (clinic, coaching), defined purely by config in `verticals/<name>/`. |
| **VERIFY** | A marker for unverified facts (prices, limits, regulations, platform features). Check before relying on it. |
