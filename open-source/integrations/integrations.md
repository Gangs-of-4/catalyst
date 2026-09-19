# Integrations

Detailed reference for each significant external integration: purpose, auth method, rate limits, sandbox availability, failure modes, and our fallback. For license/cost/free-tier framing, see `open-source/open-source.md` instead — this file is about *how the integration behaves*, not why it was chosen.

Most of these are **not yet active** — they're documented ahead of implementation because several are deliberately deferred paid alternatives (`context/decisions.md`), and the provider abstraction layer (`context/architecture.md` §2) is designed so any of them can be switched on later as a config change. Status is called out per entry.

## Vapi

- **Status:** Deferred (paid tier) — not integrated. Behind `VoiceOrchestrator` per ADR-0004/ADR-0022.
- **Purpose:** managed voice orchestration (turn-taking, interruption handling, provider glue) as a premium alternative to self-hosted Pipecat.
- **Auth method:** API key, Bearer token.
- **Rate limits:** not yet evaluated against our volume — check Vapi's current documented limits at implementation time, not from memory.
- **Sandbox availability:** dashboard-based test calls available without a production commitment.
- **Failure modes:** platform outage; per-minute billing spike from a misconfigured retry loop; vendor lock-in if ever called outside `src/providers/` (structurally prevented by the abstraction layer).
- **Our fallback:** self-hosted Pipecat, the default `VoiceOrchestrator` — switching is a `cost_tier` config change, not a rewrite.

## Retell AI

- **Status:** Deferred (paid tier) — not integrated. Kept as a second `VoiceOrchestrator` option for vendor redundancy, not just a Vapi alternative.
- **Purpose:** alternative managed voice orchestration vendor.
- **Auth method:** API key.
- **Rate limits:** not yet evaluated — check at implementation time.
- **Sandbox availability:** dashboard test calls available pre-production.
- **Failure modes:** same category as Vapi — outage, cost spike, lock-in if the abstraction boundary is bypassed.
- **Our fallback:** Pipecat (self-hosted) or Vapi, whichever is configured as primary for that tenant.

## Exotel

- **Status:** Deferred (paid tier) — additionally gated by TRAI DLT registration for outbound (ADR-0019) and by per-client provisioning (ADR-0006). Not integrated.
- **Purpose:** India-native PSTN telephony with built-in DLT/DND support, behind `TelephonyProvider`.
- **Auth method:** API Key + API Token (HTTP Basic Auth), scoped to an Exotel account Sid.
- **Rate limits:** not publicly documented in detail by Exotel — confirm with their account team at provisioning time, per-client.
- **Sandbox availability:** trial credits available on signup for pre-commitment evaluation.
- **Failure modes:** call-setup failure, a DLT template mismatch rejecting the call, regional carrier issues.
- **Our fallback:** Twilio as an alternate `TelephonyProvider` implementation, or WebRTC-only operation for tenants without a provisioned number yet.

## Sarvam AI

- **Status:** Deferred (paid tier) — not integrated. Would upgrade Indic-language STT/TTS quality over the free-tier default.
- **Purpose:** higher-quality Hindi/Hinglish (and other Indic-language) STT/TTS than Groq/Piper.
- **Auth method:** API key (subscription-key header per Sarvam's API).
- **Rate limits:** plan-dependent — verify current tier limits before relying on a specific number.
- **Sandbox availability:** a trial/evaluation API tier is offered — verify current terms at signup, they may have changed.
- **Failure modes:** API latency/outage; cost overrun if a `cost_tier` misconfiguration accidentally routes free-tier traffic through paid Sarvam.
- **Our fallback:** Groq (`SpeechToText`) / Piper (`TextToSpeech`) free-tier defaults.

## Deepgram

- **Status:** Deferred (paid tier) — not integrated. Would upgrade English STT quality/latency.
- **Purpose:** alternative to Groq Whisper for English STT when quality/latency matters more than free-tier cost.
- **Auth method:** API key.
- **Rate limits:** plan-dependent.
- **Sandbox availability:** free trial credits offered for new accounts.
- **Failure modes:** API outage; cost overrun (billed per-minute for both batch and streaming modes).
- **Our fallback:** Groq Whisper, or self-hosted faster-whisper as a further fallback.

## ElevenLabs

- **Status:** Deferred (paid tier) — not integrated. Would upgrade premium English TTS.
- **Purpose:** higher-fidelity, more natural English voice synthesis than Kokoro.
- **Auth method:** API key.
- **Rate limits:** credit-based; monthly allowance determined by subscription tier.
- **Sandbox availability:** a free tier exists (limited credits) — suitable for evaluation, not production call volume.
- **Failure modes:** API outage; credit exhaustion mid-billing-cycle for a client already relying on it.
- **Our fallback:** Kokoro TTS, the self-hosted default.

## Meta WhatsApp Cloud API

- **Status:** **Active** — this is the core knowledge-update and owner-communication channel (`context/architecture.md` §4), not deferred.
- **Purpose:** inbound webhook for owner WhatsApp messages (knowledge updates) and outbound confirmation/notification messages.
- **Auth method:** Meta Business/System User access token (Bearer) for API calls, plus a separate webhook verify token for the inbound webhook handshake.
- **Rate limits / cost:** ⚠️ not a request-rate limit in the usual sense — **per-message pricing since July 2025**, free only inside a customer-opened 24-hour service window or a 72-hour click-to-WhatsApp ad entry point. A further pricing change affecting previously-free messages is scheduled for **Oct 1, 2026**. This materially changes the "free WhatsApp channel" assumption elsewhere in this repo's docs — budget a small ongoing per-message cost rather than assuming $0. See `open-source/open-source.md`'s "Recent changes to watch."
- **Sandbox availability:** a free test number is available during development, separate from a verified production business number.
- **Failure modes:** webhook delivery failure/retry storms; a message sent outside the free window incurring unexpected per-message cost; account/number verification issues blocking production messaging entirely.
- **Our fallback:** **none** — Meta is the sole WhatsApp Business Platform provider; there is no swappable alternative behind an interface the way voice/STT/TTS/LLM vendors are. Mitigate via cost monitoring and alerting, not a vendor swap.

## Cloudflare R2

- **Status:** **Active** — call audio storage (`context/architecture.md` §7).
- **Purpose:** object storage for call audio, governed by a 30-day lifecycle rule.
- **Auth method:** S3-compatible API using an R2 Access Key ID + Secret Access Key.
- **Rate limits / free ceiling:** 10GB-month storage, 1M Class A ops/month, 10M Class B ops/month free; $0 egress always. No hard cutoff — pay-as-you-go billing begins automatically past the free allocation.
- **Sandbox availability:** the free tier itself functions as the sandbox; no separate sandbox environment needed.
- **Failure modes:** approaching the 10GB ceiling as tenant count grows (mitigated by the lifecycle rule + usage monitoring, `context/architecture.md` §13); upload failures; cross-tenant object access if bucket key paths aren't tenant-scoped by construction.
- **Our fallback:** none currently configured — R2 is the adopted default (the original brief named S3 as an "or" option, but R2 is what's actually decided, per `CLAUDE.md`).

## Supabase

- **Status:** **Rejected** as our database (ADR-0010/ADR-0023) — documented here as an evaluated alternative, not an active or even currently-deferred integration.
- **Purpose (if ever reconsidered):** managed Postgres+pgvector, offloading our own DB ops burden.
- **Auth method:** project API keys / connection string; a service-role key for privileged server-side access.
- **Rate limits / free ceiling:** 2 active free projects per org, 500MB database per project, **pauses after 7 days of inactivity** (data preserved, manual restore required).
- **Sandbox availability:** the free tier is itself effectively an evaluation tier.
- **Failure modes (if adopted):** free-tier project auto-pause on inactivity; connection pooling limits at higher scale.
- **Our fallback:** self-hosted PostgreSQL+pgvector on the Oracle VM — this is the actual primary choice, not a fallback in the usual sense; Supabase is the alternative, not the default.

## Langfuse

- **Status:** **Active** — self-hosted for observability (`context/architecture.md` §8, §10).
- **Purpose:** LLM call tracing and per-call cost attribution across the voice pipeline.
- **Auth method:** internal — a public/secret key pair generated by our own self-hosted instance, plus the instance's own admin login. No external vendor credential involved.
- **Rate limits:** none meaningful — bounded only by our own VM's resources, since it's self-hosted.
- **Sandbox availability:** N/A — self-hosting means there's no separate vendor sandbox; the local/dev Docker Compose instance serves that role.
- **Failure modes:** ⚠️ the MIT-licensed core works standalone, but some enterprise (`/ee`) features require a paid license key even when self-hosted — using one without a valid key may be unavailable or restricted (`open-source/open-source.md`). Also: our own VM going down takes tracing down with it — there's no external redundancy.
- **Our fallback:** tracing is observability, not on the critical call path — if Langfuse is unavailable, calls still function; degrade to app-level logs (already PII-scrubbed per `context/coding-rules.md`) until it recovers.

---

## Interface Mapping

Not every integration sits behind the provider abstraction layer — only the voice/STT/TTS/LLM vendors do. WhatsApp, object storage, and observability are direct integrations elsewhere in the codebase because there's no realistic multi-vendor swap need driving them to be abstracted the same way.

| Integration | Internal interface | Status |
|---|---|---|
| Vapi | `VoiceOrchestrator` | Deferred |
| Retell AI | `VoiceOrchestrator` | Deferred |
| Exotel | `TelephonyProvider` | Deferred |
| Sarvam AI | `SpeechToText` / `TextToSpeech` | Deferred |
| Deepgram | `SpeechToText` | Deferred |
| ElevenLabs | `TextToSpeech` | Deferred |
| Meta WhatsApp Cloud API | none — direct integration in `src/knowledge/` (not a voice/STT/TTS/LLM vendor) | Active |
| Cloudflare R2 | none — direct integration for object storage, not part of the voice provider abstraction | Active |
| Supabase | would have been the Postgres layer itself, not a `src/providers/` interface | Rejected |
| Langfuse | none — observability sits alongside the pipeline, not behind a swappable interface | Active |

## See Also

- `open-source/open-source.md` — license, cost, and free-tier ceiling for every dependency named above.
- `context/architecture.md` §2, §12 — the abstraction interfaces and how `cost_tier` resolves a concrete provider at runtime.
- `context/decisions.md` — the ADR for each accepted/deferred/rejected choice.
