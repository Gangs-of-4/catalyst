# Coding Rules

Engineering rules for Catalyst. No application code exists yet. These rules are the standard for the first commit onward.

**Tags:** **[MVP]** rules apply from the first commit. **[Post-MVP]** rules apply once that part of the system exists, or once the team turns them on. Don't block MVP work on a Post-MVP rule.

See also: `CLAUDE.md`, `context/architecture.md`, `context/contracts.md`.

---

## Layout [MVP]

There is one layout, used everywhere: **`backend/src/...`**. Run backend commands from `backend/`.

```
backend/src/
  api/                 FastAPI routers: REST for the web app + the agent tools API
  core/                config, DB session + RLS context, logging (with PII redaction)
  models/              Pydantic schemas and DB row models
  workers/             scheduled jobs (reminders, summaries, alerts) — scheduler per D7
  providers/           the ONLY place vendor SDKs are imported
    llm/ stt/ tts/ voice_orchestrator/ telephony/
  agents/              call session logic and the 9 tool handlers
  knowledge/           approved answers, retrieval, re-embedding
  booking/             resources, availability, blocks, bookings
  safety/              guard layer + red-flag engine
  channels/whatsapp/   doctor commands, alerts, summary, reminders + opt-out
  verticals/           loads and validates verticals/<name>/ config — nothing else
  compliance/          PII guard, consent; outbound DLT gate [Post-MVP]
backend/tests/
verticals/<name>/      prompts, escalation rules, seed knowledge, safety-suite scripts
```

Each module's `README.md` states its purpose, the capabilities it serves, the contracts it uses, and what it must not do.

---

## Architecture rules

- **[MVP] No vendor SDK import outside `backend/src/providers/`.** Business logic depends only on our interfaces (`architecture.md` §8). *Enforcement:* an import-boundary check in CI (import-linter or a Ruff rule) once CI exists. Until then, code review.
- **[MVP] The voice layer talks to us only through the agent tools API** (`contracts.md` §1). No business logic lives in voice-platform config or prompts.
- **[MVP] Every DB query is tenant-scoped.** A dependency sets the RLS session variable once per request, and RLS is the backstop. Every table ships with `tenant_id` + RLS in its first migration.
- **[MVP] Core code never branches on vertical or tenant.** No `if vertical == "clinic"` and no `if tenant_id == …`. Anything that varies lives in `verticals/<name>/` or tenant config. *Check:* the `demo_coaching` fixture loads with no core change.
- **[MVP] No clinic-only names in tables or columns** (`resources`, not `doctors`).
- **[MVP] Shared contracts change in `context/contracts.md` first**, and the PR description says so.

---

## Python [MVP unless tagged]

- Python 3.12 and FastAPI. Async for I/O.
- **Pydantic models for every external payload:** webhooks (WhatsApp, voice platform, telephony), tool requests, and LLM structured output.
- Ruff + Black in CI once CI exists.
- **Before adding a dependency,** record its licence and any free-tier ceiling in `open-source/open-source.md`. Flag copyleft licences.
- **[Post-MVP]** `mypy --strict` as a merge gate. Type hints are still expected in the MVP.

---

## LLM rules

- **[MVP] Prompts live in versioned files, `verticals/<name>/agent-prompt.md`,** never as multi-line string literals in `backend/src/`. Each prompt has a changelog header.
- **[MVP] Structured LLM output is validated against a Pydantic schema and fails closed.** On a parse error, don't write anything, don't guess, and don't substitute defaults: ask the sender to rephrase, or hand off to manual handling (C8). Tests include malformed output.
- **[MVP] Every LLM reply on a clinic call passes the safety guard** (`backend/src/safety/`) before it is spoken. It is code, run unconditionally; no prompt change can disable it.
- **[MVP] Live-call steps have a hard timeout.** A slow response degrades to a short filler, then to the take-a-message path. It never becomes dead air. The budget is set once D1 and spike S3 give real numbers.
- **[Post-MVP]** One LLM wrapper with Langfuse tracing and token accounting. In the MVP, keep all LLM calls in `providers/llm/` so the wrapper can be added in one place.

---

## Safety and compliance

- **[MVP] No PII in logs.** That means no phone numbers, names or transcript text at any level in deployed environments. Log IDs only. A redacting log filter is set up in `core/`. A raw phone number reaching a logger is a blocking review issue.
- **[MVP] No personal data in code, fixtures, tests or docs.** Use placeholders: "the pilot clinic", "Doctor A", "Doctor B", "the receptionist", "our mentor", and obviously fake numbers.
- **[MVP] Preview-and-confirm on every WhatsApp write** (ADR-0017, ADR-0034). It is never bypassed, including when an owner asks for it.
- **[MVP] Only registered tenant numbers can issue WhatsApp commands.**
- **[MVP] Never transfer to the forwarding clinic number.** Transfers go to the contact chain only, and setup validation enforces it.
- **[MVP] Patient messages are service-only** (their own appointments). STOP is honoured permanently.
- **[MVP] Minimum patient data:** name, phone and slot, plus an optional non-clinical reason.
- **[Post-MVP] Outbound calls and SMS** go through the fail-closed DLT gate, the 9 AM–9 PM IST window checked at dispatch time, DND scrub and consent, all as central middleware (`architecture.md` §12). Tests must assert that these gates *block*.

---

## Frontend [MVP]

- Next.js App Router, TypeScript strict, Tailwind + shadcn/ui (the stack the repo already chose).
- Use server components by default; mark client components explicitly with `"use client"`.
- The receptionist screen uses big buttons and must be learnable in 15 minutes. It talks only to the backend API.

---

## Testing

- **[MVP] Safety suite:** 50+ scripted calls in `verticals/clinic/tests/` at a 100% pass rate. Run it before go-live and after every prompt or rule change.
- **[MVP] Red-flag rules** each have paired positive and negative fixtures, including tricky routine-vs-red-flag phrasing.
- **[MVP] Double-booking test:** concurrent `book` calls on one slot produce exactly one booking.
- **[MVP] Dummy-vertical test:** `demo_coaching` loads and validates without core changes.
- **[MVP] Tool contract tests:** every tool matches `contracts.md`.
- **[MVP] Provider contract tests:** every implementation of an interface passes that interface's shared suite.
