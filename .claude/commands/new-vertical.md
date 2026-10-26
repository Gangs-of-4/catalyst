---
description: Scaffold a new vertical from verticals/_template and validate it
argument-hint: <name>
---

Create a new vertical named `$ARGUMENTS` (lowercase, underscores).

1. If `verticals/$ARGUMENTS/` already exists, stop and say so.
2. Copy every file from `verticals/_template/` to `verticals/$ARGUMENTS/`. That's `vertical.yaml`, `agent-prompt.md`, `escalation-rules.yaml`, `onboarding-questions.md`, `seed-knowledge.yaml` and `tests/`.
3. Fill them in for this customer type:
   - labels (resource, contact, booking), booking defaults and enabled WhatsApp commands;
   - a first-draft prompt;
   - escalation rules: what must reach a human, and what is routine;
   - onboarding questions;
   - seed Q&A with `{placeholders}`;
   - a few test scripts.
   Use `verticals/clinic/` as a worked example.
4. Mark every file `DRAFT, team to review`. Set `status: draft`.
5. **Healthcare-type verticals** must set `safety.guard: required`, include a red-flag list for the client to approve, and a safety suite (50+ scripts before go-live).
6. Validate:
   - every key in `_template/vertical.yaml` is present;
   - all YAML parses;
   - if `backend/src/verticals/` has a validator, run it.
7. **Do not change any core code.** If the vertical seems to need a core change, stop and explain why. That is a design question for the team (ADR-0033).
8. Add it to `verticals/README.md` and, if it's a planned vertical, to `context/feature-backlog.md` → Later verticals.

No real business names, people or phone numbers in any file.
