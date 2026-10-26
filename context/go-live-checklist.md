# Go-Live Checklist — the pilot clinic

Decide these with the clinic before go-live and record the answers here. **No personal data in this file.** Record roles ("Doctor A's mobile") here and keep the actual numbers in tenant config, not in the repo.

## Decisions with the clinic

| Item | Decision | Agreed on | Notes |
|---|---|---|---|
| Answer mode | _e.g. missed + after-hours only (pilot default)_ | | Full answer-mode switch is Phase 2 (item 3). |
| Backup chain (order) | _e.g. 1. Doctor A mobile, 2. Doctor B mobile, 3. the receptionist's mobile_ | | Must **not** include the forwarding clinic number. |
| Ring time per phone | _seconds each_ | | |
| Red-flag list | _link to approved version of `verticals/clinic/escalation-rules.yaml`_ | | Doctor A signs off. Grey zone counts as medical. |
| After-hours emergency instruction | _exact wording_ | | Doctor-approved. |
| Default voice | | | Clinic's choice; not pitched as a trust fix. |
| Consent and recording wording | | | Reviewed with our mentor (DPDP, VERIFY). |
| Reminder timing | _e.g. evening before_ | | |
| Approved answers (seed knowledge) | _link to approved `seed-knowledge.yaml` values in tenant config_ | | |
| One-week missed-call baseline | _count + dates_ | | Counted **before** go-live; it is the basis for "calls saved". |

## Technical readiness

- [ ] Conditional forwarding set up on the clinic number for busy, no answer and unreachable (S1 confirms how)
- [ ] Transfer to each chain number tested
- [ ] Failover tested: AI down → message taken → urgent callback created
- [ ] Safety suite passes at 100% on the final prompt and rules
- [ ] Concurrent double-booking test passes
- [ ] Doctor A has done one WhatsApp update end to end (preview → Haan → live)
- [ ] Test-call number shared with the doctors
- [ ] WhatsApp templates approved (reminder, alert, summary), see D5
- [ ] Ops alerts firing: forwarding broken, weekday silence, reminder failure
- [ ] Receptionist trained on the desk screen (target: 15 minutes)
- [ ] Deletion-request process written down for ops
