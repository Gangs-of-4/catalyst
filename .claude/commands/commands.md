# Commands

This directory is for project-specific custom Claude Code slash commands (`.claude/commands/<name>.md`).

## Current state

No application code exists yet, so none of these commands have an executable implementation file in this directory — the specs below are the backlog. When a command is first needed, create `.claude/commands/<trigger-name>.md` (the actual prompt/instructions Claude Code runs) matching its spec here; keep this file as the index.

## Available Commands

### `/new-provider`

**What it does:** Scaffolds a new provider implementation against the existing interface for one layer (voice orchestration / STT / TTS / LLM) under `src/providers/<layer>/`, plus a contract test proving it satisfies the same interface every other provider on that layer implements — so callers never need to know which provider is behind it.

**Trigger:** `/new-provider <layer> <provider-name>`

**Example usage:**
```
/new-provider stt faster-whisper
```
→ generates `src/providers/stt/faster_whisper.py` implementing the STT interface, and `tests/providers/stt/test_faster_whisper_contract.py` reusing the layer's shared contract test suite. See the "Adding a provider behind the abstraction layer" skill in `skills.md` for the underlying procedure.

### `/new-vertical`

**What it does:** Scaffolds a new vertical template: agent prompt, escalation rule pack, onboarding question set, and seed knowledge base — the four artifacts every vertical (D2C, real estate, education, healthcare) needs before a client in that vertical can go live.

**Trigger:** `/new-vertical <vertical-name>`

**Example usage:**
```
/new-vertical real-estate
```
→ generates `verticals/real-estate/agent-prompt.md`, `verticals/real-estate/escalation-rules.yaml`, `verticals/real-estate/onboarding-questions.md`, and `verticals/real-estate/seed-knowledge-base.md`, each pre-filled with the vertical's known constraints (e.g. healthcare gets admin-only scope and mandatory hard-escalation rules baked in, not left blank).

### `/compliance-check`

**What it does:** Audits a given code path for the compliance rules in `CLAUDE.md` and `context/architecture.md` — calling-window enforcement (9 AM-9 PM IST), consent/DND checks on outbound, and PII in log statements (phone numbers, names, raw transcript text). Reports file:line findings with severity and the specific rule violated.

**Trigger:** `/compliance-check <path>`

**Example usage:**
```
/compliance-check src/outbound/dialer.py
```
→ flags e.g. a log line printing a raw phone number, or a dial path with no DND check, each tied to the non-negotiable rule or compliance requirement it breaks. See the "Reviewing code for DPDP/TRAI compliance" skill in `skills.md` for the full audit procedure this command runs.

### `/call-trace`

**What it does:** Given a call ID, pulls the Langfuse trace and transcript for that call (self-hosted Langfuse) and summarizes what went wrong — e.g. a latency spike in a specific turn, an STT misrecognition, a missed escalation trigger, or an off-script LLM response.

**Trigger:** `/call-trace <call-id>`

**Example usage:**
```
/call-trace call_8f2a91
```
→ returns a short summary: turn-by-turn latency, where the conversation diverged from the agent prompt's intent, and whether an escalation rule should have fired but didn't.

### `/cost-report`

**What it does:** Computes per-minute and per-resolved-call cost for a tenant, accounting for which providers (free-tier vs. paid-tier, behind the abstraction layer) are active for that tenant across STT/TTS/LLM/telephony. Used to decide when a tenant's volume justifies moving them onto paid providers, and to size per-client telephony billing once a phone number is provisioned for them.

**Trigger:** `/cost-report <tenant-id> [date-range]`

**Example usage:**
```
/cost-report tenant_042 --last-30-days
```
→ returns per-minute cost, cost per resolved call, and a breakdown by provider layer, flagging any layer where the tenant has crossed free-tier limits.

## Adding a command

Add a command here only when a repeatable, project-specific workflow emerges that's worth invoking by name. Document the trigger, what it does, and example usage before writing the executable file, then implement `.claude/commands/<trigger-name>.md` per Claude Code's slash command format.
