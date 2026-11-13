# Phase 2: multi-business AI front desk

Phase 2 here means the program deliverable (due 15 Nov 2026), not backlog "Phase 2 (after Gate 1)". The build plan and the team lead's answers are in [`context/phase2-plan.md`](../../context/phase2-plan.md).

## What it is

Catalyst answers a small business's phone like a polite receptionist. It books into one shared schedule or takes orders, and it hands anything medical or unclear to a human. The owner runs it from a web desk and from WhatsApp.

In Phase 2 it went from one hard-coded clinic to **any number of businesses**, each signing up by itself:

| What | Where it lives |
|---|---|
| Self-serve signup and login, one owner per business, session cookies | `backend/src/accounts/`, `api/auth.py`, `api/onboarding.py` |
| Two templates as config: **clinic** (bookings) and **wholesale distributor** (orders) | `verticals/clinic/`, `verticals/wholesale/` |
| One Vapi voice assistant per business, created and updated by our backend | `providers/voice_orchestrator/vapi.py`, `api/sync.py` |
| Per-business webhook `/vapi/webhook/{public_id}` with its own secret | `api/vapi.py` |
| Wholesale: catalogue, CSV import, orders and their lifecycle, order board | `backend/src/orders/`, `api/orders.py` |
| Owner custom instructions, screened by rules, versioned with undo, fenced after the safety rules | `agents/instructions.py`, `api/instructions.py` |
| WhatsApp routed by the sender's number, with preview-and-confirm on every write | `channels/whatsapp/`, `api/whatsapp.py` |
| Usage events (no payload), admin dashboard, counts-only CSV, feedback log | `analytics.py`, `api/admin.py`, `api/feedback.py`, `frontend/app/src/features/admin/` |
| Demo clinic and demo wholesaler with today's data and optional 4-week fictional history | `seed.py`, `scripts/seed_demo.py` |
| React single-page app: landing, signup, home, desk, settings, test page, admin | `frontend/app/` (ADR-0042) |
| Deployed: Vercel (frontend) + Render (backend) + Neon Postgres, all free tiers | [deploy.md](deploy.md) |

## Live

- App: https://catalyst-peach-seven.vercel.app
- Try the agent with no login: `/demo/clinic` and `/demo/wholesale`
- How to test it step by step: [try-this.md](try-this.md)
- What doesn't work yet, said plainly: [limitations.md](limitations.md)

## Decisions made for Phase 2

All are in [`context/decisions.md`](../../context/decisions.md).

| ADR | Decision | State |
|---|---|---|
| 0037 | Wholesale distributor as the second template | Accepted |
| 0038 | Self-serve onboarding and owner custom instructions | Accepted |
| 0039 | Render + Neon (Singapore) for the backend; residency exception; app-level tenant scoping instead of RLS | Proposed |
| 0040 | Target voice stack: self-hosted Pipecat + Sarvam in India | Proposed |
| 0041 | Vercel rewrites `/api` to the backend, so session cookies are first-party | Accepted (team, 2026-11-11; cookie checked live 2026-11-12) |
| 0042 | React (Vite + TypeScript + Tailwind + shadcn/ui) for the frontend | Accepted |
| 0043 | Move the frontend from Vercel Hobby to Cloudflare Workers | Proposed |

## Safety rules that still hold

- The safety rules are locked in each template's prompt. Owner instructions go in a fenced section *after* them and can never override them. Lines that conflict are rejected one by one.
- The agent never gives diagnosis, medicine or dosage advice. Wholesale never suggests a substitute product.
- Minimum data: name, phone, slot or order, and an optional non-clinical reason. Usage events carry no payload, so the admin CSV has counts only.
- Every query is tenant-scoped, and isolation tests check that business A can't read or write business B.

## Build record

Milestones M0–M10 merged through PRs #8 to #59. The progress table is in `context/phase2-plan.md`. Changes after deploy:

- #46: the Vapi SDK class shape in the production build;
- #51: Hindi transcriber, and digit-by-digit read-back of phone numbers (clinic prompt 0.3.1, wholesale 0.2.1);
- #52: the voice library loads before the call cap is spent;
- #54: connection pool and latency;
- #55: the old static pages and their backend routes are removed, so the backend serves no HTML;
- #57: admin dashboard for the mentor showcase, and time-in-app pings;
- #58: "microphone not heard" message;
- #59: a stale tab reloads after a deploy.
