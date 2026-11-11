# Architecture Decisions

ADR log for Catalyst. One entry per significant, actually-made decision — never backfilled invented history. Every entry states a **cost implication** explicitly, because the team operates under a zero-budget constraint (ADR-0002): `Free` (no recurring cost), `Free tier with limits` (free today, bounded by a quota/ceiling), or `Deferred paid` (a real cost, intentionally pushed to when a paying client funds it).

**Format:** ID · Date · Status · Cost implication · Context · Decision · Consequences.

**Statuses:** `Accepted` · `Proposed` (written down, awaiting team approval — do not build on it as if settled) · `Superseded` · `Rejected`. ADRs are never deleted; a reversal is a new ADR. If a change would reverse an Accepted ADR, write it as **Proposed**.

**Open decisions** (not yet ADRs) are at the bottom: D3–D7. D1 is decided (ADR-0029, Accepted); D2 is still a Proposed ADR (ADR-0030).

**Path note (2026-10-26):** older ADRs say `src/...`. The layout is now `backend/src/...` everywhere (e.g. `backend/src/providers/`). Section numbers (`architecture.md` §N) in ADRs dated before 2026-10-26 refer to the earlier architecture doc; see git history.

## Index

| ID | Title | Status | Cost implication |
|---|---|---|---|
| ADR-0001 | Adopt a Claude Code context-engineering structure | Accepted | Free |
| ADR-0002 | Zero-budget as a binding architectural constraint | Accepted — *challenged by ADR-0029, ADR-0030 (Proposed)* | Free |
| ADR-0003 | Oracle Cloud Always Free as the single production host | Accepted — *RAM figure disputed, see D3* | Free tier with limits |
| ADR-0004 | Self-hosted Pipecat over paid Vapi/Retell | Accepted — *pilot uses Vapi per ADR-0029; Pipecat stays the long-term path* | Free |
| ADR-0005 | WebRTC-first development; PSTN deferred | Accepted — *challenged by ADR-0030 (Proposed)* | Free |
| ADR-0006 | Telephony cost passed through per-client | Accepted — *challenged by ADR-0030 (Proposed)* | Deferred paid |
| ADR-0007 | Groq free tier for live-call STT and LLM | Accepted | Free tier with limits |
| ADR-0008 | Kokoro + Piper for TTS over paid Sarvam/ElevenLabs | Accepted | Free |
| ADR-0009 | Gemini Flash free tier for offline parsing and embeddings | Accepted | Free tier with limits |
| ADR-0010 | Self-hosted Postgres + pgvector over Supabase/managed DB | Accepted | Free |
| ADR-0011 | Self-hosted Langfuse over Langfuse Cloud | Accepted | Free |
| ADR-0012 | Cloudflare R2 free tier, 30-day audio lifecycle | Accepted | Free tier with limits |
| ADR-0013 | Cloudflare Pages for frontend hosting | **Superseded by ADR-0036** | Free tier with limits |
| ADR-0014 | Provider abstraction layer as the free-to-paid migration mechanism | Accepted | Free (enables cheap Deferred paid later) |
| ADR-0015 | Accept 1.2-2s latency as the price of zero budget | Accepted — *MVP targets <~1 s; challenged by ADR-0029 (Proposed)* | Free |
| ADR-0016 | Multi-tenancy via tenant_id + RLS from day one | Accepted | Free |
| ADR-0017 | Mandatory human confirmation before applying WhatsApp knowledge updates | Accepted — *extended to every WhatsApp write by ADR-0034* | Free |
| ADR-0018 | Separate agent configs for customer care vs. outbound sales | Accepted | Free |
| ADR-0019 | Inbound-first; outbound blocked on paid DLT registration | Accepted | Deferred paid |
| ADR-0020 | Reject self-hosting speech models (Whisper/Piper) | **Superseded by ADR-0021** | Deferred paid (assumed API cost) |
| ADR-0021 | Adopt self-hosted faster-whisper + Piper | Accepted — **supersedes ADR-0020**; *challenged by ADR-0029 (Proposed)* | Free |
| ADR-0022 | Vapi/Retell as the default voice platform | Rejected — *ADR-0029 (Proposed) would use one for the pilot only* | Deferred paid |
| ADR-0023 | Managed Postgres, managed Redis, paid secret manager | Rejected | Deferred paid |
| ADR-0024 | Speculative phone number provisioning | Rejected — *ADR-0030 (Proposed) would allow one pilot number* | Deferred paid |
| ADR-0025 | Training our own speech/language models | Rejected | Deferred paid |
| ADR-0026 | A separate vector database | Rejected | Free tier with limits (would've added its own footprint) |
| ADR-0027 | BFSI vertical | Rejected | N/A — not a cost decision |
| ADR-0028 | Clinics first, coaching second; D2C and real estate deferred | Accepted — supersedes the vertical order in ADR-0027's consequences and the old `CLAUDE.md` | N/A |
| ADR-0029 | Managed voice platform for the pilot behind `VoiceOrchestrator` (D1) | Accepted — Vapi | Deferred paid → paid during pilot |
| ADR-0030 | One team-funded phone number for the pilot (D2) | **Proposed** — *demo uses Vapi web calls* | Paid during pilot |
| ADR-0031 | Clinic escalation by doctor-approved red-flag list, not "any symptom" | Accepted | Free |
| ADR-0032 | Backend owns the brain: agent tools API, safety guard in our code | Accepted | Free |
| ADR-0033 | Verticals are config; generic booking model with exclusion constraint | Accepted | Free |
| ADR-0034 | WhatsApp is its own channel module; preview-and-confirm on every write | Accepted — extends ADR-0017 | Free tier with limits (per-message pricing, D5) |
| ADR-0035 | Demo build simplifications | Accepted — *revisit before the first real clinic pilot*; frontend hosting amended by ADR-0036; frontend stack amended by ADR-0042 | Free tier with limits (Vapi, Twilio sandbox trial credit) |
| ADR-0036 | Vercel for frontend hosting, deployed from GitHub Actions | Accepted — **supersedes ADR-0013**; *decision 4 amended by ADR-0041; hosting challenged by ADR-0043 (Proposed)* | Free tier with limits (Vercel Hobby — non-commercial terms, see Consequences) |
| ADR-0037 | Wholesale distributor template | Accepted — *amends the vertical order in ADR-0028* | Free |
| ADR-0038 | Self-serve onboarding and owner custom instructions | Accepted | Free tier with limits (one Vapi assistant per business) |
| ADR-0042 | React (Vite + TypeScript + Tailwind + shadcn/ui) for the frontend | Accepted — *amends the frontend row of ADR-0035; replaces the Next.js plan* | Free |
| ADR-0039 | Render + Neon for the Phase 2 backend; residency exception; app-level tenant scoping | **Proposed** — *would supersede ADR-0003 for Phase 2; departs from ADR-0010, ADR-0016, ADR-0023* | Free tier with limits |
| ADR-0040 | Target voice stack: self-hosted Pipecat + Sarvam in India | **Proposed** — *would change ADR-0008, ADR-0021, ADR-0029* | Deferred paid |
| ADR-0041 | Vercel rewrites `/api` to the backend for first-party session cookies | Accepted — *amends ADR-0036 decision 4* | Free tier with limits |
| ADR-0043 | Move the frontend from Vercel Hobby to Cloudflare Workers (static assets) | **Proposed** — *would supersede ADR-0036; would carry ADR-0041's `/api` forwarding over as a Worker script* | Free tier with limits |

---

## Accepted

### ADR-0001: Adopt a Claude Code context-engineering structure

- **Date:** 2026-09-12
- **Status:** Accepted
- **Cost implication:** Free — documentation only, no infrastructure.

**Context:** The repository had no structure to guide Claude Code sessions: no `CLAUDE.md`, no task template, no separation between always-relevant instructions, project knowledge, and deeper technical/MCP/third-party documentation.

**Decision:** Establish `CLAUDE.md` (always-relevant instructions), `task.md` (current-task template), `context/` (project knowledge, architecture, coding rules, decisions), `mcp/` and `open-source/` (integration docs), and `.claude/skills/` + `.claude/commands/` (reusable skills/commands) — populated as real code and workflows come into existence.

**Consequences:** Contributors (and Claude) must update the relevant file in this structure, not just `CLAUDE.md`, when architecture, conventions, or integrations change.

---

### ADR-0002: Zero-budget as a binding architectural constraint

- **Date:** 2026-09-12
- **Status:** Accepted
- **Cost implication:** Free — this is the constraint that forces every other decision toward `Free` or `Free tier with limits`.

**Context:** The team is 4 people, part-time, with effectively no money, targeting 15-30 clients in Year 1. An earlier stack draft (Vapi, Exotel, Sarvam, Supabase, AWS) assumed a budget that doesn't exist.

**Decision:** Every infrastructure choice must be free-tier, open-source-and-self-hosted, or explicitly deferred until a paying client exists and funds it. A doc recommending a paid service without marking it `Deferred paid` is wrong by definition. When a paid service is genuinely unavoidable (phone numbers, DLT registration), its cost is passed through to the client that requires it, not absorbed.

**Consequences:** Every subsequent infra ADR in this log is downstream of this one. It also means the provider abstraction layer (ADR-0014) isn't optional polish — it's what makes moving off free-tier components later a config change instead of a rewrite.

---

### ADR-0003: Oracle Cloud Always Free as the single production host

- **Date:** 2026-09-12
- **Status:** Accepted
- **Cost implication:** Free tier with limits — permanently free within Oracle's Always Free ceiling (4 ARM cores, 24GB RAM, 200GB disk), not a trial.

**Context:** Zero budget (ADR-0002) rules out any paid VM/hosting. DPDP requires personal data (recordings, transcripts, contact details) to stay in India-region infrastructure.

**Decision:** Run the entire stack as one Docker Compose deployment on a single Oracle Cloud Always Free ARM VM in the Mumbai or Hyderabad region — chosen specifically because it satisfies India data residency at zero cost, which no other Always Free tier available to the team does.

**Consequences:** Everything must fit in 24GB RAM and run on ARM (aarch64) — see `context/architecture.md` §10 for the RAM budget and ARM constraint. A single VM is also a single point of failure; acceptable at current scale, revisit once revenue funds redundancy.

---

### ADR-0004: Self-hosted Pipecat over paid Vapi/Retell

- **Date:** 2026-09-12
- **Status:** Accepted
- **Cost implication:** Free — self-hosted, open source. (Vapi/Retell remain available as a `Deferred paid` tier, see ADR-0022.)

**Context:** Vapi and Retell charge per minute, which doesn't work under zero budget at any call volume. Voice orchestration itself is a commodity — see `CLAUDE.md` positioning.

**Decision:** Use Pipecat, self-hosted, as the default `VoiceOrchestrator` implementation. Vapi and Retell are implemented behind the same interface as future paid-tier options, not removed from the codebase's design.

**Consequences:** We own the operational burden of running Pipecat (upgrades, scaling, debugging) that a managed platform would otherwise absorb. This is accepted as the explicit tradeoff for zero cost.

---

### ADR-0005: WebRTC-first development; PSTN deferred

- **Date:** 2026-09-12
- **Status:** Accepted
- **Cost implication:** Free — no phone number or per-minute telephony charge required for development or demos.

**Context:** A real phone number (via Exotel/Twilio) costs money from day one regardless of call volume. Development, demos, and early design-partner conversations don't require dialing a real number.

**Decision:** All development and demos use WebRTC as the transport. PSTN telephony (ADR-0006) is deferred until a paying client exists.

**Consequences:** The product can be demoed and iterated on with zero telephony spend. A real phone number only enters the picture once ADR-0006's per-client billing trigger fires.

---

### ADR-0006: Telephony cost passed through per-client

- **Date:** 2026-09-12
- **Status:** Accepted
- **Cost implication:** Deferred paid — incurred only when a specific paying client requires a real phone number, and billed to that client.

**Context:** Exotel/Twilio phone numbers cost money per number, ongoing. Provisioning one before a client exists would be a recurring cost with no attached revenue.

**Decision:** Telephony (Exotel or Twilio) is provisioned per-client, only once that client is paying, with the cost billed through to them rather than absorbed into company overhead.

**Consequences:** No speculative telephony spend ever appears on the company's books (see ADR-0024, rejected). Client onboarding must include a step where telephony cost is quoted and passed through.

---

### ADR-0007: Groq free tier for live-call STT and LLM

- **Date:** 2026-09-12
- **Status:** Accepted
- **Cost implication:** Free tier with limits — subject to Groq's rate limits/quotas.

**Context:** Live-call STT and LLM inference need low latency more than raw quality (see `CLAUDE.md`, `context/architecture.md` §11). Groq's free tier runs on purpose-built low-latency inference hardware.

**Decision:** Use Groq free tier (`whisper-large-v3-turbo` for STT; Groq or Cerebras for the live-call LLM) as the default. Latency was the selection criterion, not model intelligence.

**Consequences:** Quota exhaustion mid-call must be handled gracefully (see `context/architecture.md` §13 — fail over to self-hosted faster-whisper, per ADR-0021, rather than dropping the call).

---

### ADR-0008: Kokoro + Piper for TTS over paid Sarvam/ElevenLabs

- **Date:** 2026-09-12
- **Status:** Accepted
- **Cost implication:** Free — self-hosted, open-source (Kokoro is Apache 2.0). Sarvam/ElevenLabs remain `Deferred paid` upgrades behind the abstraction layer.

**Context:** Paid TTS (Sarvam, ElevenLabs) has per-character or per-minute cost incompatible with zero budget at volume.

**Decision:** Use Kokoro TTS (CPU) for English and Piper Hindi voices for Hindi/Hinglish as the default `TextToSpeech` implementations.

**Consequences:** Voice quality/prosody is a step below paid options — accepted as part of the zero-budget tradeoff (ADR-0015). Sarvam/ElevenLabs are implemented behind the same interface so upgrading is a config change (`cost_tier`), not new code.

---

### ADR-0009: Gemini Flash free tier for offline parsing and embeddings

- **Date:** 2026-09-12
- **Status:** Accepted
- **Cost implication:** Free tier with limits.

**Context:** WhatsApp knowledge-update parsing, post-call analysis, and knowledge-base embeddings aren't latency-bound the way live calls are, so a larger free-tier model is affordable there without hurting the caller experience.

**Decision:** Use Google Gemini Flash free tier for offline LLM work: WhatsApp message structured extraction (`context/architecture.md` §4), post-call analysis, and `LLMProvider.embed()` for `knowledge_base_entries`.

**Consequences:** Offline processing throughput is bounded by Gemini's free-tier quota; acceptable since it isn't real-time and can be queued via Celery.

---

### ADR-0010: Self-hosted Postgres + pgvector over Supabase or any managed DB

- **Date:** 2026-09-12
- **Status:** Accepted
- **Cost implication:** Free — runs in Docker on the already-free Oracle VM (ADR-0003).

**Context:** A managed database (Supabase or otherwise) has a recurring cost once usage exceeds its free tier, and adds an external dependency outside our own India-region infrastructure.

**Decision:** Run PostgreSQL with the pgvector extension self-hosted in Docker Compose on the Oracle VM. No separate vector database (ADR-0026).

**Consequences:** We own backup, upgrade, and availability for Postgres ourselves. In exchange, relational data, vector embeddings, and (per ADR-0011) Langfuse's metadata all share one zero-cost instance, and data never leaves India-region infra.

---

### ADR-0011: Self-hosted Langfuse over Langfuse Cloud

- **Date:** 2026-09-12
- **Status:** Accepted
- **Cost implication:** Free — self-hosted on the same Oracle VM.

**Context:** Langfuse Cloud has usage-based pricing beyond its free tier. Call tracing volume will grow with client count, making a metered cloud cost unpredictable under zero budget.

**Decision:** Self-host Langfuse in Docker on the Oracle VM, sharing the existing Postgres instance (ADR-0010) for trace storage rather than running Langfuse's own ClickHouse-backed stack, to conserve the 24GB RAM budget.

**Consequences:** Some Langfuse UI/analytics features that depend on ClickHouse are unavailable; acceptable tradeoff for RAM headroom (`context/architecture.md` §10) and zero cost.

---

### ADR-0012: Cloudflare R2 free tier, 30-day audio lifecycle, stay under 10GB

- **Date:** 2026-09-12
- **Status:** Accepted
- **Cost implication:** Free tier with limits — 10GB storage ceiling, zero egress fees.

**Context:** Call audio needs storage for QA and dispute resolution, but paid object storage or exceeding R2's free tier introduces recurring cost. DPDP also requires a deletion path (`context/architecture.md` §7).

**Decision:** Store call audio in Cloudflare R2 under a 30-day lifecycle rule (tightened from the general 30-90 day range) specifically to stay inside the 10GB free ceiling as tenant count grows.

**Consequences:** Audio older than 30 days is unavailable for QA review. A monitoring job is required to catch usage approaching 10GB before 30 days naturally clears it (`context/architecture.md` §13).

---

### ADR-0014: Provider abstraction layer as the free-to-paid migration mechanism

- **Date:** 2026-09-12
- **Status:** Accepted
- **Cost implication:** Free to build (engineering time only) — its entire purpose is making future `Deferred paid` upgrades cheap.

**Context:** Nearly every default choice above (Pipecat, Groq, Kokoro/Piper, self-hosted Postgres) is free specifically because of zero budget, not because it's the best long-term choice. Voice AI vendor choice is not our differentiation (`CLAUDE.md` positioning) — so being stuck with today's free-tier vendor would be a self-inflicted, avoidable risk.

**Decision:** Every voice, STT, TTS, and LLM provider sits behind our own interface in `backend/src/providers/` (path updated 2026-10-26) (`VoiceOrchestrator`, `SpeechToText`, `TextToSpeech`, `LLMProvider`, `TelephonyProvider` — see `context/architecture.md` §2). No vendor SDK is imported outside that directory. Provider selection is resolved per-tenant at runtime from `agent_configs.cost_tier`.

**Consequences:** Adding or upgrading a provider is additive (new file + contract test), never a rewrite of business logic. This is treated as non-negotiable in `CLAUDE.md`, enforced via `/compliance-check`-style grepping for stray SDK imports.

---

### ADR-0015: Accept 1.2-2s latency as the price of zero budget

- **Date:** 2026-09-12
- **Status:** Accepted
- **Cost implication:** Free — this decision is literally "accept worse latency in exchange for $0 infrastructure cost."

**Context:** The self-hosted CPU stack (faster-whisper, Kokoro/Piper, Groq/Cerebras) runs measurably slower than an all-paid-API stack: an estimated ~1.2-2s round trip vs. 600-900ms (`context/architecture.md` §11).

**Decision:** Accept the higher latency as an explicit, documented tradeoff for demos and first design partners, rather than pretending it doesn't exist or quietly reaching for a paid provider to hide it.

**Consequences:** Agent prompts must be written to tolerate this latency and handle interruption gracefully (see the prompt-versioning skill in `.claude/skills/skills.md`). When budget appears, paid STT is upgraded first, then TTS (`context/architecture.md` §11), because they're the largest latency contributors.

---

### ADR-0016: Multi-tenancy via tenant_id + RLS from day one

- **Date:** 2026-09-12
- **Status:** Accepted
- **Cost implication:** Free — a schema/code discipline; Postgres Row Level Security is a built-in feature, not an add-on.

**Context:** Every table stores data belonging to a specific client tenant. Retrofitting tenant isolation after tables and queries already exist is far riskier than building it in from the first migration.

**Decision:** Every table storing tenant data carries a `tenant_id` column and a Postgres RLS policy from its very first migration — no table ships without RLS "for later" (`context/architecture.md` §3).

**Consequences:** Slightly more upfront schema/migration work per table; in exchange, a cross-tenant data leak becomes a defense-in-depth failure (app bug + RLS bypass) rather than a single point of failure.

---

### ADR-0017: Mandatory human confirmation before applying WhatsApp knowledge updates

- **Date:** 2026-09-12
- **Status:** Accepted
- **Cost implication:** Free — a product/process decision, no infrastructure cost.

**Context:** The business owner's only configuration surface is WhatsApp. An LLM-parsed update (e.g. a price change) could be misparsed, and a misparsed update silently applied could cause the agent to tell a real customer the wrong price or policy.

**Decision:** Every WhatsApp-sourced update goes: message → LLM structured extraction → confirmation message back to the owner → **only on explicit confirmation** is `knowledge_base_entries` written and re-embedded (`context/architecture.md` §4). This step is never bypassed, including for latency or UX-friction reasons.

**Consequences:** Knowledge updates take one extra round trip (a WhatsApp reply) before taking effect. This is accepted as the cost of preventing a wrong extraction from reaching a live customer call.

---

### ADR-0018: Separate agent configs for customer care vs. outbound sales

- **Date:** 2026-09-12
- **Status:** Accepted
- **Cost implication:** Free — a schema/design decision; both agent types reuse the same infrastructure.

**Context:** Inbound customer care and outbound lead follow-up are both "voice agent calls" technically, but have different goals (support/resolution vs. conversion/follow-up), different prompts, and often warrant different `cost_tier` settings.

**Decision:** Model them as separate `agent_configs` rows per tenant (`agent_type`: `inbound_care` | `outbound_sales`), sharing the same `VoiceOrchestrator`/`SpeechToText`/`TextToSpeech`/`LLMProvider` infrastructure (`context/architecture.md` §3).

**Consequences:** A tenant can run both agent types independently — e.g. free-tier inbound care plus a higher `cost_tier` for outbound sales calls that justify the cost — without any code branching on "which kind of call is this."

---

### ADR-0019: Inbound-first; outbound blocked on paid DLT registration

- **Date:** 2026-09-12
- **Status:** Accepted
- **Cost implication:** Deferred paid — TRAI DLT Principal Entity registration is a real, unavoidable cost, gating the entire outbound phase.

**Context:** TRAI requires DLT Principal Entity registration before any outbound commercial calling. Registration costs money the team doesn't have yet, and outbound calling without it is a compliance violation, not just a risk.

**Decision:** Ship inbound customer care first. The entire outbound pipeline (`context/architecture.md` §6) ships with a DLT registration gate that is **fail-closed by default** — it blocks the queue unless a confirmed registration record exists, not a feature flag someone could leave on.

**Consequences:** Revenue from outbound lead follow-up (a priced-in D2C/real estate/education use case) is delayed until registration is funded and completed. This is accepted as non-negotiable rather than worked around.

---

### ADR-0021: Adopt self-hosted faster-whisper + Piper

- **Date:** 2026-09-12
- **Status:** Accepted — supersedes ADR-0020
- **Cost implication:** Free — CPU-only inference on the already-free Oracle ARM compute (ADR-0003); zero incremental cost.

**Context:** ADR-0020 rejected self-hosting these models because GPU and ops cost were judged to exceed paid API cost — a conclusion that assumed a budget existed to pay for either the GPU or the APIs. Under the zero-budget constraint (ADR-0002), neither assumption holds: there's no budget for paid APIs at scale, and the Oracle Always Free VM provides CPU compute (not GPU) at zero cost.

**Decision:** Reverse ADR-0020. Run `faster-whisper` (int8, CPU) as the offline/fallback STT and Piper as a default Hindi TTS voice, both self-hosted in Docker on the Oracle VM (`context/architecture.md` §10).

**Consequences:** No GPU is available or needed — both run CPU-only in int8/quantized mode, which is part of why the latency tradeoff in ADR-0015 exists. This reversal is only valid under the zero-budget constraint; if the constraint changes (ADR-0002 revisited), ADR-0020's original reasoning about ops burden should be re-examined too.

---

### ADR-0028: Clinics first, coaching second; D2C and real estate deferred

- **Date:** 2026-10-26
- **Status:** Accepted — supersedes the vertical order in ADR-0027's consequences and the old `CLAUDE.md`
- **Cost implication:** N/A.

**Context:** Discovery work found a pilot dental clinic with clear, daily pain (missed calls, double-bookings, manual reminders) and an owner willing to pilot. The old order (D2C → real estate → education → healthcare, healthcare gated last) had no pilot customer behind it.

**Decision:** Clinics are the first customer type and the MVP (`context/mvp.md`). Coaching institutes are next, added as config only. D2C and real estate are deferred. BFSI stays rejected (ADR-0027).

**Consequences:** The healthcare safety guard moves from a late gate to an MVP requirement (C5). Outbound lead follow-up, the main D2C/real-estate use case, stays deferred behind DLT (ADR-0019).

---

### ADR-0032: Backend owns the brain — agent tools API, safety guard in our code

- **Date:** 2026-10-26
- **Status:** Accepted
- **Cost implication:** Free — a design rule.

**Context:** Whichever voice stack we use (managed or self-hosted Pipecat), switching it must never touch business logic. Healthcare also needs a safety check we control, not one buried in a vendor prompt.

**Decision:** Knowledge, schedule, rules, safety decisions and alerts live in our backend. The voice layer only talks and calls our **agent tools API** — nine tools: `get_clinic_info`, `find_slots`, `book`, `reschedule`, `cancel`, `create_callback`, `escalate`, `transfer`, `log_call_outcome` (contracts in `context/contracts.md`). Every LLM reply on a clinic call passes our safety guard (`backend/src/safety/`) before it is spoken. With a managed platform, its LLM calls route through our own endpoint (custom-LLM mode) so the guard still runs. A platform that cannot do this is not acceptable for healthcare.

**Consequences:** `contracts.md` becomes a shared contract all four work areas build against; changes to it are called out in PRs. Adds one network hop per LLM turn on a managed platform — measure in spike S3.

---

### ADR-0033: Verticals are config; generic booking model with exclusion constraint

- **Date:** 2026-10-26
- **Status:** Accepted
- **Cost implication:** Free.

**Context:** Coaching follows clinics. Adding it must not need a restructure. Double-bookings across phone, WhatsApp and walk-in are the pilot clinic's main pain.

**Decision:** Each vertical is a folder `verticals/<name>/` (`vertical.yaml`, `agent-prompt.md`, `escalation-rules.yaml`, `onboarding-questions.md`, `seed-knowledge.yaml`, `tests/`). Core code never branches on vertical; `backend/src/verticals/` only loads and validates. The booking model is generic: resources, services, availability rules, blocks, bookings — no table or column named after a clinic-only concept. Every booking has a `source` (`phone` | `whatsapp` | `walk_in`). A Postgres exclusion constraint makes overlapping active bookings for the same resource impossible.

**Consequences:** A dummy `demo_coaching` vertical must load in tests without core changes — that test is an MVP done-criterion. Prompts move from the old `prompts/` idea into `verticals/<name>/agent-prompt.md`.

---

### ADR-0034: WhatsApp is its own channel module; preview-and-confirm on every write

- **Date:** 2026-10-26
- **Status:** Accepted — extends ADR-0017
- **Cost implication:** Free tier with limits — business-initiated messages (reminders, alerts, summaries) are billed per message (D5, VERIFY).

**Context:** WhatsApp was documented only as knowledge-update ingestion under `src/knowledge/`. The MVP also needs doctor schedule commands, urgent alerts, a weekly summary and patient reminders with opt-out.

**Decision:** `backend/src/channels/whatsapp/` owns all of it. ADR-0017's rule widens: **every** WhatsApp-sourced write (knowledge or schedule) is previewed and applied only after an explicit "Haan". Only numbers registered to the tenant may give commands.

**Consequences:** Knowledge and booking modules expose plain service functions; WhatsApp calls them after confirmation. Formats in `context/contracts.md`.

---

### ADR-0035: Demo build simplifications

- **Date:** 2026-10-27
- **Status:** Accepted — every item below is revisited **before the first real clinic pilot**.
- **Cost implication:** Free tier with limits — Vapi trial credit, Twilio WhatsApp sandbox, Cloudflare quick tunnel (all VERIFY).
- **Departs from (for the demo build only):** ADR-0010, ADR-0013, ADR-0016, ADR-0032, ADR-0033, ADR-0034, and `contracts.md` §1 transport.

**Context:** We need a working, demo-able clinic voice agent in one day, on Windows machines, with fictional data only. Several accepted decisions cost more setup time than one day allows.

**Decision:** The demo build (`feat/demo-mvp`) takes these shortcuts. Each has a revisit trigger: *before the first real clinic pilot*.

| Shortcut | Instead of | Notes |
|---|---|---|
| SQLite file (`backend/data/clinic.db`) | Postgres + pgvector (ADR-0010) | Docker on Windows would eat the day. The double-booking lock is kept as a **partial unique index** on `(resource_id, date, time)` for active bookings, so the DB, not app code, still refuses a double booking. It only covers fixed-length aligned slots; the overlap exclusion constraint (ADR-0033) returns with Postgres. |
| Single clinic, no `tenant_id` / RLS | ADR-0016 | One fictional clinic. Keep a `clinic_id` seam in mind; add `tenant_id` + RLS with the Postgres migration. |
| Plain HTML, CSS and JS served by FastAPI | Next.js on Cloudflare Pages (ADR-0013) | No build step. The Vapi Web SDK is bundled once with esbuild and committed. *Amended 2026-11-09 by ADR-0036:* the same static files are also deployed to Vercel; FastAPI still serves them for local runs. *Amended 2026-11-11 by ADR-0042:* the frontend becomes a Vite + React app; the static pages are replaced page by page during Phase 2 M8. |
| Cloudflare quick tunnel | A hosted VM | Public HTTPS URL for Vapi and Twilio webhooks; the URL changes on every restart. |
| Vapi web calls | A phone number (ADR-0030, still Proposed) | Prospects talk to the agent from our web page. Live transfer is impossible on web calls, so `transfer` is a stub. |
| One `POST /vapi/webhook` with `x-catalyst-secret` | `POST /v1/tools/<name>` with `X-Catalyst-Tool-Key` (`contracts.md` §1) | Vapi sends every tool call and server message to one URL. Tool logic is the same; see `contracts.md` §1.10. |
| Safety = prompt rules + red-flag `escalate` + **post-call** safety flag | Guard in code on every reply via custom-LLM (ADR-0032) | Detection, not prevention. The custom-LLM guard is the next step and is required before any real patient call. |
| Twilio WhatsApp sandbox, rule-based commands | Meta WhatsApp Business Platform (D5) | Free-text alerts work inside the sandbox's 24-hour window only. Preview-and-confirm (ADR-0034) is kept. |

**Consequences:** The demo must never take real patient calls. Moving to the pilot means: Postgres with `tenant_id` + RLS and the exclusion constraint, the custom-LLM guard, the `/v1/tools/*` transport, a real number (ADR-0030), and Meta WhatsApp templates.

---

### ADR-0036: Vercel for frontend hosting, deployed from GitHub Actions

- **Date:** 2026-11-09
- **Status:** Accepted — **supersedes ADR-0013**; amends the frontend row of ADR-0035
- **Cost implication:** Free tier with limits — Vercel Hobby plan (VERIFY limits in `open-source/open-source.md` §2). Hobby is licensed for **non-commercial use only**; moving to Pro is a **Deferred paid** cost that must happen before the frontend serves a paying client.

**Context:** Nothing is deployed yet. ADR-0013 picked Cloudflare Pages for a future Next.js app; ADR-0035 has FastAPI serve the demo's static pages. The team wants the frontend on Vercel. The repo is public and owned by a 4-member GitHub organisation; the Vercel account is one person's Hobby account. Vercel's commit-author check on Hobby (only the owner's commits deploy) applies to **private** repositories in a GitHub organisation; for public repositories "collaboration is free" (Vercel docs: *Deploying Git Repositories*, *Troubleshoot project collaboration*). Backend hosting is **not decided** (D3).

**Decision:**
1. **All frontend hosting is Vercel** — the current static pages (`frontend/`) now, and the planned Next.js app later.
2. **Deploys run from GitHub Actions** (`.github/workflows/deploy-frontend.yml`) after the `CI` workflow succeeds on a push to `main` (`workflow_run`; it deploys exactly the commit CI tested, and runs on every merge because `workflow_run` can't filter by path), with the Vercel CLI pinned to `vercel@65.1.0`: `vercel pull` → `vercel build --prod` → `vercel deploy --prebuilt --prod`, with the real Git metadata. Because the repo is public, any teammate's merge deploys. The real commit SHA is recorded on the GitHub side: the job is a GitHub `production` environment deployment, and the job summary records the deployed SHA and URL.
3. **Vercel's own Git integration stays off** (`"git": {"deploymentEnabled": false}` in `frontend/vercel.json`), so Actions is the only path to production — no duplicate deployments.
4. **The browser calls the backend directly.** The backend's public HTTPS URL is the Vercel environment variable `NEXT_PUBLIC_API_URL`, injected at build time (into `static/config.js` for the static pages; natively for Next.js later). The backend allows the Vercel domain via `CORS_ALLOWED_ORIGINS`. Vercel serves only static files and **never proxies API traffic** — no rewrites to the backend.

**Consequences:**
- *Data residency (rule 4):* holds — patient data goes browser ↔ backend and never passes through Vercel, which is not India-hosted. Do not add Vercel rewrites, serverless functions or edge middleware that touch API data; that would route personal data through non-India infrastructure.
- *Until D3 is decided* `NEXT_PUBLIC_API_URL` stays empty and the deployed pages call `/api` on their own origin, which does not exist on Vercel — so the Vercel site shows the pages but no live data. Set it (and `CORS_ALLOWED_ORIGINS` on the backend) once the backend has a stable public HTTPS URL; a Cloudflare quick tunnel URL changes on every restart and would need a redeploy each time.
- *`/desk` and `/setup` auth:* they use HTTP Basic auth (`DESK_PASSWORD`). Browsers do not show a Basic-auth prompt for cross-origin `fetch`, so with a password set these pages will not work cross-origin. They need a login form or token auth before the Vercel-hosted desk is used — a follow-up, not done here.
- *The repo must stay public.* On Hobby, Vercel cannot deploy a private repository in a GitHub organisation. Making it private means Vercel Pro or another host. Hiding commit authors (for example deleting `.git` before deploying) is **rejected**: it would circumvent a documented Vercel restriction, which their fair use guidelines treat as a violation. Going private would also, on GitHub Free for organisations, likely drop the required-review rule on `main` and limit Actions minutes.
- *Licence:* Vercel Hobby is non-commercial only, and Vercel counts "advertising the sale of a product or service" as commercial. The public Try-it page shows our service to prospective clinics, so it likely counts as commercial use already. Move to Pro, or revisit hosting (Cloudflare Pages has no such limit on its free plan, VERIFY its terms), before using the Vercel site to market to clinics.
- *Manual setup:* repo secrets `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID`; Vercel project Root Directory = `frontend`, not connected to the Git repo.

---

### ADR-0037: Wholesale distributor template

- **Date:** 2026-11-10
- **Status:** Accepted — team lead, 2026-11-10. Amends the vertical order in ADR-0028.
- **Cost implication:** Free — config plus one generic orders module.

**Context:** The Phase 2 program deliverable (due 15 Nov 2026) needs a multi-business product with real design partners. Our first real lead outside clinics is a medicine manufacturer that sells wholesale and takes many order calls a day. ADR-0028 put coaching second; no coaching partner exists yet.

**Decision:** Add `verticals/wholesale/` as the second template, alongside clinic. Coaching stays next after that, still config only. Wholesale needs orders, not appointments, so we add a generic **orders** module (catalogue, orders, order lines; `source` = `phone` | `whatsapp` | `walk_in`, as for bookings). Which modules a business uses comes from `vertical.yaml` (`modules: [bookings]` or `[orders]`); core code still never branches on the template name (ADR-0033). The no-medical-advice rule applies to wholesale too: the agent never advises on medicines, dosage or substitutes, even though the products are medicines. Contracts: `contracts.md` §1.11, §3.1, §4.

**Consequences:** `vertical.yaml` gains `modules`, `tools` and `onboarding` keys (template first, then every vertical). The desk shows the schedule or the order board from config. Conflicts on orders never suggest another product.

---

### ADR-0038: Self-serve onboarding and owner custom instructions

- **Date:** 2026-11-10
- **Status:** Accepted — team lead, 2026-11-10.
- **Cost implication:** Free tier with limits — each business gets its own Vapi assistant; web-call minutes are capped (`contracts.md` §1.10) because there is no Vapi budget yet.
- **Changes:** moves backlog items 80 (setup form) and parts of 71–78 (customisation panel) out of "Phase 2 after Gate 1" for the program deliverable; `mvp.md` C12 ("team sets up a clinic") gains a self-serve path. The config-file setup stays.

**Context:** Phase 2 needs any small business to sign up, create its own front desk, test it and use it daily without our team in the loop. Owners also want to tell the agent things ("pehle Hindi mein baat karo") without seeing a system prompt.

**Decision:**
1. Email + password signup (`hashlib.scrypt`), one owner per business, HttpOnly session cookies. No OTP, roles or email verification yet (item 88 stays later).
2. A 2-minute create-business form, prefilled from the chosen template. On creation a per-business Vapi assistant is created and the owner lands on their test page.
3. **Custom instructions**, one plain-language box (≤ 500 characters) in onboarding, settings and WhatsApp ("agent ko bolo …"). The core prompt — identity, truth rules, booking/order flow, every safety rule — stays locked. Owner text goes into a fenced section **below** the safety rules, and the prompt tells the model owner text can never override safety or truth rules. Each line is screened on save (rules always; LLM via the provider layer when a key is set). Conflicting lines are rejected with a plain reason, and the rest is saved. Every version is kept, with undo.
4. Usage events (no payload) and an in-app feedback button, for the usage evidence and feedback log.

**Consequences:** Prompt rule 7 holds: the prompt still lives in `verticals/<name>/agent-prompt.md`; owner text is data inserted into one placeholder. A test proves no owner text can remove or reorder a safety line. WhatsApp writes still need "Haan" (ADR-0034).

---

### ADR-0042: React (Vite + TypeScript + Tailwind + shadcn/ui) for the frontend

- **Date:** 2026-11-11
- **Status:** Accepted — team, 2026-11-11. Amends the frontend row of ADR-0035 and the "keep the frontend static HTML" answer in `phase2-plan.md` §8. Replaces the Next.js plan (ADR-0013's app, `CLAUDE.md` stack row).
- **Cost implication:** Free — open-source libraries (MIT); the build runs in the existing GitHub Actions + Vercel pipeline.

**Context:** Phase 2 M8 redesigns every page and adds signup, login, onboarding, settings and admin. The static pages are small (about 1k lines), so they are cheap to replace. Building the new screens in plain JS means hand-writing every form, dialog and state change. The team wants better UI/UX and to use component libraries directly (shadcn/ui, and 21st.dev patterns through its MCP, `mcp/servers/21st/21st.md`), and those are React + Tailwind. Next.js was the long-term plan, but nothing needs server rendering: every page is behind login or is a client-side web call, and the backend owns all logic (ADR-0032).

**Decision:**
1. **`frontend/` becomes a Vite + React + TypeScript (strict) single-page app**, with Tailwind CSS, shadcn/ui components and React Router. Exact versions are pinned in `package-lock.json`.
2. **No Next.js.** A static build fits Vercel and the `/api` rewrite (ADR-0041) as they are. Revisit only if a page needs server rendering.
3. **The browser API is unchanged.** Pages call relative `/api/...` (contracts.md §6). Locally, the Vite dev server proxies `/api`, `/vapi` and `/healthz` to FastAPI on port 8000, so cookies stay same-origin. In production the Vercel rewrite does the same (ADR-0041). Pages still hold no business rules, never touch the database and keep no patient data in browser storage.
4. **Migration is page by page in M8, one PR per task.** The old static pages and FastAPI's page routes keep working until their React replacement merges, then they are deleted.
5. **The Vapi Web SDK becomes an npm dependency** (`@vapi-ai/web`, pinned), replacing the committed `static/vapi.bundle.js` once the try page is ported.
6. **CI gets a frontend job** (install, type-check, lint, build), and the Vercel deploy builds the Vite app. Both come with the scaffold PR.
7. **Design** stays in `frontend/DESIGN.md` (phase2-plan §6). Tokens become Tailwind theme values / CSS variables, as shadcn/ui expects. 21st.dev or shadcn components are adapted to those tokens and the "Catalyst"-only brand rule before they ship.

**Consequences:**
- Frontend work needs **Node 24 LTS** on every OS (the deploy workflow already uses Node 24). Running only the backend still needs no Node until the old static pages are deleted. After that, local runs use `npm run dev` beside `uvicorn`.
- A build step exists now: a broken frontend build blocks the deploy, as a failing CI already does.
- `coding-rules.md` Frontend rules change from Next.js App Router to Vite + React (no server components).
- Bundle size and AA contrast are checked per page in the M8 checklist (360px width, keyboard focus).
- Every new dependency's licence is recorded in `open-source/open-source.md`.

---

## Proposed

ADR-0029 and ADR-0031 were accepted on 2026-10-27 and stay here so their history reads in order. The rest need team approval. Until approved, the Accepted ADRs they challenge still stand — but build behind the interfaces so either outcome works.

### ADR-0029: Managed voice platform for the pilot behind `VoiceOrchestrator` (D1)

- **Date:** 2026-10-26
- **Status:** Accepted — Team lead chose Vapi, 2026-10-27.
- **Cost implication:** Paid during the pilot (per-minute platform fees, VERIFY current pricing); Pipecat stays the long-term low-cost path.
- **Would change:** ADR-0002 (zero budget), ADR-0004 (Pipecat default), ADR-0015 (1.2–2 s accepted), ADR-0021 (self-hosted speech), ADR-0022 (Vapi/Retell rejected as default).

**Context:** The backlog's effort estimates and the MVP's sub-~1 s latency target (C2) assume a managed platform (Vapi/Retell). The accepted ADRs chose self-hosted Pipecat at zero cost with 1.2–2 s latency. Older callers hang up on robotic or slow agents, so latency is a product risk, not polish.

**Recommendation:** Use a managed platform for the single pilot clinic, behind `VoiceOrchestrator`, and keep Pipecat as the long-term low-cost path. Conditions:

1. The platform must support the custom-LLM route (ADR-0032) so our safety guard runs on every reply. VERIFY on the chosen platform.
2. **Data residency.** A US-hosted platform processes call audio outside India, which breaks this repo's India-residency rule. The team and our mentor decide whether that is acceptable for the pilot under DPDP (VERIFY), or find an India-hosted option. **Note:** the same question already applies to the accepted stack — Groq/Cerebras (live STT/LLM), Gemini (offline parsing) and Cloudflare R2 (audio) are not India-hosted as far as we know (VERIFY). Decide residency for all of them together.

**Consequences if accepted:** Spike S3 measures real latency; D3 (hosting) and D4 (cost per minute) must be re-checked.

---

### ADR-0030: One team-funded phone number for the pilot (D2)

- **Date:** 2026-10-26
- **Status:** **Proposed** — Demo uses Vapi web calls; number decided before the pilot.
- **Cost implication:** Paid during the pilot, owned by the team (VERIFY provider pricing).
- **Would change:** ADR-0002 (paid costs passed through, not absorbed), ADR-0005 (WebRTC-first), ADR-0006 (per-client, once paying), ADR-0024 (no speculative numbers).

**Context:** Item 1 (C1) needs a real number before the clinic pays. Missed calls on the clinic's own number cannot be proven over WebRTC, so the pilot cannot show value without one.

**Recommendation:** One pilot number, cost owned by the team during the pilot. Spike S1 decides the provider (and whether an Indian provider such as Exotel must sit between the SIM/landline and the voice stack; VERIFY the regulatory side).

**Consequences if accepted:** ADR-0024's rule still holds for everything beyond this one number. At Gate 1 the cost moves to the clinic per ADR-0006.

---

### ADR-0031: Clinic escalation by doctor-approved red-flag list, not "any symptom"

- **Date:** 2026-10-26
- **Status:** Accepted — Team lead chose Vapi, 2026-10-27. (Accepted together with ADR-0029; it loosens a documented safety rule, so the safety suite gate below is binding.)
- **Cost implication:** Free.
- **Would change:** the old healthcare rule ("any symptom description → immediate hard escalation, no exceptions") previously in `context/architecture.md` §5 and `.claude/skills/skills.md`.

**Context:** Most clinic calls mention a reason ("daant mein dard hai"). Escalating every one would flood the doctor and defeat the product. Discovery showed routine reasons should just book.

**Decision (proposed):** The agent still never gives diagnosis, medicine or dosage advice — enforced by the guard in code. Routine reasons book. Only the doctor-approved red-flag list (`verticals/clinic/escalation-rules.yaml`) escalates; **grey-zone calls count as medical and escalate**. After hours, the approved emergency instruction is given. The 50+ call safety suite must pass at 100% before go-live and after every prompt or rule change.

**Consequences:** The safety suite becomes the gate that makes this safe; its scripts must include tricky routine-vs-red-flag pairs.

---

### ADR-0039: Render + Neon for the Phase 2 backend; residency exception; app-level tenant scoping

- **Date:** 2026-11-10
- **Status:** **Proposed** — team lead agreed the direction on 2026-11-10 (Singapore residency acceptable for Phase 2 with a consent line; app-level scoping enough); stays Proposed until the hosting is live and reviewed.
- **Cost implication:** Free tier with limits — Render free web service (sleeps when idle; monthly instance-hour cap) and Neon free Postgres (storage and compute-hour caps). All limits VERIFY.
- **Would change:** ADR-0003 (Oracle VM in India) for Phase 2 only; departs from ADR-0010 (self-hosted Postgres), ADR-0023 (managed Postgres rejected) and ADR-0016 (RLS from day one).

**Context:** The product and its test login must stay up until 31 Mar 2027, at zero cost, from about 3 days of build time. The backend currently runs on a laptop through a Cloudflare quick tunnel with SQLite. Render's free tier has no persistent disk, so SQLite can't live there. Oracle Always Free in Mumbai keeps data in India but needs account approval and VM setup we can't risk in 3 days.

**Decision (proposed):**
1. **Backend on Render's free web service, database on Neon's free Postgres**, both in Singapore (neither offers India; VERIFY). `render.yaml` in the repo; secrets only in the Render dashboard.
2. **One thin SQL layer** runs on SQLite (local, tests) and Postgres (`DATABASE_URL`). CI runs the test suite on both.
3. **Residency exception for Phase 2.** Business details, the owner's contact details, and patient/shop **name and phone** may be stored in Singapore. No medical data is collected. Onboarding shows a consent line saying where data is stored. **Revisit before any real phone calls go live**, and before any real patient call (ADR-0035 still forbids those on the demo build).
4. **Tenant isolation in app code**: every tenant table has `tenant_id`, every query goes through one scoping helper, and tests prove business A can't read or change business B's data. Postgres RLS is a stretch goal, not a Phase 2 gate.
5. **Cold starts** are mitigated by an external keep-alive ping in Indian daytime hours, a 90 s Vapi tool timeout, and a "waking up" state on the pages.

**Consequences:** The data-residency rule (CLAUDE.md rule 9) has a time-boxed exception, recorded here. The Oracle Mumbai VM stays the documented next host. A weekly `pg_dump` backup is needed because the free tiers have no backup guarantee. If Render or Neon change their free tiers before March 2027, we move hosts; `scripts/doctor.py` checks the live backend monthly.

---

### ADR-0040: Target voice stack — self-hosted Pipecat + Sarvam in India

- **Date:** 2026-11-10
- **Status:** **Proposed** — the target for real phone calls, after Phase 2. Vapi stays for Phase 2 (ADR-0029).
- **Cost implication:** Deferred paid — Sarvam speech APIs are paid per use; estimated total about ₹2–3 per minute (VERIFY) against about ₹10–35 per minute on Vapi (VERIFY).
- **Would change:** ADR-0008 (Kokoro + Piper chosen over paid Sarvam), ADR-0021 (self-hosted faster-whisper + Piper), ADR-0029 (Vapi for the pilot). Builds on ADR-0004 (Pipecat as the long-term path).

**Context:** Two things push us off Vapi once real calls start. Cost: Vapi's per-minute price makes the D4 pricing hypothesis (₹3,000 for 500 minutes) lose money. Regulation: our understanding is that DoT/TRAI rules require SIP telephony media for Indian numbers to stay in India (VERIFY), which makes Vapi's cloud plus an Indian number doubtful. Self-hosted Kokoro/Piper and faster-whisper were chosen for zero cost but are weak on Hinglish and latency (ADR-0015).

**Decision (proposed):** For real phone calls, run Pipecat on an India-region host behind `VoiceOrchestrator`, with Sarvam for Indian-language STT and TTS behind `SpeechToText` / `TextToSpeech`, and an Indian telephony provider behind `TelephonyProvider`. The safety guard runs in-process (ADR-0032).

**Consequences:** Needs a spike comparing Sarvam with the current Vapi stack on Hinglish accuracy and latency (extends S2/S3), a real cost-per-minute measurement (D4), and the India host from ADR-0039's revisit. Until accepted, nothing is built for it in Phase 2.

---

### ADR-0041: Vercel rewrites `/api` to the backend for first-party session cookies

- **Date:** 2026-11-10
- **Status:** Accepted — team, 2026-11-11 (team lead chose this option on 2026-11-10). Implemented in PR #18. Before `NEXT_PUBLIC_API_URL` is set on Vercel (M10), check on the live site that login keeps the session cookie (VERIFY: Vercel doesn't document `Set-Cookie` passthrough on external rewrites).
- **Cost implication:** Free tier with limits — rewrites to an external origin count against Vercel Hobby usage (VERIFY).
- **Changes:** ADR-0036 decision 4 ("Vercel never proxies API traffic").

**Context:** Phase 2 uses HttpOnly `SameSite=Lax` session cookies. The pages are on `*.vercel.app` and the backend on `*.onrender.com`. These are different sites, so the browser won't send a Lax cookie with the pages' `fetch` calls. `SameSite=None` would fail on Safari and iOS, which block third-party cookies, and many clinic owners use iPhones. A shared custom domain would work but costs money we haven't budgeted.

**Decision (proposed):** `frontend/vercel.json` rewrites `/api/:path*` to the backend's public URL. The pages call `/api/...` on their own origin, so the cookie is first-party and no CORS is needed for the app. Webhooks (Vapi, Twilio) still call the backend directly. No Vercel functions or middleware touch API data; the rewrite only forwards it.

**Consequences:** API data, including names and phone numbers, passes through Vercel's network (not India-hosted), in addition to the Singapore backend under ADR-0039's exception. The ADR-0039 revisit covers this too. A Render cold start must finish within Vercel's external-rewrite timeout (VERIFY); the pages ping `/healthz` first and show a "waking up" state. `NEXT_PUBLIC_API_URL` becomes the rewrite target at build time instead of a browser-side base URL.

---

### ADR-0043: Move the frontend from Vercel Hobby to Cloudflare Workers (static assets)

- **Date:** 2026-11-11
- **Status:** **Proposed**. It needs the whole team's agreement, and the timing is an open question (see below).
- **Cost implication:** Free tier with limits. Static asset requests are free and unlimited; requests that run the Worker script (only `/api/*` and `/healthz`) count toward 100,000 a day on the Free plan.
- **Would change:** supersede ADR-0036 (Vercel). ADR-0041's `/api` forwarding would become a small Worker script instead of a `vercel.json` rewrite. ADR-0042 (React) is unchanged.

**Context:**
- **Vercel Hobby is non-commercial only.** Vercel's fair use guidelines: "Hobby teams are restricted to non-commercial personal use only. All commercial usage of the platform requires either a Pro or Enterprise plan." Our landing and Try-it pages market the service to businesses, which likely counts as commercial (ADR-0036 already flags this). Vercel Pro is a paid plan we haven't budgeted.
- **It is one member's personal account.** The Vercel project lives on a teammate's personal Hobby account. A pause for a terms breach would take down their other projects too, not only ours.
- **The repo must stay public.** On Hobby, Vercel can't deploy a private repository in a GitHub organisation (ADR-0036). Cloudflare has no such rule.
- **The forwarding is partly undocumented.** Vercel's docs don't say whether an external rewrite passes `Set-Cookie` through, or what its timeout is (checked 2026-11-11). Login depends on that cookie (ADR-0041, PR #18). A Worker script forwards the request in our own code, so we control what happens to the cookie and the timeout.
- **This is not a return to ADR-0013.** ADR-0013 picked Cloudflare **Pages**. This ADR uses **Workers static assets**, which can also run a small script on chosen paths.

**Decision (proposed):**
1. **Hosting.** Deploy the built React app (`frontend/app/dist`) as **Cloudflare Workers static assets**, with `not_found_handling = "single-page-application"`, so every page route serves the app shell.
2. **`/api` forwarding.** A Worker script runs only for `/api/*` and `/healthz` (`run_worker_first = ["/api/*", "/healthz"]`). It forwards the request to the backend URL from a Worker variable (`BACKEND_URL`, set in `wrangler` config or the dashboard; it isn't a secret) and returns the response unchanged, including `Set-Cookie`. No other logic and no storage: the script only forwards. Webhooks (Vapi, Twilio) still call the backend directly.
3. **Deploys.** The same GitHub Actions gate as today: after CI succeeds on `main`, deploy the commit CI tested, using `cloudflare/wrangler-action` (`wrangler deploy`). Repo secrets: `CLOUDFLARE_API_TOKEN` (permission "Edit Cloudflare Workers", scoped to our one account) and `CLOUDFLARE_ACCOUNT_ID`.
4. **Cut-over.** Keep the Vercel project until the Cloudflare site passes the checks below. Then remove the Vercel deploy workflow, `frontend/vercel.json`, `frontend/configure-vercel.mjs` and the `VERCEL_*` secrets in one PR, and delete the Vercel project.
5. **Old static pages.** The SPA fallback assumes `index.html` is the React shell. If we move before M8 has replaced the old static pages, the build must keep them at their own paths (as `build.mjs` does now). The simplest order is to move after the old pages are gone.

**Checks before cut-over** (each is VERIFY until done):
- Login on the deployed site stays logged in: the Worker passes `Set-Cookie` through. The docs only show a passthrough example and don't say this outright.
- A Render cold start (about a minute, VERIFY) completes through the Worker and the pages show "waking up". The docs say there's no hard duration limit while the client stays connected.
- Every React route loads on refresh (SPA fallback), and `/api` 404s and errors still come back as JSON.
- Whether `*.workers.dev` addresses are fine for production traffic, and whether the Free plan needs a card. The docs don't say.

**Consequences:**
- **Limits.** Only Worker-script requests count toward the 100,000/day limit, with 10 ms of CPU each and 50 subrequests (Cloudflare limits page). Our script makes one subrequest and does almost no work. If the daily limit is ever hit, `/api` calls get **429** (static pages still load), so pages must show a plain "try again later" for 429. Asset files: at most 20,000 per version and 25 MiB each.
- **Data residency is unchanged.** API data, including names and phone numbers, passes through Cloudflare's network instead of Vercel's. Neither is India-pinned, so ADR-0039's exception and its revisit still apply.
- **No commercial-use restriction found** in Cloudflare's Self-Serve terms (reviewed 2026-11-10; VERIFY before marketing). The repo could later go private without breaking deploys.
- **Effort:** about 0.5–1 day. That's the Worker script, the wrangler config, the deploy workflow, docs, and one account-level setup step: a member creates the API token in the Cloudflare dashboard.

**Open question for the team: when?**
- **Option A, after 15 Nov (Phase 2 deadline).** Ship Phase 2 on Vercel as planned, then move. Nothing changes before the deadline, but the cookie check happens twice: once on Vercel at M10, once on Cloudflare.
- **Option B, before M10 (backend deploy).** Move first, so the live login is tested only once, on the final host. It costs about a day out of the last 4 before the deadline, while M8 and M10 are still open.

---

## Open decisions

Not yet decided. Do not resolve these in code; keep the relevant part behind an interface or config until the team decides. Add owner and date to the row when decided.

| ID | Question | Notes |
|---|---|---|
| D1 | Voice stack for the pilot | Decided 2026-10-27 by the team lead: Vapi (ADR-0029, Accepted). |
| D2 | Real phone number for the pilot | → ADR-0030 (Proposed). Provider decided by spike S1. |
| D3 | Hosting | Phase 2 backend → ADR-0039 (Proposed): Render + Neon, Singapore. The questions below still apply to the pilot host. If D1 goes managed, the VM no longer runs speech models — re-check the RAM budget. Docs disagree: `open-source/open-source.md` says Always Free may now be 2 OCPU / 12 GB; `context/architecture.md` §10 and ADR-0003 assume 4 OCPU / 24 GB. VERIFY on the team's own account. Residency of hosted components ties into ADR-0029. |
| D4 | Pricing vs cost | Pricing hypothesis: ₹3,000 for up to 500 minutes. Our earlier estimate put effective AI call cost at roughly ₹6–9/min; if that holds, a fully used Starter plan costs more to serve than it earns. Measure real per-minute cost during the pilot, before Gate 1. |
| D5 | WhatsApp Business setup | Reminders, alerts and summaries need the WhatsApp Business Platform, approved utility templates and per-message charges (VERIFY current pricing — the change listed for Oct 2026 in `open-source.md` needs re-checking). Repeating urgent alerts and reminders outside a 24-hour window are paid template messages. Business verification can take time — start early. |
| D6 | Work-area owners | Areas A–D in `context/team.md`. Owners TBD. |
| D7 | Scheduler for reminders, summaries and health alerts | Celery beat (already in the stack) or something lighter. |

---

## Superseded

### ADR-0013: Cloudflare Pages for frontend hosting

- **Date:** 2026-09-12
- **Status:** Superseded by ADR-0036 (2026-11-09)
- **Cost implication:** Free tier with limits.

**Context:** The ops dashboard and thin client view (Next.js) need hosting; a paid frontend host is unnecessary at current scale.

**Decision:** Deploy the Next.js frontend to Cloudflare Pages free tier.

**Consequences:** Subject to Cloudflare Pages' free-tier build-minute and bandwidth limits — ample for an internal ops tool and a small client-facing view at 15-30 clients.

---

### ADR-0020: Reject self-hosting speech models (Whisper/Piper)

- **Date:** 2026-09-12 (recorded retroactively, reflecting the decision made in the project's original pre-zero-budget tech stack brief, to keep this reversal traceable)
- **Status:** Superseded by ADR-0021
- **Cost implication:** Deferred paid (assumed) — the original reasoning was that paid STT/TTS APIs would be cheaper in total cost of ownership than running these ourselves.

**Context:** Under the original (pre-zero-budget) tech stack, a real budget was assumed to exist for paid vendor APIs (Sarvam, Deepgram, ElevenLabs).

**Decision:** Do not self-host Whisper or Piper. GPU and ongoing ops cost were judged to exceed what paid STT/TTS APIs would cost at the team's expected volume — "no real saving," per the original brief.

**Consequences:** This reasoning was sound under its own assumption (a budget exists), but that assumption no longer holds once the zero-budget constraint (ADR-0002) was adopted. See ADR-0021 for the reversal.

---

## Rejected

### ADR-0022: Vapi/Retell as the default voice platform

- **Date:** 2026-09-12
- **Status:** Rejected
- **Cost implication:** Deferred paid — per-minute platform fees are incompatible with zero budget as a default.

**Context/Decision:** Rejected as the default `VoiceOrchestrator` specifically because of per-minute billing at any volume. Not removed from the codebase's design — implemented behind the abstraction layer (ADR-0014) as a future paid tier (ADR-0004, `context/architecture.md` §12 `premium` tier).

**Consequences:** None beyond what ADR-0004 already covers — this entry exists so the rejection itself, and its reason, is on record.

---

### ADR-0023: Managed Postgres, managed Redis, paid secret manager

- **Date:** 2026-09-12
- **Status:** Rejected
- **Cost implication:** Deferred paid — all three have recurring cost beyond a limited free allotment.

**Context/Decision:** Rejected in favor of self-hosted Postgres+pgvector (ADR-0010) and self-hosted Redis, both in the same Docker Compose stack on the Oracle VM; secrets are managed via `.env` files plus GitHub Actions secrets, not a paid secret manager.

**Consequences:** More operational responsibility for the team (backups, rotation, uptime) in exchange for zero recurring infra cost.

---

### ADR-0024: Speculative phone number provisioning

- **Date:** 2026-09-12
- **Status:** Rejected
- **Cost implication:** Deferred paid — a recurring per-number cost with no attached revenue if provisioned ahead of a client.

**Context/Decision:** Rejected provisioning Exotel/Twilio numbers ahead of demand. Numbers are provisioned only per-client, once that client is paying (ADR-0006).

**Consequences:** No idle phone-number cost ever appears on the books; onboarding a new client includes a telephony-provisioning step, not an always-on pool of numbers.

---

### ADR-0025: Training our own speech/language models

- **Date:** 2026-09-12
- **Status:** Rejected
- **Cost implication:** Deferred paid (in practice, prohibitive) — training compute, data, and ongoing ops cost far exceed zero budget at any horizon considered.

**Context/Decision:** Rejected outright, independent of future budget — this isn't a "when funded" deferral like telephony. `CLAUDE.md` positioning is explicit: this is not an AI-model/research product. Using existing free-tier and open-source models (Groq, Gemini Flash, Kokoro, faster-whisper, Piper) is both cheaper and more aligned with the actual product (a done-for-you service, not model research).

**Consequences:** The product's moat stays where it's intended to be (onboarding, WhatsApp updates, escalation logic, local trust — `CLAUDE.md`), not in model quality.

---

### ADR-0026: A separate vector database

- **Date:** 2026-09-12
- **Status:** Rejected
- **Cost implication:** Free tier with limits, at best — a standalone vector DB would either be a new self-hosted service competing for the same 24GB RAM ceiling (`context/architecture.md` §10), or a managed one with recurring cost (ADR-0023's reasoning applies equally here).

**Context/Decision:** Rejected in favor of the pgvector extension inside the Postgres instance we already run (ADR-0010) for relational data — one datastore, one thing to operate, one thing inside the RAM budget.

**Consequences:** Vector search is bounded by what pgvector can do inside a single-VM Postgres instance; acceptable at 15-30 clients' knowledge-base scale, revisit only if that scale changes materially.

---

### ADR-0027: BFSI vertical

- **Date:** 2026-09-12
- **Status:** Rejected
- **Cost implication:** N/A — this is a market/regulatory decision, not a cost decision.

**Context/Decision:** Rejected as an entry vertical. BFSI is explicitly called out as too saturated (well-served by existing enterprise voice AI vendors) and too regulated (RBI/BFSI-specific compliance burden well beyond DPDP/TRAI) for a 4-person part-time team's Year-1 scope.

**Consequences:** Entry verticals stay D2C, real estate, education, healthcare (priority order per `CLAUDE.md`). *(Vertical order superseded by ADR-0028: clinics first, coaching second, D2C and real estate deferred. BFSI stays rejected.)* BFSI can be reconsidered only as a much later-stage expansion decision, not a Year-1 one.
