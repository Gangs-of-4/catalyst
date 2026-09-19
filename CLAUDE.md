# CLAUDE.md

Single entry point for any agent (human or Claude) working in this repository. Read this fully before touching code.

## Project

Voice AI for Business is a done-for-you AI voice agent service for small and medium Indian businesses — D2C sellers, real estate brokers, coaching institutes, clinics — handling inbound customer care and outbound lead follow-up calls. Business owners are non-technical and configure nothing; our team runs onboarding, WhatsApp-based knowledge updates, and ongoing setup on their behalf. This is **not** an AI-model or research product — voice AI is a commodity layer underneath it. The moat is zero-effort onboarding, WhatsApp-based knowledge updates, pre-built domain escalation logic, a provider-agnostic backend, and local trust, sold as a finished service to a segment that DIY tools (Vapi/Bland/Retell/ElevenLabs) and enterprise platforms (SquadStack/Yellow.ai/Gnani) both leave unserved. Entry verticals, in priority order: D2C e-commerce (COD/RTO reduction), real estate (speed-to-lead), education (coaching follow-up), healthcare (admin-only, hybrid-safety required). BFSI is out of scope. The team is 4 people, part-time, with effectively no budget — every infra choice is free-tier/open-source/self-hosted, or explicitly deferred until a paying client funds it.

## Tech Stack

| Layer | Choice | Why |
|---|---|---|
| Compute | Oracle Cloud Always Free ARM VM (4 core/24GB/200GB, Mumbai/Hyderabad), Docker Compose | zero-cost compute that also satisfies India data residency |
| Voice orchestration | Pipecat, self-hosted, open source | avoids per-minute Vapi/Retell billing; Vapi/Retell kept as future paid-tier options behind the abstraction layer |
| Transport | WebRTC for all dev/demos | no phone number required pre-revenue |
| Telephony | Exotel or Twilio — **deferred** until a paying client exists | cost is billed through to that client, never provisioned speculatively |
| STT | Groq free tier (whisper-large-v3-turbo) primary; self-hosted faster-whisper (int8, CPU) fallback/offline | free, low-latency primary with an offline-capable fallback |
| TTS | Kokoro TTS (Apache 2.0, CPU) for English; Piper Hindi voices for Hindi/Hinglish | free, self-hosted, no per-call cost; Sarvam/ElevenLabs are paid upgrades behind the abstraction layer, not defaults |
| LLM — live calls | Groq or Cerebras free tier | chosen for latency, not intelligence, during a call |
| LLM — offline (WhatsApp parsing, post-call analysis, embeddings) | Google Gemini Flash free tier | not latency-bound; free tier covers analysis workloads |
| Backend | Python 3.12 + FastAPI | team fluency, async support, fast to ship |
| Database | PostgreSQL + pgvector, self-hosted in Docker on the Oracle VM | no Supabase, no managed DB, no separate vector database — zero recurring cost |
| Queue | Redis + Celery, self-hosted in the same Docker Compose stack | outbound call queue, retries, WhatsApp message ingestion, no managed queue cost |
| Multi-tenancy | `tenant_id` on every table + Postgres Row Level Security | enforced from day one, not bolted on later |
| WhatsApp | Meta WhatsApp Cloud API | free test number in dev, free service-conversation tier in production |
| Object storage | Cloudflare R2 free tier (10GB, zero egress), 30-day lifecycle rule | call audio retention that stays inside the free tier |
| Frontend | Next.js + TypeScript + Tailwind + shadcn/ui, deployed on Cloudflare Pages free tier | ops dashboard + thin read-only client view, zero hosting cost |
| Observability | Langfuse self-hosted (Docker), Sentry free tier, PostHog free tier | minimum viable observability at zero cost |
| CI | GitHub Actions free tier | no paid CI runner |
| Secrets | `.env` files + GitHub Actions secrets | no paid secret manager |

**The abstraction layer is the central architectural idea**: every voice/STT/TTS/LLM provider sits behind our own interface in `src/providers/`, because today's stack is free/self-hosted with worse latency and quality, and must be swappable to paid providers per-client the instant revenue allows. No vendor SDK is imported outside `src/providers/`.

**Known tradeoff (documented, not hidden):** the self-hosted CPU stack runs ~1.2-2s round-trip latency vs. 600-900ms on paid APIs. Acceptable for demos and first design partners — it's the explicit price of zero budget. See `context/decisions.md`.

Rejected alternatives (any per-minute voice platform as default, any managed/paid DB/queue/secret manager, provisioning phone numbers pre-revenue, training a model from scratch, a separate vector DB, a website chatbot now, BFSI) are logged with reasoning in `context/decisions.md` — do not silently reintroduce them.

## Repository Map

- `README.md`, `LICENSE` — project root files.
- `CLAUDE.md` — this file.
- `task.md` — reusable template for specifying the current task.
- `.claude/` — Claude Code configuration.
  - `settings.json` — Claude Code settings.
  - `skills/skills.md` — skill-directory convention; populated once real frontend/backend/db/testing code exists.
  - `commands/commands.md` — custom slash command convention.
- `context/` — project knowledge that doesn't belong in this file: `project-context.md` (purpose/state), `architecture.md` (system design + compliance boundaries), `coding-rules.md` (established conventions), `decisions.md` (ADR log, including rejected alternatives), `roadmap.md` (phased execution plan, incl. which tasks are money-gated and what unblocks them).
- `mcp/` — MCP server integration docs (`mcp.md`, `servers/`, `config/`). None configured yet.
- `open-source/` — docs for significant third-party/open-source integrations beyond what the package manifest records (`open-source.md`, `integrations/`, `references/`).
- Application code (backend, frontend, provider abstraction layer) does not exist in the repository yet — this scaffold predates implementation.

## Non-Negotiable Rules

Apply regardless of task scope; do not relax for convenience.

1. **Provider abstraction layer.** All voice, STT, TTS, and LLM calls go through `src/providers/` — business logic never imports or calls Pipecat, Groq, Cerebras, Kokoro, Piper, Gemini, or (later) Vapi/Retell/Sarvam/ElevenLabs SDKs directly.
2. **Multi-tenancy is mandatory.** Every table storing tenant data has a `tenant_id` column and a Postgres Row Level Security policy from its first migration — no table ships without RLS "for later."
3. **No PII in logs.** No phone numbers, names, transcripts, or recordings in log output. Log tenant/call/lead IDs, never the underlying data.
4. **India data residency.** Personal data — recordings, transcripts, contact details — stays on the Oracle Mumbai/Hyderabad VM (or other India-region infra) per DPDP. Never route personal data through non-India infrastructure or third parties that store it outside India.
5. **No direct provider SDK calls outside `src/providers/`.** This includes today's free-tier providers and any Vapi/Retell/Sarvam/ElevenLabs SDK added later as a paid tier — finding one imported elsewhere is a bug.

Compliance rules that shape architecture and code — TRAI DLT Principal Entity registration (paid, deferred, blocks the entire outbound phase), 9 AM-9 PM IST calling window, consent/DND logging, DPDP consent and deletion handling, healthcare admin-only scope with hard escalation on any symptom/emergency signal — are detailed in `context/architecture.md` and `context/coding-rules.md`. Treat them as load-bearing, not optional.

## Read These First

Before non-trivial work, read in this order:

1. `context/project-context.md` — what this product is, who it's for, current state.
2. `context/architecture.md` — system design, data flow, compliance boundaries.
3. `context/decisions.md` — what's decided and rejected, and why.
4. `context/coding-rules.md` — established conventions once code exists.

## Local Dev Setup

No application code exists in the repository yet; these are the target commands for the decided stack, to be verified against the real scaffolding as it lands. Everything runs in Docker Compose on a single VM (Oracle in production, any machine locally).

```bash
# Full stack (Postgres+pgvector, Redis, Pipecat, backend, workers, self-hosted Langfuse)
docker compose up -d

# Backend (Python 3.12 + FastAPI), if iterating outside Docker
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head            # apply DB migrations
uvicorn app.main:app --reload   # run API locally

# Background workers (outbound call queue, WhatsApp ingestion)
celery -A app.worker worker --loglevel=info

# Frontend (Next.js ops dashboard)
cd frontend
npm install
npm run dev
```

### Required Environment Variables (names only — never commit values)

```
DATABASE_URL
REDIS_URL
GROQ_API_KEY
CEREBRAS_API_KEY
GEMINI_API_KEY
WHATSAPP_CLOUD_API_TOKEN
WHATSAPP_PHONE_NUMBER_ID
WHATSAPP_VERIFY_TOKEN
CLOUDFLARE_R2_ACCESS_KEY_ID
CLOUDFLARE_R2_SECRET_ACCESS_KEY
CLOUDFLARE_R2_BUCKET
LANGFUSE_HOST
LANGFUSE_PUBLIC_KEY
LANGFUSE_SECRET_KEY
SENTRY_DSN
POSTHOG_API_KEY
JWT_SECRET

# Deferred — only needed once a paying client funds these
VAPI_API_KEY
RETELL_API_KEY
SARVAM_API_KEY
ELEVENLABS_API_KEY
EXOTEL_API_KEY
EXOTEL_API_TOKEN
EXOTEL_SID
```
