# `backend/src/agents/`

**Purpose.** Call session logic and the nine tool handlers behind `/v1/tools/*`.

**Capabilities served.** C2, C3, C4, C5, C6, C10 (outcome logging)

**Demo build.** Served through `POST /vapi/webhook/{public_id}` (`contracts.md` §1.10, ADR-0035), one path and secret per business, plus `find_booking`. The old `POST /vapi/webhook` (global secret, demo clinic) stays until every assistant is re-synced. `prompt.build` reads the business's template from its `tenants` row; a template with no `agent-prompt.md` raises `NoPrompt` and gets no assistant. Wholesale tools (contracts.md §1.11): `get_business_info`, `get_catalog`, `check_stock`, `create_order`, `order_status`, served from `orders/`. Their results only ever carry catalogue names and rates, never suggest another product, and an order counts as `booked` in the call outcome. The webhook refuses tools the business's template doesn't list. Owner custom instructions (`instructions.py`, M5): screened line by line (rules only; the LLM screen is cut, phase2-plan.md), kept as versions with undo, and put by `prompt.build` into the fenced `{owner_instructions}` section that follows every locked rule.

**Contracts used.** `contracts.md` §1

**Must not.** Branch on vertical or tenant; embed prompts as string literals (prompts live in `verticals/<name>/agent-prompt.md`).
