# `backend/src/agents/`

**Purpose.** Call session logic and the nine tool handlers behind `/v1/tools/*`.

**Capabilities served.** C2, C3, C4, C5, C6, C10 (outcome logging)

**Demo build.** Served through `POST /vapi/webhook` (`contracts.md` §1.10, ADR-0035), plus `find_booking`.

**Contracts used.** `contracts.md` §1

**Must not.** Branch on vertical or tenant; embed prompts as string literals (prompts live in `verticals/<name>/agent-prompt.md`).
