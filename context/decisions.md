# Architecture Decisions

ADR log for Catalyst. One entry per significant, actually-made decision — never backfilled invented history. Every entry states a **cost implication** explicitly, because the team operates under a zero-budget constraint (ADR-0002): `Free` (no recurring cost), `Free tier with limits` (free today, bounded by a quota/ceiling), or `Deferred paid` (a real cost, intentionally pushed to when a paying client funds it).

**Format:** ID · Date · Status · Cost implication · Context · Decision · Consequences.

**Statuses:** `Accepted` · `Proposed` (written down, awaiting team approval — do not build on it as if settled) · `Superseded` · `Rejected`. ADRs are never deleted; a reversal is a new ADR. If a change would reverse an Accepted ADR, write it as **Proposed**.

**Open decisions** (not yet ADRs) are at the bottom: D3–D7. D1 and D2 are Proposed ADRs (ADR-0029, ADR-0030).

**Path note (2026-10-26):** older ADRs say `src/...`. The layout is now `backend/src/...` everywhere (e.g. `backend/src/providers/`). Section numbers (`architecture.md` §N) in ADRs dated before 2026-10-26 refer to the earlier architecture doc; see git history.

## Index

| ID | Title | Status | Cost implication |
|---|---|---|---|
| ADR-0001 | Adopt a Claude Code context-engineering structure | Accepted | Free |
| ADR-0002 | Zero-budget as a binding architectural constraint | Accepted — *challenged by ADR-0029, ADR-0030 (Proposed)* | Free |
| ADR-0003 | Oracle Cloud Always Free as the single production host | Accepted — *RAM figure disputed, see D3* | Free tier with limits |
| ADR-0004 | Self-hosted Pipecat over paid Vapi/Retell | Accepted — *challenged by ADR-0029 (Proposed)* | Free |
| ADR-0005 | WebRTC-first development; PSTN deferred | Accepted — *challenged by ADR-0030 (Proposed)* | Free |
| ADR-0006 | Telephony cost passed through per-client | Accepted — *challenged by ADR-0030 (Proposed)* | Deferred paid |
| ADR-0007 | Groq free tier for live-call STT and LLM | Accepted | Free tier with limits |
| ADR-0008 | Kokoro + Piper for TTS over paid Sarvam/ElevenLabs | Accepted | Free |
| ADR-0009 | Gemini Flash free tier for offline parsing and embeddings | Accepted | Free tier with limits |
| ADR-0010 | Self-hosted Postgres + pgvector over Supabase/managed DB | Accepted | Free |
| ADR-0011 | Self-hosted Langfuse over Langfuse Cloud | Accepted | Free |
| ADR-0012 | Cloudflare R2 free tier, 30-day audio lifecycle | Accepted | Free tier with limits |
| ADR-0013 | Cloudflare Pages for frontend hosting | Accepted | Free tier with limits |
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
| ADR-0029 | Managed voice platform for the pilot behind `VoiceOrchestrator` (D1) | **Proposed** | Deferred paid → paid during pilot |
| ADR-0030 | One team-funded phone number for the pilot (D2) | **Proposed** | Paid during pilot |
| ADR-0031 | Clinic escalation by doctor-approved red-flag list, not "any symptom" | **Proposed** | Free |
| ADR-0032 | Backend owns the brain: agent tools API, safety guard in our code | Accepted | Free |
| ADR-0033 | Verticals are config; generic booking model with exclusion constraint | Accepted | Free |
| ADR-0034 | WhatsApp is its own channel module; preview-and-confirm on every write | Accepted — extends ADR-0017 | Free tier with limits (per-message pricing, D5) |

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

### ADR-0013: Cloudflare Pages for frontend hosting

- **Date:** 2026-09-12
- **Status:** Accepted
- **Cost implication:** Free tier with limits.

**Context:** The ops dashboard and thin client view (Next.js) need hosting; a paid frontend host is unnecessary at current scale.

**Decision:** Deploy the Next.js frontend to Cloudflare Pages free tier.

**Consequences:** Subject to Cloudflare Pages' free-tier build-minute and bandwidth limits — ample for an internal ops tool and a small client-facing view at 15-30 clients.

---

### ADR-0014: Provider abstraction layer as the free-to-paid migration mechanism

- **Date:** 2026-09-12
- **Status:** Accepted
- **Cost implication:** Free to build (engineering time only) — its entire purpose is making future `Deferred paid` upgrades cheap.

**Context:** Nearly every default choice above (Pipecat, Groq, Kokoro/Piper, self-hosted Postgres) is free specifically because of zero budget, not because it's the best long-term choice. Voice AI vendor choice is not our differentiation (`CLAUDE.md` positioning) — so being stuck with today's free-tier vendor would be a self-inflicted, avoidable risk.

**Decision:** Every voice, STT, TTS, and LLM provider sits behind our own interface in `src/providers/` (`VoiceOrchestrator`, `SpeechToText`, `TextToSpeech`, `LLMProvider`, `TelephonyProvider` — see `context/architecture.md` §2). No vendor SDK is imported outside that directory. Provider selection is resolved per-tenant at runtime from `agent_configs.cost_tier`.

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

## Proposed

These need team approval. Until approved, the Accepted ADRs they challenge still stand — but build behind the interfaces so either outcome works.

### ADR-0029: Managed voice platform for the pilot behind `VoiceOrchestrator` (D1)

- **Date:** 2026-10-26
- **Status:** **Proposed**
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
- **Status:** **Proposed**
- **Cost implication:** Paid during the pilot, owned by the team (VERIFY provider pricing).
- **Would change:** ADR-0002 (paid costs passed through, not absorbed), ADR-0005 (WebRTC-first), ADR-0006 (per-client, once paying), ADR-0024 (no speculative numbers).

**Context:** Item 1 (C1) needs a real number before the clinic pays. Missed calls on the clinic's own number cannot be proven over WebRTC, so the pilot cannot show value without one.

**Recommendation:** One pilot number, cost owned by the team during the pilot. Spike S1 decides the provider (and whether an Indian provider such as Exotel must sit between the SIM/landline and the voice stack; VERIFY the regulatory side).

**Consequences if accepted:** ADR-0024's rule still holds for everything beyond this one number. At Gate 1 the cost moves to the clinic per ADR-0006.

---

### ADR-0031: Clinic escalation by doctor-approved red-flag list, not "any symptom"

- **Date:** 2026-10-26
- **Status:** **Proposed** — loosens a documented safety rule, so it needs explicit team approval.
- **Cost implication:** Free.
- **Would change:** the old healthcare rule ("any symptom description → immediate hard escalation, no exceptions") previously in `context/architecture.md` §5 and `.claude/skills/skills.md`.

**Context:** Most clinic calls mention a reason ("daant mein dard hai"). Escalating every one would flood the doctor and defeat the product. Discovery showed routine reasons should just book.

**Decision (proposed):** The agent still never gives diagnosis, medicine or dosage advice — enforced by the guard in code. Routine reasons book. Only the doctor-approved red-flag list (`verticals/clinic/escalation-rules.yaml`) escalates; **grey-zone calls count as medical and escalate**. After hours, the approved emergency instruction is given. The 50+ call safety suite must pass at 100% before go-live and after every prompt or rule change.

**Consequences:** The safety suite becomes the gate that makes this safe; its scripts must include tricky routine-vs-red-flag pairs.

---

## Open decisions

Not yet decided. Do not resolve these in code; keep the relevant part behind an interface or config until the team decides. Add owner and date to the row when decided.

| ID | Question | Notes |
|---|---|---|
| D1 | Voice stack for the pilot | → ADR-0029 (Proposed). |
| D2 | Real phone number for the pilot | → ADR-0030 (Proposed). Provider decided by spike S1. |
| D3 | Hosting | If D1 goes managed, the VM no longer runs speech models — re-check the RAM budget. Docs disagree: `open-source/open-source.md` says Always Free may now be 2 OCPU / 12 GB; `context/architecture.md` §10 and ADR-0003 assume 4 OCPU / 24 GB. VERIFY on the team's own account. Residency of hosted components ties into ADR-0029. |
| D4 | Pricing vs cost | Pricing hypothesis: ₹3,000 for up to 500 minutes. Our earlier estimate put effective AI call cost at roughly ₹6–9/min; if that holds, a fully used Starter plan costs more to serve than it earns. Measure real per-minute cost during the pilot, before Gate 1. |
| D5 | WhatsApp Business setup | Reminders, alerts and summaries need the WhatsApp Business Platform, approved utility templates and per-message charges (VERIFY current pricing — the change listed for Oct 2026 in `open-source.md` needs re-checking). Repeating urgent alerts and reminders outside a 24-hour window are paid template messages. Business verification can take time — start early. |
| D6 | Work-area owners | Areas A–D in `context/team.md`. Owners TBD. |
| D7 | Scheduler for reminders, summaries and health alerts | Celery beat (already in the stack) or something lighter. |

---

## Superseded

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
