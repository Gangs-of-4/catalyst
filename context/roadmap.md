# Roadmap

Phased execution plan for Voice AI for Business. Cross-references: `CLAUDE.md` (stack, positioning), `context/architecture.md` (system design), `context/decisions.md` (ADRs behind these choices).

**Money discipline applies throughout** (`context/decisions.md` ADR-0002): every task below that requires spending money is marked 💰 and states exactly what unblocks it. Nothing marked 💰 is scheduled to happen "soon" by default — it happens when its stated unblock condition is met, not before.

> **Note on scope:** Phase 0 is specified in full detail below. Phases 1-3 are a proposed sequencing built from decisions already on record (inbound-first, WhatsApp test-number-then-production, entry-vertical priority order, telephony/DLT deferral) — flag anything here you want reordered or rescoped; they weren't separately specified and shouldn't be read as equally locked-in as Phase 0 and Phase 4.

---

## Phase 0 — Zero-cost foundation (Week 1-2)

- **Claim an Oracle Cloud Always Free ARM instance** in Mumbai or Hyderabad. **This task blocks everything else** — nothing in this phase or beyond can start until compute exists. ARM (Ampere A1) Always Free capacity is frequently exhausted in Indian regions; treat "capacity unavailable" as expected, not a failure. Retry approach: run an automated script that repeatedly attempts instance creation across both eligible regions/availability domains on a short interval (e.g. every few minutes) until one succeeds, rather than manually retrying in the console. If capacity cannot be claimed within a few days, escalate it as a blocking risk to the team — do not substitute a paid instance as a workaround; that would violate ADR-0002.
- **Claim the GitHub Student Developer Pack** for the team (free domain, extra credits) — free, no blocker, do in parallel with the above while waiting on ARM capacity.
- **Docker Compose stack on the VM:** Postgres+pgvector, Redis, Caddy (reverse proxy with automatic free TLS), Langfuse — per `context/architecture.md` §10.
- **Postgres schema with `tenant_id` and RLS** from the first migration (ADR-0016) — not retrofitted later.
- **Provider interfaces defined, with one free implementation each:** Groq STT, Groq LLM, Kokoro TTS, Piper Hindi TTS — the `SpeechToText`/`LLMProvider`/`TextToSpeech` interfaces (`context/architecture.md` §2) exist even though only one implementation each exists yet; this is what makes Phase 3's paid upgrades a config change later.
- **Pipecat running a WebRTC voice loop end to end in the browser.** No phone number, no paid service, no credit card used anywhere in this phase.
- **Measure and record actual round-trip latency as the baseline** — compare against the ~1.2-2s estimate in `context/architecture.md` §11; if reality differs, that estimate gets corrected, not defended.

**Definition of done for Phase 0:** a browser-based voice conversation works end to end on free infrastructure, and the team has spent zero rupees.

---

## Phase 1 — First vertical, first design partners (proposed)

Goal: prove the product loop (agent handles a real conversation, owner updates knowledge via WhatsApp, escalation fires correctly) with real design partners, still entirely on the Phase 0 free stack — no telephony, no paid services.

- Pick the first entry vertical to build for (D2C e-commerce, per the stated priority order in `CLAUDE.md`) and scaffold it via `/new-vertical` once that command exists: agent prompt, escalation rule pack, onboarding question set, seed knowledge base.
- Build the WhatsApp knowledge-update ingestion pipeline (`context/architecture.md` §4) against the **free WhatsApp test number** — extraction → mandatory owner confirmation → write → re-embed (ADR-0017).
- Build the escalation engine (`context/architecture.md` §5) for this one vertical: rule pack + the global uncertainty rule, with adversarial transcript test fixtures (`context/coding-rules.md`).
- Onboard 1-3 unpaid design-partner businesses in this vertical, running calls over WebRTC (no phone number needed yet — design partners can talk to the agent in-browser or via a shared link).
- Validate multi-tenancy with more than one real tenant (not just schema-level RLS, but actual concurrent tenants exercising it).

**Definition of done:** at least one real (unpaid) design-partner business is using the agent for real inbound conversations, with WhatsApp-driven knowledge updates working end to end, entirely on free infrastructure.

---

## Phase 2 — First paying clients (proposed)

Goal: convert design partners (or new prospects) into paying clients, which is what unlocks the money-gated infrastructure this product actually needs to feel "real" to a business owner (a phone number, a production WhatsApp number).

- 💰 **Phone number provisioning (Exotel/Twilio)** — blocked on first paying client (ADR-0006, ADR-0024). Provisioned per-client only once that client is paying; cost billed through to them, not absorbed.
- 💰 **WhatsApp production number / business verification** — use the free test number (from Phase 0/1) until a paying client needs a real, branded WhatsApp presence; move to production verification at that point, not speculatively.
- Exercise the `agent_configs.cost_tier` mechanism for the first time: move a paying client from `free` to `standard` (`context/architecture.md` §12) — telephony added, voice stack still free-tier components.
- Client onboarding process (non-technical owner, zero-config) gets its first real-world test under paying-client stakes, not just design-partner goodwill.

**Definition of done:** at least one client is paying, has a real phone number routing to the agent, and the `cost_tier` upgrade from `free` to `standard` happened as a config change, not a code change.

---

## Phase 3 — Multi-vertical scale (proposed)

Goal: extend from one vertical and a handful of clients toward the Year-1 target (15-30 clients) across the remaining entry verticals, in priority order (real estate, education, healthcare).

- Scaffold and validate escalation rule packs per additional vertical (real estate: negotiation/price/legal; education: fee negotiation; healthcare: admin-only with hard emergency/symptom escalation — `context/architecture.md` §5).
- Healthcare vertical specifically requires the clinical-advice guard layer (`context/coding-rules.md`) to be in place and tested before any healthcare client goes live — this is a harder gate than the others, not a checkbox.
- 💰 **Any paid STT/TTS upgrade** (Sarvam/Deepgram, ElevenLabs, or Vapi/Retell for voice orchestration) — post-revenue, and implemented purely as a `cost_tier` config change (ADR-0014) for clients whose volume or quality needs justify it. No architecture change, no rewrite.
- Cost reporting (`/cost-report`) becomes operationally important here — with multiple tenants on a mix of `free`/`standard`/`premium` tiers, per-tenant cost visibility is what tells the team when an upgrade is actually justified.
- Observability maturity: Langfuse trace review becomes a routine part of quality control across verticals, not just a debugging tool.

**Definition of done:** clients are live across at least two additional verticals beyond the first, with per-vertical escalation packs tested, and the healthcare guard layer verified before any healthcare client goes live.

---

## Phase 4 — Outbound lead follow-up — 💰 blocked on DLT registration

Goal: enable outbound calling (D2C lead follow-up/COD-RTO reduction, real estate speed-to-lead, education coaching follow-up), which is explicitly out of reach until this phase's blocking prerequisite is funded and completed.

- 💰 **TRAI DLT Principal Entity registration is the gate for this entire phase** (ADR-0019). It is a paid prerequisite; the outbound pipeline ships with a fail-closed gate (`context/architecture.md` §6) that blocks dispatch by default, regardless of when engineering work on this phase starts. Engineering can build and test the pipeline against the gate before registration completes — it simply cannot dispatch a real outbound call until the gate is satisfied.
- Build the outbound Celery queue with calling-window enforcement (9 AM-9 PM IST, checked at dispatch time, not enqueue time), DND scrubbing, consent checks, and the bounded retry policy (`context/architecture.md` §6) — all of which stay enforced independently of the DLT gate, before and after registration.
- Once registered: enable outbound for the highest-priority use case first (D2C COD/RTO reduction, per `CLAUDE.md` vertical priority), then extend to real estate and education follow-up.
- Likely mandatory AI-disclosure at commercial call start (expected 2026-27, `context/architecture.md`) should be implemented ahead of when it becomes mandatory, not reactively once it is.

**Definition of done:** DLT Principal Entity registration is complete, the outbound pipeline has been dispatching real calls under full calling-window/DND/consent enforcement with zero violations, and at least one client is receiving outbound lead follow-up.

---

## Money-Gated Tasks — Quick Reference

| Task | Phase | Unblocked by |
|---|---|---|
| Phone number provisioning (Exotel/Twilio) | Phase 2+ | first paying client (cost billed through to them, ADR-0006) |
| WhatsApp production number / business verification | Phase 2 | a client needing a real branded WhatsApp presence; free test number used until then |
| Any paid STT/TTS/voice-orchestration upgrade (Sarvam, Deepgram, ElevenLabs, Vapi, Retell) | Phase 3+ | post-revenue, applied as a `cost_tier` config change only (ADR-0014) |
| TRAI DLT Principal Entity registration | Phase 4 | funded once outbound revenue justifies it; gates all of Phase 4, fail-closed by default |

Not money-gated, but capacity-gated: the Phase 0 Oracle Cloud ARM instance claim is blocked on Oracle's Always Free capacity availability, not on money — see Phase 0's retry approach above.
