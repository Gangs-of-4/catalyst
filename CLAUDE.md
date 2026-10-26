# CLAUDE.md

Entry point for any agent working in this repo. Read this, then `context/mvp.md`, before planning work.

## What we're building

**Catalyst** is an AI front-desk assistant for small Indian businesses. It answers the phone like a polite receptionist. Our team sets it up, and the owner controls it from WhatsApp, never from a dashboard.

- **First customer type: small clinics.** The pilot is a dental clinic: Doctor A (owner), Doctor B, and the receptionist.
- **Next:** coaching institutes, as config only. **Deferred:** D2C and real estate. **Rejected:** BFSI.
- The team is four part-time people on Windows, Linux and macOS. Budget is near zero, so paid costs are explicit decisions (`context/decisions.md`).

## North star

> A small clinic never misses a patient call. The agent answers, books correctly into one shared schedule, and sends anything medical to a human. The doctor controls everything from WhatsApp.

## The MVP: 12 capabilities

The full "done when" for each is in `context/mvp.md`, which is the source of truth.

| | | | |
|---|---|---|---|
| C1 Phone line and coverage | C2 Natural conversation | C3 Approved answers only | C4 One shared schedule |
| C5 Patient safety | C6 Escalation and failover | C7 Receptionist screen | C8 Doctor control on WhatsApp |
| C9 Reminders | C10 Proof of value | C11 Privacy and reliability | C12 Clinic setup from config |

**Out of scope for now:** everything else in `context/feature-backlog.md`, including outbound calls and SMS, AGENT OFF/ON, customisation panels, OTP and roles, and the setup form.

## Working agreement for agents

The repo guides; it never blocks. Members choose what they work on. Your job is to keep that work connected to the north star and visible to the others.

1. **Start of session.** Read this file and `context/mvp.md`, and understand what the member wants. In your plan, say which capability (C1–C12) the work moves forward.
2. **Outside the MVP?** Say so in one line, then ask: build it now, or add it to `context/feature-backlog.md`? Do what the member decides. **Never refuse.**
3. **Before anything sizeable,** run `git fetch`, check remote branches and open PRs touching the same module, and mention any overlap.
4. **Shared contracts.** If a change touches `context/contracts.md`, say so clearly in the PR description.
5. **When done,** update the module README or docs if behaviour changed. If a capability is now complete, tick it in `context/roadmap.md`.
6. **Personal data:** never in code, logs, fixtures or docs. Use "the pilot clinic", "Doctor A", "Doctor B", "the receptionist" and "our mentor".
7. **Unverified facts** (prices, limits, regulations, platform features) are marked `VERIFY`.
8. **Decisions.** Don't silently reverse an ADR. Write a **Proposed** ADR instead. Open questions D1–D7 are in `context/decisions.md`; don't resolve them in code.

## Architecture in one screen

- **Our backend owns the brain; the voice stack only talks** (ADR-0032).
  - The voice layer calls nine tools: `get_clinic_info`, `find_slots`, `book`, `reschedule`, `cancel`, `create_callback`, `escalate`, `transfer` and `log_call_outcome`.
  - Contracts are in `context/contracts.md`.
- **The safety guard runs in our code** on every LLM reply on a clinic call. A managed platform must use our custom-LLM endpoint.
- **Generic booking model:** resources, services, availability rules, blocks and bookings. A Postgres exclusion constraint makes double-booking impossible. Every booking has a `source` (`phone`, `whatsapp` or `walk_in`).
- **Verticals are config:** `verticals/<name>/`. Core code never branches on vertical.
- **WhatsApp is its own module.** Preview-and-confirm applies to every write.
- **Telephony.** The clinic number forwards conditionally to the pilot number. **Never transfer back to the forwarding number**; use contact-chain mobiles only.
- **Voice stack (D1) and pilot number (D2) are Proposed ADRs.** Build behind `VoiceOrchestrator` and `TelephonyProvider` so either outcome works.

Details are in `context/architecture.md`.

## Rules

Tags: **[MVP]** applies now. **[Post-MVP]** applies once that part exists. The full list is in `context/coding-rules.md`.

**[MVP]**
1. **One layout: `backend/src/...`.** Vendor SDKs are imported only in `backend/src/providers/`.
2. **`tenant_id` plus RLS** on every tenant table from its first migration. Every query is tenant-scoped.
3. **No PII in logs.** Log IDs only.
4. **Safety guard in code** on every clinic-call LLM reply. Never give diagnosis, medicine or dosage advice.
5. **Pydantic validation** of every external payload and all LLM structured output. Fail closed.
6. **Preview-and-confirm** on every WhatsApp write. Only registered numbers can command.
7. **Prompts** live in `verticals/<name>/agent-prompt.md`, versioned, never inline.
8. **Minimum patient data:** name, phone, slot, and an optional non-clinical reason.
9. **India data residency** is the default. Exceptions for hosted vendors are open (ADR-0029, D3).

**[Post-MVP]**
- Langfuse, Sentry, PostHog, R2 audio, `mypy --strict`, and cost tiers beyond the pilot.
- Outbound calls and SMS go through the fail-closed DLT gate (ADR-0019).

## Stack

| Layer | Choice |
|---|---|
| Backend | Python 3.12 + FastAPI |
| Database | PostgreSQL + pgvector (self-hosted), RLS |
| Voice | behind `VoiceOrchestrator`: managed platform for the pilot (Proposed, D1), or self-hosted Pipecat (ADR-0004) |
| Telephony | behind `TelephonyProvider`; provider by spike S1 (D2) |
| WhatsApp | Meta WhatsApp Business Platform: utility templates, paid per message (D5) |
| Frontend | Next.js + TypeScript + Tailwind + shadcn/ui |
| Jobs | Celery beat or lighter (D7) |
| Hosting | single India-region VM, Docker Compose; RAM is disputed (D3) |

## Map

```
context/       mvp.md (source of truth) · feature-backlog · contracts · architecture
               decisions (ADRs + D1–D7) · roadmap (M0–M5) · go-live-checklist · spikes
               coding-rules · team (work areas) · glossary
verticals/     _template/ (copy to start) · clinic/ (DRAFT)
backend/src/   api core models workers providers/{llm,stt,tts,voice_orchestrator,telephony}
               agents knowledge booking safety channels/whatsapp verticals compliance
backend/tests/ incl. fixtures/verticals/demo_coaching
frontend/      receptionist web app (C7)
scripts/       clinic setup CLI (C12), call review CLI (C10)
.claude/       helper commands: /whats-next /align /new-vertical /standup (optional)
.github/       PR + issue templates (reminders, not gates)
mcp/ open-source/   integration notes, licences, free-tier limits
task.md        optional template for specifying a task
```

Each `backend/src/<module>/README.md` gives the module's purpose, the capabilities it serves, the contracts it uses, and what it must not do.

## Local setup

See `README.md` for Windows and Linux/macOS steps. Environment variable names are in `.env.example`; never commit values.
