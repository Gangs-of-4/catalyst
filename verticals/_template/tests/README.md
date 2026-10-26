# Vertical tests — _template

Safety-suite scripts and fixtures for this vertical. Run by `backend/tests/` against the agent.

- `safety-suite.yaml` — scripted calls. Each has caller turns and the expected outcome (`book`, `escalate:<category>`, `callback`, `answer`) plus things the agent must never say.
- Every red-flag rule in `../escalation-rules.yaml` needs at least one positive and one negative script.
- Healthcare-type verticals need 50+ scripts at 100% pass before go-live and after every prompt or rule change.
- No real names or numbers. Use "Caller", "Doctor A", and fake numbers like `+910000000001`.
