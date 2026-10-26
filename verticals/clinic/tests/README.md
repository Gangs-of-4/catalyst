# Clinic safety suite

> **DRAFT, team to review.**

`safety-suite.yaml` holds scripted calls. The suite must reach **50+ scripts at 100% pass** before go-live and after every prompt or rule change (C5). This draft has 16 seed scripts across the required categories. Grow it to 50+ in M3.

Categories to cover:
- **Routine booking.** Reason mentioned, no escalation.
- **Red flag.** Each rule in `../escalation-rules.yaml` gets a positive script, plus a near-miss negative.
- **Grey zone.** Escalates.
- **Pushing for advice.** Medicine, dosage, "is it serious", "doctor said it's ok".
- **Unknown question.** Leads to a callback.
- **Staff request** at any point.
- **After hours** with a red flag.
- **Language switching**, and dates said either way.
- **Failover.** A tool error leads to an urgent callback, never silence.

Script format:

```yaml
- id: string
  category: routine | red_flag | grey_zone | advice_push | unknown | staff | after_hours | language | failover
  turns: ["caller line", "..."]
  expect: book | escalate:red_flag | escalate:grey_zone | escalate:caller_request | callback | answer
  must_not_say: [diagnosis, medicine, dosage]
```

No real names or numbers. Callers are "Caller", and phones are fake (`+910000000001`).
