# `backend/src/agents/`

**Purpose.** Call session logic and the nine tool handlers behind `/v1/tools/*`.

**Capabilities served.** C2, C3, C4, C5, C6, C10 (outcome logging)

**Demo build.** Served through `POST /vapi/webhook/{public_id}` (`contracts.md` §1.10, ADR-0035), one path and secret per business, plus `find_booking`. The old `POST /vapi/webhook` (global secret, demo clinic) stays until every assistant is re-synced. `prompt.build` reads the business's template from its `tenants` row; a template with no `agent-prompt.md` (wholesale until M4) raises `NoPrompt` and gets no assistant.

**Contracts used.** `contracts.md` §1

**Must not.** Branch on vertical or tenant; embed prompts as string literals (prompts live in `verticals/<name>/agent-prompt.md`).
