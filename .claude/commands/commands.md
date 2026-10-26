# Commands

Project slash commands live in `.claude/commands/<name>.md`. **All of them are optional helpers.** Nobody has to use them, and none of them blocks work.

## Available now

| Command | What it does |
|---|---|
| `/whats-next [area]` | Reads the roadmap, recent commits and open PRs, then suggests useful next work. |
| `/align <idea>` | Says how an idea fits the MVP, or where it belongs in the backlog. Advisory only. |
| `/new-vertical <name>` | Copies `verticals/_template/`, fills it in, and validates it. Changes no core code. |
| `/standup [days]` | Summarises your recent work for the team chat. |

## Specced, not yet implemented

Create `.claude/commands/<name>.md` when one of these is first needed.

- **`/new-provider <layer> <name>`** [MVP]. Scaffolds a provider under `backend/src/providers/<layer>/`, plus a contract test in `backend/tests/providers/<layer>/` that reuses the layer's shared suite. Layers: `llm`, `stt`, `tts`, `voice_orchestrator`, `telephony`.
- **`/compliance-check <path>`** [MVP for PII; Post-MVP for outbound].
  - Audits a path for PII in logs, unguarded LLM replies on clinic calls, WhatsApp writes without confirmation, and transfers to a forwarding number.
  - Once outbound exists, it also checks the DLT gate, the calling window, DND and consent.
  - Output is a `file:line — violation — rule` list.
- **`/safety-suite [vertical]`** [MVP]. Runs `verticals/<vertical>/tests/safety-suite.yaml` and reports pass/fail per script. The clinic must be at 100%.
- **`/call-trace <call-id>`** [Post-MVP, needs Langfuse]. Summarises a call's trace: per-turn latency, misrecognition, and missed escalation.
- **`/cost-report <tenant-id>`** [Post-MVP]. Per-minute and per-call cost by provider layer. In the MVP, the D4 per-minute cost is measured manually.
