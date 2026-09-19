# Catalyst — Voice AI for Business

A done-for-you AI voice agent service for small and medium Indian businesses: it answers inbound customer calls and follows up on leads by phone, and the business owner never touches a config screen — our team sets it up and keeps it current for them over WhatsApp.

## Who it's for

Non-technical SMB owners who want a working voice agent, not a tool to configure: D2C sellers (COD/RTO reduction), real estate brokers (speed-to-lead), coaching institutes (lead follow-up), and clinics (admin-only, hybrid-safety required). BFSI is explicitly out of scope.

## The problem, and the economics

Voice AI is a commodity — Vapi, Bland, Retell, and ElevenLabs sell capable DIY tooling, but only to developers. Yellow.ai, Gnani, and SquadStack sell finished automation, but only to enterprises. A small business that wants a working voice agent with zero setup effort is unserved by both ends of that market. Catalyst sells the finished service to that middle segment. The moat isn't model quality — it's zero-effort onboarding, WhatsApp-based knowledge updates, pre-built escalation logic per vertical, a provider-agnostic backend, and local trust.

This is also a service-heavy business in its first stage, run by a 4-person part-time team with no funding, targeting 15-30 clients in Year 1 — so the build leans on free-tier and self-hosted infrastructure wherever possible, and treats every paid dependency as something to defer until a client's revenue funds it. See `context/decisions.md` for the reasoning behind each of those calls.

## Tech Stack

| Layer | Choice |
|---|---|
| Compute | Oracle Cloud Always Free ARM VM, single Docker Compose stack |
| Voice orchestration | Pipecat (self-hosted); Vapi/Retell as a future paid tier |
| Transport | WebRTC today; PSTN telephony (Exotel/Twilio) deferred to first paying client |
| STT | Groq (whisper-large-v3-turbo) primary, self-hosted faster-whisper fallback |
| TTS | Kokoro (English), Piper (Hindi/Hinglish) |
| LLM | Groq/Cerebras for live calls, Gemini Flash for offline analysis and embeddings |
| Backend | Python 3.12 + FastAPI |
| Database | PostgreSQL + pgvector, self-hosted |
| Queue | Redis + Celery |
| WhatsApp | Meta WhatsApp Cloud API |
| Object storage | Cloudflare R2 |
| Frontend | Next.js + TypeScript + Tailwind + shadcn/ui, on Cloudflare Pages |
| Observability | Langfuse (self-hosted), Sentry, PostHog |

Full detail, and why each choice was made, is in `CLAUDE.md` and `context/architecture.md`.

## Repo Structure

```
CLAUDE.md            instructions for any agent working in this repo
task.md              template for specifying a task
.claude/             Claude Code config, skills, and commands
context/             project knowledge: purpose, architecture, coding rules, decisions, roadmap
mcp/                 MCP server integration docs (none configured yet)
open-source/         open-source & third-party dependency docs (license, cost, integration detail)
```

Application code (backend, frontend, provider abstraction layer) doesn't exist yet — this repo is currently the planning/context scaffold that precedes it.

## Quickstart

**Prerequisites:** Docker + Docker Compose, Python 3.12, Node.js (for the frontend), and free-tier API keys for Groq, Cerebras, and Google Gemini.

**Environment variables** (names only — get real values from whoever holds them, never commit them):

```
DATABASE_URL, REDIS_URL, GROQ_API_KEY, CEREBRAS_API_KEY, GEMINI_API_KEY,
WHATSAPP_CLOUD_API_TOKEN, WHATSAPP_PHONE_NUMBER_ID, WHATSAPP_VERIFY_TOKEN,
CLOUDFLARE_R2_ACCESS_KEY_ID, CLOUDFLARE_R2_SECRET_ACCESS_KEY, CLOUDFLARE_R2_BUCKET,
LANGFUSE_HOST, LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY,
SENTRY_DSN, POSTHOG_API_KEY, JWT_SECRET
```

**Run it:**

```bash
docker compose up -d          # Postgres+pgvector, Redis, Pipecat, backend, workers, self-hosted Langfuse
cd frontend && npm install && npm run dev   # ops dashboard
```

(These are the target commands for the decided stack — there's no application code to actually run yet. See "Current Status" below.)

## Current Status & Roadmap

This repo is pre-code: the tech stack, architecture, and compliance rules are decided and documented, but nothing has been built. We're at the start of **Phase 0 — Zero-cost foundation**: stand up the free infrastructure and get a browser-based voice conversation working end to end, on Rs 0.

After that: Phase 1 proves the product loop with unpaid design partners in one vertical; Phase 2 brings on the first paying clients (which is what unlocks a real phone number); Phase 3 scales across verticals; Phase 4 turns on outbound calling once TRAI DLT registration is complete. Full detail in `context/roadmap.md`.

## Team

A 4-person, part-time student team. This is being built as an execution-service business, not a research project — see `context/decisions.md` for why that shapes almost every technical choice in this repo.

## License

MIT — see `LICENSE`.
