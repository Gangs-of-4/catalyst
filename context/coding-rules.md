# Coding Rules

Enforceable engineering rules for Voice AI for Business. No application code exists in the repository yet — these rules are the target standard for the first and every subsequent commit, not a description of existing patterns. Each rule states what's checked and, where possible, how it's enforced (lint, CI, test, code review) rather than left to memory.

See also: `CLAUDE.md` (non-negotiable rules, tech stack), `context/architecture.md` (system design these rules implement), `.claude/skills/skills.md` (procedures for provider addition and compliance review).

---

## Architecture Rules

**No vendor SDK import outside `src/providers/`.** Business logic depends only on our own interfaces (`VoiceOrchestrator`, `SpeechToText`, `TextToSpeech`, `LLMProvider`, `TelephonyProvider` — `context/architecture.md` §2), never on Pipecat, Groq, Cerebras, Kokoro, Piper, Gemini, or any future paid vendor SDK directly.
*Enforcement:* CI import-boundary check (e.g. `import-linter` or a Ruff/AST-based custom rule) that fails the build if a vendor SDK import appears anywhere under `src/` outside `src/providers/**`. A stray import is a bug, not a style nit — treat it as build-breaking.

**Every DB query is tenant-scoped.** A query against a tenant-owned table with no `tenant_id` filter and no RLS session context set is a bug, full stop — RLS (`context/architecture.md` §3) is the backstop, not the only line of defense, because a bug that silently returns zero rows instead of raising is easy to miss in review.
*Enforcement:* every request handler sets the Postgres RLS session variable (current tenant) before any query executes; a middleware/dependency does this once per request rather than leaving it to each handler. Code review checklist item: any new raw query or ORM call touching a tenant table must be traceable to a request context with tenant scoping already established.

**All per-client config lives in `agent_configs`, never in code.** No `if tenant_id == "..."` branches, no hardcoded client names, phone numbers, prompts, or thresholds in source. Anything that varies by client — language, `cost_tier`, prompt version, escalation rule pack, vertical — is a column or referenced row in `agent_configs` (`context/architecture.md` §3, §12).
*Enforcement:* code review; a codebase-wide search for tenant-identifying string literals outside migrations/seed/test fixtures should return nothing.

---

## Python

- **Python 3.12, FastAPI.** Async by default for anything touching I/O (DB, HTTP, provider calls, Celery task dispatch) — no blocking calls on the request path.
- **Pydantic models for every external payload**: webhook bodies (WhatsApp, telephony callbacks), and LLM structured JSON output. Nothing external is trusted as a raw dict past the boundary where it enters the system.
- **Ruff + Black + `mypy --strict`** run on `src/` in CI; a failing check blocks merge, same as a failing test.
- **`src/` layout:**
  - `api/` — FastAPI routers and request/response handling, including webhook endpoints.
  - `providers/` — the abstraction layer (§ above); the only place vendor SDKs are imported.
  - `agents/` — vertical agent logic: prompt selection/versioning, `agent_configs` handling, agent-type-specific (`inbound_care` vs `outbound_sales`) behavior.
  - `knowledge/` — knowledge base CRUD, the WhatsApp ingestion pipeline (`context/architecture.md` §4), embedding/re-embedding.
  - `telephony/` — outbound queueing/dispatch, calling-window/consent/DND enforcement, the DLT gate (`context/architecture.md` §6).
  - `compliance/` — shared compliance checks used across the above: DND scrub, consent verification, PII-log guards, the healthcare clinical-advice guard.
  - `workers/` — Celery tasks and beat schedules.
  - `models/` — Pydantic schemas and database row models.
  - `core/` — shared config, DB session/RLS context setup, logging setup, app-wide utilities.

---

## LLM-Specific

**Prompts live in versioned files under `prompts/`, never as inline string literals.** A prompt embedded in Python code can't be diffed, versioned, or referenced from a call's `agent_configs.prompt_version` (`context/architecture.md` §3). See the prompt-versioning skill in `.claude/skills/skills.md`.
*Enforcement:* code review rejects any PR introducing a multi-line prompt string literal in `src/`.

**All LLM calls go through one wrapper** that handles retries, timeouts, token accounting, and Langfuse tracing. No call site constructs its own retry loop or calls a provider's `complete()`/`embed()` directly without going through it.
*Enforcement:* the wrapper lives in `src/providers/llm/` (or wraps every `LLMProvider` implementation uniformly); a missing Langfuse trace on an LLM call is treated as a bug in the wrapper's usage, not an acceptable gap.

**Any structured LLM output must be validated against a Pydantic schema and fail closed on parse errors.** This applies to WhatsApp update extraction (`context/architecture.md` §4) and any other place an LLM returns JSON the system acts on. "Fail closed" means: on a validation error, do not write to the knowledge base, do not silently substitute a default, and do not guess at the intended structure — surface the failure (e.g. ask the WhatsApp sender to rephrase, or escalate) instead.
*Enforcement:* test coverage includes malformed/adversarial LLM output fixtures asserting the failure path is taken, not just the happy path.

**Live-call LLM calls have a hard latency budget; document it and assert on it.** Per `context/architecture.md` §11, the live-call LLM stage's share of the ~1.2-2s total budget is a specific number, not "as fast as possible." Document that number where the call is made, and enforce a hard timeout at that budget so a slow response degrades (falls back / apologizes / escalates) rather than the caller sitting in dead air.
*Enforcement:* a timeout wraps every live-call LLM invocation; load/latency tests assert p95 stays within budget, and a regression here should fail CI or be flagged, not discovered from a client complaint.

---

## Safety and Compliance

**Never log phone numbers, names, or transcript content at INFO level or above.** Log tenant/call/lead IDs instead — never the underlying data (`CLAUDE.md` non-negotiable rule 3). If a DEBUG-level trace of raw content is ever genuinely needed for local debugging, it must be behind an explicit local-only flag that cannot be enabled in any deployed environment — `CLAUDE.md`'s "no PII in logs" rule is absolute for anything that ships, and DEBUG is not a loophole around it in production or staging.
*Enforcement:* a logging filter/formatter that redacts known PII field names by default; code review treats a raw phone number or transcript string reaching any logger as a blocking issue, not a nit.

**Consent and DND checks are middleware on the outbound path, not caller responsibility.** No function that dials an outbound call is trusted to remember to check consent/DND itself — the check is enforced centrally so it can't be skipped by a new call site forgetting to call it (`context/architecture.md` §6).
*Enforcement:* the outbound dispatch path structurally routes through this middleware; a call cannot reach `TelephonyProvider.place_outbound_call` without passing through it first.

**Calling-window check happens at dispatch time, not enqueue time.** A call enqueued at 8:55 PM IST but dispatched after a queue delay past 9:00 PM must not go out — the window is real-world wall-clock time at the moment of dialing, not at the moment of queueing.
*Enforcement:* the 9 AM-9 PM IST check re-evaluates immediately before `TelephonyProvider.place_outbound_call` is invoked, every time, even for a call that already passed the check once earlier in its queue lifetime.

**Healthcare agents must never produce clinical advice — enforce with a guard layer, not just prompting.** Prompting alone ("don't give medical advice") is not sufficient; every LLM output on a healthcare-vertical call path goes through a guard check (rule-based or classifier-based) before it reaches TTS, in addition to the escalation rules in `context/architecture.md` §5. A response the guard flags as clinical advice is blocked/rewritten and the call escalates.
*Enforcement:* the guard runs as code on every healthcare-vertical response, unconditionally — it is not something a future prompt change can accidentally disable.

---

## Frontend

- **Next.js App Router**, TypeScript strict mode.
- **Tailwind + shadcn/ui** for styling and components.
- **Server components by default**; a component is a client component only when it genuinely needs interactivity/state — that choice is explicit (`"use client"`), not the default.

---

## Testing

**Every provider implementation needs a contract test against the shared interface.** A new `SpeechToText`, `TextToSpeech`, `LLMProvider`, `VoiceOrchestrator`, or `TelephonyProvider` implementation must pass the same shared test suite every other implementation on that interface passes, proving it's interchangeable from the caller's point of view. See `/new-provider` in `.claude/commands/commands.md`.

**Escalation rules need unit tests with adversarial transcript fixtures.** Each rule in a vertical's escalation rule pack (`context/architecture.md` §5) ships with paired positive (should escalate) and negative (should not) transcript fixtures, including deliberately tricky/borderline phrasing — not just the obvious case. See the escalation-rule-pack skill in `.claude/skills/skills.md`.

**Compliance gates need tests that assert they block, not just that they run.** A test for the calling-window check, DND scrub, consent check, or DLT registration gate (`context/architecture.md` §6) must assert the call is actually rejected/blocked under a violating condition — a test that only confirms the function executes without raising, without checking the outcome, doesn't prove the gate works and doesn't satisfy this rule.
