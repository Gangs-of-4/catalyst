# `backend/src/safety/`

**Purpose.** Guard layer (blocks diagnosis/medicine/dosage in every LLM reply) and the red-flag engine (reads `escalation-rules.yaml`).

**Capabilities served.** C5, C6

**Contracts used.** `contracts.md` §1.7 (`escalate`), §2 (custom-LLM route)

**Must not.** Be optional or prompt-only for clinics; let any code path speak an unguarded LLM reply on a clinic call.
