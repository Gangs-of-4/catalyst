# Skills

Project skills live in `.claude/skills/<skill-name>/SKILL.md`. None is implemented yet; the specs below are the backlog. Create a `SKILL.md` when a skill is first needed, and write it from the real code.

## Writing and versioning agent prompts [MVP]

**When:** creating a vertical's prompt, or changing one after a call review or safety-suite failure.

**Steps:**
1. Start from `verticals/<vertical>/agent-prompt.md`, or `_template/` if there is none.
2. Use short, interruptible turns. Disclose that the caller is talking to an automated assistant. Read back before booking (C2).
3. Answer only from `get_clinic_info` (C3). Use the nine tools exactly as named in `context/contracts.md`.
4. Reflect `escalation-rules.yaml` and don't invent triggers. For clinics, the "never give diagnosis, medicine or dosage" section is backed by the guard in code.
5. Bump the version and fill in the changelog header (version, date, what changed, why, validated against).
6. **Run the safety suite.** Any prompt change must pass at 100% for clinics.

## Designing escalation rule packs [MVP]

**When:** onboarding a vertical or client, or after a missed or over-firing escalation.

**Steps:**
1. Tag call turns that should, and should not, have reached a human.
2. Split them into `red_flags` (escalate), `routine` (just book), and grey zone (clinic: escalate).
3. Write each rule with a one-line rationale in `verticals/<vertical>/escalation-rules.yaml`.
4. Add paired positive and near-miss negative scripts to `tests/safety-suite.yaml`.
5. Get client sign-off (role only, e.g. "Doctor A") before go-live. Record it in `context/go-live-checklist.md`.

Clinics bias toward safety. ADR-0031 (Proposed) replaces the old "any symptom escalates" rule with the approved red-flag list.

## Adding a provider behind the abstraction layer [MVP]

**When:** adding a voice, STT, TTS, LLM or telephony vendor (for example the D1 managed platform, or the S1 telephony provider).

**Steps:**
1. Read the interface in `backend/src/providers/<layer>/`. Don't change it for a one-off quirk.
2. Implement it. All vendor SDK calls stay in this one file.
3. Pass the layer's shared contract tests.
4. Add env var names (never values) to `.env.example`.
5. Grep the codebase to confirm nothing outside `backend/src/providers/` imports the SDK.
6. For a new paid vendor, add or update an ADR and note the cost (VERIFY).

## Reviewing code for privacy and compliance [MVP; outbound parts Post-MVP]

**When:** before merging changes that touch logging, storage, WhatsApp, transfers or LLM replies.

**Checks:**
1. No PII in logs.
2. Every clinic-call LLM reply passes the guard.
3. WhatsApp writes require "Haan", and only registered senders can command.
4. Transfers never target a forwarding number.
5. Patient messages are service-only and STOP is honoured.
6. Minimum data is collected, with no clinical detail stored.
7. Residency follows the current decision (ADR-0029 / D3).
8. **[Post-MVP]** Outbound calls and SMS go through the fail-closed DLT gate, the 9 AM–9 PM IST window checked at dispatch, DND and consent.

**Output:** `file:line — violation — severity — rule — fix`.
