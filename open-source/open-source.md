# Open Source & Free-Tier Dependencies

This project is built almost entirely on open source and free-tier hosted services because the team has zero budget (`context/decisions.md` ADR-0002). This document is where *why* a dependency was chosen, its license, its cost profile, and its free-tier ceiling live — information a `requirements.txt`/`package.json` lockfile doesn't capture.

## Current state

No application code exists in the repository yet (no lockfile/manifest to point to), but the dependencies below are decided (`CLAUDE.md`, `context/decisions.md`) and documented here ahead of implementation, so license and cost tradeoffs are on record before the first line of code depends on them.

## ⚠️ Recent changes to watch

These surfaced during research for this document (verified externally, not from memory) and affect assumptions already baked into other docs in this repo:

- **Oracle Cloud Always Free ARM allocation was reduced** in mid-2026 from 4 OCPUs/24GB RAM to **2 OCPUs/12GB RAM** (200GB block storage unchanged). `context/architecture.md` §10's RAM budget (~13.1GB estimated usage) was written against the old 24GB figure and needs revisiting against the new ceiling — flagged, not yet fixed, as of this document.
- **Meta WhatsApp Cloud API moved to per-message pricing** in July 2025 (with another change scheduled Oct 2026). It is not simply "free" the way earlier docs assumed — see `open-source/integrations/integrations.md` for detail.
- **Redis's license depends heavily on version.** ≤7.2 is BSD-3-Clause; 7.4+ is RSAL/SSPL/AGPL tri-licensed (only AGPLv3 is OSI-approved). Pin the version you actually deploy and re-check this table against it.
- **Piper's license differs by fork.** The original `rhasspy/piper` (MIT) is archived; the actively maintained successor `OHF-Voice/piper1-gpl` is GPL-3.0. Confirm which fork is actually vendored before treating Piper as permissively licensed.
- **Google Gemini's free-tier limits are not fixed** — Google publishes them only via the live AI Studio console, not a stable table. Don't hardcode a number from this document into code or a client-facing SLA.

## Standing rule

**Before adding any dependency, check two things and record both in this file: (1) its license, and (2) whether it has a hard free ceiling.** A dependency that's free today but meters usage (API calls, storage, compute minutes) needs its ceiling and at-limit behavior documented in Table 2 below; a dependency with a copyleft or otherwise non-permissive license needs that flagged here even if it costs nothing, per `context/coding-rules.md`. Neither check is satisfied by "it's on the approved stack list" — the stack list says *what*, this file has to say *why it's safe to depend on*.

---

## 1. Self-hosted open source in active use

| Component | License | What it replaces | What it would cost if paid | arm64 support |
|---|---|---|---|---|
| Pipecat | BSD 2-Clause | Vapi/Retell managed voice orchestration | Vapi ~$0.05/min platform fee; Retell ~$0.055-0.07/min (both realistically $0.10-0.30+/min all-in with STT/LLM/TTS) | Python framework — compatible via its dependencies; verify each transport/plugin dependency individually rather than assuming |
| faster-whisper | MIT (SYSTRAN); CTranslate2 (OpenNMT) MIT; underlying Whisper model MIT | Deepgram/Sarvam paid STT | Deepgram ~$0.0043-0.0077/min; Sarvam ~₹30/hr (~₹0.50/min) | CTranslate2 wheel availability for aarch64 not confirmed — verify before committing to this image (`context/architecture.md` §10) |
| Kokoro TTS | Apache 2.0 | ElevenLabs/Sarvam paid TTS (English) | ElevenLabs $6-990+/month tiers; Sarvam TTS ₹30/10,000 chars | ONNX/torch runtime — verify aarch64 wheel availability before deploy |
| Piper | ⚠️ split by fork — MIT (`rhasspy/piper`, archived) vs **GPL-3.0** (`OHF-Voice/piper1-gpl`, actively maintained) | Sarvam/ElevenLabs paid TTS (Hindi/Hinglish) | same as Kokoro row above | Lightweight ONNX voices; generally good arm64 history, confirm against whichever fork is actually vendored |
| FastAPI | MIT | N/A — framework, no direct paid equivalent | N/A | Pure Python, fully compatible |
| pgvector | PostgreSQL License | A separate managed vector DB | Varies by vendor (e.g. a managed vector DB's starter tier) | Compiles fine; official Postgres images are multi-arch |
| PostgreSQL | PostgreSQL License | Supabase / managed Postgres | Supabase Pro from $25/month | Official image is multi-arch |
| Redis | ⚠️ tri-licensed as of 8.0 — RSALv2 / SSPLv1 / AGPLv3 (only AGPLv3 is OSI-approved); ≤7.2 was BSD-3-Clause. Consider **Valkey** (BSD-3-Clause, Linux Foundation fork) if a permissive license matters more than staying on Redis proper. | A managed Redis (e.g. Upstash) | Varies by vendor | Official image (and Valkey) multi-arch |
| Celery | BSD 3-Clause | A managed task queue | Varies | Pure Python, compatible |
| Langfuse | MIT (core); ⚠️ enterprise (`/ee`) features require a paid license key even when self-hosted | Langfuse Cloud | Langfuse Cloud paid tiers | Not confirmed in research — verify the self-host Docker image publishes an arm64 build before deploy |
| Caddy | Apache 2.0 | A paid reverse proxy / managed TLS service | N/A | Native arm64 Go binary |
| Docker (Engine + Compose) | Apache 2.0 (Engine, Compose). Docker Desktop is separately licensed (proprietary EULA) — not used here; we run Engine directly on a Linux VM. | A paid container platform | N/A | Fully supported |

---

## 2. Free-tier hosted services in use

| Service | Exact free limit | What happens at the limit | Our fallback | Card required? |
|---|---|---|---|---|
| Groq | Whisper large-v3-turbo: 20 RPM / 2,000 RPD / 7,200 audio-sec per hour / 28,800 audio-sec per day. Llama 3.1 8B Instant: 30 RPM / 14,400 RPD / 6,000 TPM / 500K TPD. Llama 3.3 70B: 30 RPM / 1,000 RPD / 12,000 TPM / 100K TPD. | HTTP 429 | Self-hosted faster-whisper for STT (`context/architecture.md` §13); Cerebras or queued retry for LLM | Not confirmed — verify at signup |
| Google Gemini Flash | ⚠️ Not fixed — Google publishes only via the live console, not a stable table; secondary sources cite ~10 RPM / 250K TPM / 500-1,500 RPD depending on model version. **Check the live console, don't hardcode this number.** | Request throttled/rejected | Queue via Celery and retry later — offline processing (WhatsApp parsing, embeddings) tolerates delay | Not confirmed |
| Cloudflare R2 | 10GB-month storage, 1M Class A ops/month, 10M Class B ops/month, $0 egress always | No hard cutoff — pay-as-you-go billing begins automatically beyond the free allocation | 30-day audio lifecycle rule + usage monitoring to stay under 10GB (`context/architecture.md` §7, §13) | Yes — R2 requires billing details on file even to use the free allocation, unlike most other Cloudflare free products |
| Cloudflare Pages | 500 builds/month, unlimited bandwidth, 20,000 files/site, 25MiB max asset size | Builds queue/fail until next month | Reduce build frequency; build locally and push static output if needed | Not required |
| Meta WhatsApp Cloud API | ⚠️ Not a flat free tier — per-message pricing since July 2025; free only inside a customer-opened 24-hour service window or a 72-hour click-to-WhatsApp ad entry. Another pricing change is scheduled for Oct 2026. | Not a quota — messages outside the free windows are billed per message | Keep confirmation messages inside owner-opened windows where possible; budget a small ongoing per-message cost, don't assume $0 (see `open-source/integrations/integrations.md`) | Yes — production use requires a Meta Business payment method on file |
| Sentry | 5,000 errors/month (Developer plan), separately metered spans/replays/logs/attachments | Events dropped/sampled until next cycle | Reduce sampling rate, prioritize error capture over trace volume | Not required for Developer plan |
| PostHog | 1,000,000 events/month | Ingestion stops (or bills, if pay-as-you-go is enabled) until reset | Reduce event volume / sample | Not required to start |
| GitHub Actions | 2,000 min/month (private repos; unlimited for public repos); OS multipliers Linux 1x / Windows 2x / macOS 10x | Workflow runs blocked until next cycle or a card is added | Linux-only runners (cheapest multiplier), reduce CI frequency | Not required unless exceeding free minutes |
| Oracle Cloud Always Free | ⚠️ **Reduced mid-2026** to 2 OCPUs / 12GB RAM (down from the 4 OCPU/24GB figure most existing tutorials and this project's own earlier docs cite), 200GB block storage. ARM capacity is frequently exhausted regionally. | Cannot provision additional Always Free resources; existing resources keep running | None within the zero-budget constraint — see the retry approach in `context/roadmap.md` Phase 0 | Yes — Oracle requires a card for identity verification, but should not charge if usage stays within Always Free limits |

---

## 3. Paid alternatives deliberately deferred

| Alternative | What it would improve | Approximate cost | Trigger condition to adopt |
|---|---|---|---|
| Vapi | Voice orchestration reliability/features vs. self-hosted Pipecat | ~$0.05/min platform fee (~$0.10-0.30+/min all-in) | A client's call volume/reliability needs exceed self-hosted Pipecat, funded by that client's `cost_tier` (`context/architecture.md` §12) |
| Retell AI | Same as Vapi; alternate orchestration vendor for redundancy | ~$0.055-0.07/min base (~$0.07-0.31/min all-in) | Same as Vapi |
| Sarvam AI | STT/TTS quality for Indic languages vs. Groq/Piper | STT ~₹30/hr (~₹0.50/min); TTS ~₹30/10,000 chars | A client's language/accent needs exceed Groq+Piper quality, funded by that client's tier |
| Deepgram | English STT accuracy/latency vs. Groq/faster-whisper | Batch ~$0.0043/min; streaming ~$0.0077/min | Groq free-tier STT quality/latency becomes the limiting factor for a paying client |
| ElevenLabs | English TTS quality/prosody vs. Kokoro | Subscription tiers $6-990+/month by volume | A premium client's voice-quality bar exceeds Kokoro/Piper |
| Exotel | Real India PSTN number with DLT/DND support | No public per-minute rate — quote-based prepaid credit bundles; third-party estimates ~₹0.60-1.80/min outbound | First paying client needing a real phone number (ADR-0006); cost billed through to them |
| Twilio | Alternate PSTN provider to Exotel | India mobile outbound ~$0.0496/min, landline ~$0.0699/min, +$2/month per number | Same trigger as Exotel; kept as a fallback `TelephonyProvider` |
| Supabase | Managed Postgres+pgvector, offloads our own DB ops burden | Free tier pauses after 7 days inactivity (500MB/project); Pro from $25/month | Self-hosted Postgres ops burden becomes unsustainable at scale and revenue justifies offloading it — note this was an explicit *rejected* decision (ADR-0010/ADR-0023), not merely deferred; reconsidering it is a deliberate reopening, not a default next step |

---

## See Also

- `context/decisions.md` — the ADRs behind each choice above (search for the component name).
- `context/architecture.md` §10, §12, §13 — deployment topology, cost-tier config, free-tier guardrails.
- `open-source/integrations/integrations.md` — deeper integration detail (auth, rate limits, sandbox, failure modes, fallback) for the external API integrations named above.
- `context/coding-rules.md` — the license-check rule as it applies to new code dependencies generally.
