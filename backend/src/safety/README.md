# `backend/src/safety/`

**Purpose.** Guard layer (blocks diagnosis/medicine/dosage in every LLM reply) and the red-flag engine (reads `escalation-rules.yaml`).

**Demo build.** Only `post_call.py`: flags calls whose assistant lines contain medicine, dosage or diagnosis language, for review on `/desk`. Detection, not prevention; the in-call guard is next (ADR-0035). For a business that sells products (orders template), `scan(..., catalogue, selling=True)`: only the "a medicine was named" checks (drug name, "500 mg") ignore the catalogue's own names and pack sizes, compared after folding case, punctuation and "500mg"/"500 mg". Every advice check runs on the line as said, catalogue names included, plus selling checks: a product for a symptom ("bukhar mein le lijiye", "for the pain", "bachche ko de dijiye") and substitutes ("ki jagah", "same hi hai"). Refusals ("substitute nahi bata sakti") are not flagged.

**Capabilities served.** C5, C6

**Contracts used.** `contracts.md` §1.7 (`escalate`), §2 (custom-LLM route)

**Must not.** Be optional or prompt-only for clinics; let any code path speak an unguarded LLM reply on a clinic call.
