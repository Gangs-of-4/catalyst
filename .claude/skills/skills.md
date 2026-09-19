# Skills

This directory holds project-specific Claude Code skills, one per subdirectory, each with a `SKILL.md`:

```
.claude/skills/<skill-name>/SKILL.md
```

## Current state

No application code exists yet, so none of the skills below have a `SKILL.md` implementation in a subdirectory yet — the specs here are the backlog. These four are process/workflow skills (not tied to a specific frontend/backend/db area), so they're worth speccing now even though no code exists: create `.claude/skills/<skill-name>/SKILL.md` per its spec below when it's first needed.

## Reusable Skills

### Writing and versioning voice agent prompts

**When to trigger:** creating a new vertical's agent prompt (typically via `/new-vertical`), updating an existing prompt after a `/call-trace` review surfaces a problem, or a client requests a wording/behavior change via WhatsApp.

**Inputs:** target vertical (D2C / real estate / education / healthcare); business context (name, offerings, tone) supplied at onboarding; the current self-hosted stack's latency budget (~1.2-2s round trip, see `context/decisions.md`); any escalation rules from that vertical's rule pack that must be reflected in the prompt.

**Steps:**
1. Start from the vertical's existing prompt version (or the vertical template if none exists).
2. Write in short, interruptible turns — the agent must handle barge-in cleanly; avoid long uninterruptible monologues given the latency budget.
3. Encode escalation triggers as explicit, recognizable instructions the model can act on mid-call, matching the vertical's escalation rule pack exactly (don't invent new triggers here — that's the escalation-rule-pack skill's job).
4. For healthcare, hard-code the admin-only scope and the instruction to escalate on any symptom/emergency signal with no conditional bypass.
5. Version the prompt (e.g. `v3` or a date stamp) and keep prior versions diffable.
6. Note which real or seed call transcripts were used to validate pacing and interruption handling.

**Output format:** a versioned prompt file (e.g. `verticals/<vertical>/agent-prompt.md`) with a short changelog header: version, date, what changed, why, and which transcripts it was validated against.

### Designing escalation rule packs from real transcripts

**When to trigger:** onboarding a new client or vertical (via `/new-vertical`), or after `/call-trace` or a `/compliance-check` finding shows a missed or over-firing escalation.

**Inputs:** a batch of real or seed call transcripts for the vertical; the vertical's known risk signals (e.g. symptom/emergency mentions for healthcare, high-intent buying signals for real estate, angry-customer signals for D2C); the current escalation rule pack, if one exists.

**Steps:**
1. Read transcripts and tag every utterance that should have triggered a human handoff.
2. Generalize tagged utterances into rule patterns (keyword, intent classification, or sentiment threshold — whichever is cheapest to evaluate reliably at call time on the live-call LLM).
3. Cross-check against hard compliance mandates first — for healthcare, any symptom or emergency signal escalates with no exception, regardless of confidence score.
4. Write rules into the pack's structured format, each with a one-line rationale.
5. Add a paired test-transcript set: positive examples (should escalate) and negative examples (should not), so a future prompt or rule change that breaks this is caught, not discovered live.
6. Balance false positives (escalation fatigue, defeats the "zero-effort" pitch) against false negatives (safety/compliance risk) — bias toward safety for healthcare, bias toward fewer false positives elsewhere.

**Output format:** `verticals/<vertical>/escalation-rules.yaml` (or equivalent structured file) plus its paired test-transcript set, each rule carrying a short rationale comment.

### Adding a provider behind the abstraction layer

**When to trigger:** integrating a new voice/STT/TTS/LLM vendor, or moving a tenant from a free-tier provider to a paid one (e.g. Kokoro → ElevenLabs, Groq → a paid LLM) once revenue justifies it. Often invoked via `/new-provider`.

**Inputs:** target layer (voice orchestration / STT / TTS / LLM); the layer's existing interface definition in `src/providers/<layer>/`; the layer's shared contract test suite; the new provider's SDK/API docs; whether the provider is free-tier or paid (for `/cost-report` and `context/decisions.md`).

**Steps:**
1. Read the existing interface for that layer. Do not change it unless the new provider reveals a gap that's genuinely shared across every provider on that layer — a one-off provider quirk stays inside that provider's own file.
2. Implement the interface for the new provider; every vendor-SDK call lives inside this one file, per the "no direct provider SDK calls outside `src/providers/`" rule in `CLAUDE.md`.
3. Run the layer's shared contract test suite against the new implementation before writing any provider-specific tests.
4. Add required config as environment variable names (never values) and register the provider in the layer's factory/config so tenants can select it.
5. Grep the codebase to confirm no file outside `src/providers/<layer>/` imports the new SDK directly.
6. If this is a new paid vendor relationship, add an entry to `context/decisions.md` and note its per-unit cost for `/cost-report`.

**Output format:** a new file under `src/providers/<layer>/` passing the shared contract test suite, plus (if applicable) a `context/decisions.md` entry and a cost note.

### Reviewing code for DPDP/TRAI compliance

**When to trigger:** before merging any change touching outbound calling, logging, data storage, or WhatsApp data handling; as a standing periodic audit. This is the procedure `/compliance-check` runs.

**Inputs:** the code path or diff under review; the compliance rules in `CLAUDE.md` and `context/architecture.md` (calling window, consent/DND, DPDP data handling, healthcare escalation); current TRAI DLT registration status (while unregistered, all outbound commercial calling must be fully gated off, not just rate-limited).

**Steps:**
1. Confirm any outbound-calling code path checks current IST time against the 9 AM-9 PM window before dialing.
2. Confirm consent and DND status are checked and logged before any outbound commercial call, and that the entire outbound path is disabled if TRAI DLT registration isn't complete yet — not just discouraged.
3. Grep log statements on the path for PII — raw phone numbers, names, transcript text — flag any occurrence; only tenant/call/lead IDs should appear in logs.
4. Confirm recordings and transcripts are written only to India-region storage (Oracle Mumbai/Hyderabad or equivalent) and that a deletion path exists for DPDP "delete on request" requests.
5. For healthcare-vertical code, confirm symptom/emergency detection routes to hard escalation with no confidence-based bypass.
6. Check whether the call-start AI-disclosure requirement (expected mandatory 2026-27) is implemented or explicitly tracked as pending — don't let it silently fall through.

**Output format:** a findings list, each entry as `file:line — violation — severity — rule violated — suggested fix`, referencing the specific `CLAUDE.md` non-negotiable or compliance requirement broken.

## Adding a skill

Once a skill above is first needed, or once a real area of the codebase exists (e.g. a frontend app, an API service, a test suite) that needs its own skill:

1. Create `.claude/skills/<skill-name>/SKILL.md`.
2. Write practical, project-specific instructions verified from the actual code — conventions, common commands, gotchas specific to that area.
3. Avoid generic/filler content that isn't specific to this project.
