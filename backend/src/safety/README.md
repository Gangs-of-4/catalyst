# `backend/src/safety/`

**Purpose.** Guard layer (blocks diagnosis/medicine/dosage in every LLM reply) and the red-flag engine (reads `escalation-rules.yaml`).

**Demo build.** Only `post_call.py`: flags calls whose assistant lines contain medicine, dosage or diagnosis language, for review on `/desk`. Detection, not prevention; the in-call guard is next (ADR-0035).

**Capabilities served.** C5, C6

**Contracts used.** `contracts.md` §1.7 (`escalate`), §2 (custom-LLM route)

**Must not.** Be optional or prompt-only for clinics; let any code path speak an unguarded LLM reply on a clinic call.
