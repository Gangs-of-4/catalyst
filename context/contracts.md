# Contracts

Shared interfaces that the four work areas build against. **If your change touches this file, say so clearly in the PR description** — other members depend on it.

Status: **v0.2 draft, 2026-11-10.** v0.2 adds multi-business tenancy, the wholesale template, owner custom instructions, usage events, feedback and the browser API (Phase 2 program deliverable; ADR-0037, ADR-0038). Field names may change in review, but change them here first, then in code.

Contents: 1. Agent tools API (1.10 Vapi transport, 1.11 wholesale tools) · 2. Custom-LLM endpoint · 3. Booking schema (3.1 Phase 2 tables) · 4. WhatsApp command format · 5. Alert and summary formats · 6. Browser API.

Conventions everywhere:
- Times are ISO 8601 with offset, clinic-local (`Asia/Kolkata`), e.g. `2026-11-03T17:00:00+05:30`.
- Phone numbers are E.164 (`+91…`) in storage and APIs. **Never logged** — log IDs only.
- IDs are UUIDs as strings.
- `tenant_id` is never sent by the voice layer, the LLM or the browser. The backend resolves it from the webhook path (`public_id`), the session cookie, or the WhatsApp sender number.
- Money is integer paise in storage (`rate_paise`); APIs send paise and pages format ₹.

---

## 1. Agent tools API

The voice layer (managed platform or Pipecat) calls these nine tools. Business logic lives behind them (ADR-0032).

- **Transport:** `POST /v1/tools/<tool_name>` on our backend, JSON in and out.
- **Auth:** shared secret per voice platform in the `X-Catalyst-Tool-Key` header, plus `call_id`. The backend maps `call_id` → tenant. VERIFY how the chosen platform passes custom headers and call IDs.
- **Writes are idempotent:** `book`, `reschedule`, `cancel`, `create_callback` and `escalate` take an `idempotency_key`. A retry with the same key returns the first result.
- **Errors** use one envelope:

```json
{ "error": { "code": "SLOT_TAKEN", "say": "Ji, yeh slot abhi book ho gaya. Main doosra time batati hoon.", "retryable": false } }
```

`say` is an optional caller-safe line in the caller's language. **Fail-safe rule:** on any error the voice layer cannot recover from — or if the backend is unreachable — it takes the caller's name and number and calls `create_callback` with `urgent: true`. If even that fails, the platform plays its fallback message and the call is recovered from platform logs. The caller is never left in dead air (C6).

Common error codes: `UNKNOWN_CALL`, `VALIDATION`, `SLOT_TAKEN`, `OUTSIDE_HOURS`, `BLOCKED` (leave/holiday), `NOT_FOUND`, `AMBIGUOUS` (several bookings match), `INTERNAL`.

### 1.1 `get_clinic_info`

Answers only from doctor-approved entries (C3). Despite the name, core code treats this as tenant info; the label comes from `vertical.yaml`.

```json
// request
{ "call_id": "…", "question": "Sunday ko khula hai?", "language": "hi-en" }
// response
{ "found": true, "answers": [ { "entry_id": "…", "text": "Clinic Sunday ko band rehta hai." } ] }
// response when nothing approved matches
{ "found": false, "answers": [] }
```

On `found: false` the agent says it doesn't know, takes name and number, and calls `create_callback`.

### 1.2 `find_slots`

```json
// request
{ "call_id": "…", "resource_id": null, "service_id": null,
  "earliest": "2026-11-03T17:00:00+05:30", "latest": null, "limit": 3 }
// response
{ "slots": [
  { "resource_id": "…", "resource_label": "Doctor A", "starts_at": "2026-11-03T17:00:00+05:30", "ends_at": "2026-11-03T17:15:00+05:30" }
] }
```

Returns the 2–3 nearest free slots, respecting availability rules and blocks. `resource_id: null` means any resource.

### 1.3 `book`

```json
// request
{ "call_id": "…", "idempotency_key": "…",
  "resource_id": "…", "starts_at": "2026-11-03T17:00:00+05:30", "service_id": null,
  "contact": { "name": "…", "phone": "+91…" },
  "reason": "daant mein dard" }
// response
{ "booking_id": "…", "status": "booked",
  "readback": { "day": "Mangalvaar", "date": "3 November", "time": "shaam 5 baje", "resource_label": "Doctor A" } }
```

- `source` is set to `phone` by the backend.
- `reason` is optional, short and non-clinical (≤ 80 chars). It must not hold diagnoses or medicines.
- The agent reads back `readback` **before** calling `book` (C2) and confirms the same values after it. On `SLOT_TAKEN` the response includes `"alternatives": [slot, …]`.

### 1.4 `reschedule`

```json
// request
{ "call_id": "…", "idempotency_key": "…",
  "booking_id": null, "lookup": { "phone": "+91…", "date": "2026-11-03" },
  "new_resource_id": "…", "new_starts_at": "2026-11-04T11:00:00+05:30" }
// response
{ "booking_id": "…", "status": "booked", "readback": { "…": "…" }, "freed": { "resource_id": "…", "starts_at": "…" } }
```

Use `booking_id` or `lookup`. `AMBIGUOUS` returns a short list for the agent to confirm. The old slot frees immediately (C4).

### 1.5 `cancel`

```json
// request
{ "call_id": "…", "idempotency_key": "…", "booking_id": null, "lookup": { "phone": "+91…", "date": "2026-11-03" } }
// response
{ "booking_id": "…", "status": "cancelled", "freed": { "resource_id": "…", "starts_at": "…" } }
```

### 1.6 `create_callback`

```json
// request
{ "call_id": "…", "idempotency_key": "…",
  "contact": { "name": "…", "phone": "+91…" },
  "reason": "unanswered_question | staff_request | failover | other",
  "note": "Asked about braces cost", "urgent": false }
// response
{ "callback_id": "…" }
```

Shows in the receptionist inbox (C7) and in "aaj ke appointments?" (C8). `urgent: true` also raises an alert (§5).

### 1.7 `escalate`

Called when the red-flag engine or the guard flags the call, or the caller asks for staff.

```json
// request
{ "call_id": "…", "idempotency_key": "…",
  "category": "red_flag | grey_zone | caller_request",
  "matched_rule_id": "swelling_spreading",
  "summary": "Caller reports swelling spreading to the eye since morning. Wants to see Doctor A.",
  "contact": { "name": "…", "phone": "+91…" } }
// response
{ "escalation_id": "…",
  "action": "transfer | alert_only | after_hours_instruction",
  "say": "…",
  "transfer_chain_length": 2 }
```

- `summary` is at most 2 lines and goes to the doctor (C6).
- `after_hours_instruction` returns the doctor-approved emergency text in `say`.
- The backend raises the urgent alert for every escalation; it stops repeating when someone marks it done.

### 1.8 `transfer`

Gets the next live-transfer target. The voice layer performs the transfer and reports back.

```json
// request
{ "call_id": "…", "escalation_id": "…", "position": 0, "previous_result": null }
// response
{ "destination": "+91…", "ring_seconds": 20, "position": 0, "is_last": false }
// response when the chain is exhausted
{ "destination": null, "is_last": true, "fallback": "take_message" }
```

- `previous_result` is one of `no_answer`, `busy`, `failed`, `connected`, or null for the first request.
- **Never returns the clinic number that forwarded the call** (telephony rule in `mvp.md`). Destinations come only from the tenant's contact chain, which validation keeps separate from the forwarded number.
- When the chain is exhausted, the agent takes a message, and the open escalation alert keeps repeating to the whole chain.

### 1.9 `log_call_outcome`

Called once at call end. Feeds C10.

```json
// request
{ "call_id": "…", "outcome": "booked | answered | escalated | callback | hung_up",
  "booking_id": null, "callback_id": null, "escalation_id": null,
  "language": "hi-en", "duration_s": 94, "flags": ["misunderstood"] }
// response
{ "ok": true }
```

Transcripts are pushed separately by the voice layer integration into our database (never into logs). `flags` feed the weekly misunderstood-call review.

### 1.9a `find_booking` (added 2026-10-27)

Looks up the caller's upcoming bookings before `reschedule` or `cancel`, so the agent can confirm which one.

```json
// request
{ "call_id": "…", "phone": "+91…" }
// response
{ "bookings": [ { "booking_id": "…", "resource_label": "Doctor A", "starts_at": "2026-11-03T17:00:00+05:30" } ] }
```

### 1.10 Demo transport: Vapi webhook (ADR-0035, demo build only)

The demo build serves the same tools through **one** Vapi endpoint instead of `/v1/tools/<name>`. The pilot returns to §1.

- **Endpoint (v0.2):** `POST /vapi/webhook/{public_id}` for both tool calls and server messages. `public_id` is the business's random URL slug (§3.1 `tenants.public_id`); the backend resolves the tenant from it. Unknown `public_id` → `401`, the same as a wrong secret, so the webhook can't be used to find which ids exist. The single-tenant `POST /vapi/webhook` is removed once every assistant is re-synced.
- **Auth (v0.2):** header `x-catalyst-secret: <tenants.tool_secret>`, a per-business secret generated when the business is created and set on each tool and on that business's assistant. Missing or wrong → `401`. A secret for business A never authorises business B. (v0.1 used one global `CATALYST_TOOL_SECRET` from `.env`.)
- **Assistants:** one Vapi assistant per business, created on signup and PATCHed when that business's settings or instructions change. Only that business's assistant is touched; a business without one gets a new one or `not_configured`, never the demo clinic's. The demo clinic keeps its original assistant (`VAPI_ASSISTANT_ID` in `.env`) until the try page reads `tenants.vapi_assistant_id`. Tool calls outside the business's template `tools` list are refused (`Unknown tool …`). Every assistant sets `maxDurationSeconds: 180` (`VAPI_MAX_CALL_SECONDS`).
- **Call caps:** before the browser starts a web call it asks `POST /api/try/{public_id}/start` (§6). The backend allows at most `DEMO_CALLS_PER_DAY` (default 20) web calls per day across all businesses, plus a per-business daily cap (`CALLS_PER_BUSINESS_PER_DAY`, default 10). Over the cap it answers `429 {"code": "MINUTES_USED_UP"}` and the page shows a friendly "minutes used up for today" state.
- **Tool call request** (VERIFY against the Vapi docs if Vapi changes it; checked against `@vapi-ai/web` 2.7.1 types):
  ```json
  { "message": { "type": "tool-calls",
                 "toolCallList": [ { "id": "…", "type": "function", "function": { "name": "find_slots", "arguments": { "date": "kal", "time": "shaam 5 baje" } } } ],
                 "call": { "id": "…", "type": "webCall", "customer": { "number": "+91…" } } } }
  ```
  `arguments` may be an object or a JSON string. The older `toolWithToolCallList[].toolCall` shape is also accepted.
- **Tool call response** (HTTP 200): `{ "results": [ { "name": "<tool>", "toolCallId": "<id>", "result": "<plain text>" } ] }`. The result is plain text for the voice LLM, and always states the resolved day and date (e.g. "Wednesday, 28 October 2026, 5 PM with Dr. …").
- **Arguments** take spoken words or ISO: `date` ("kal", "parso", "somvar", "28 Oct", "2026-10-28"), `time` ("shaam 5 baje", "saade 10", "17:00"), `doctor` (name, fuzzy-matched). `phone` defaults to the caller ID when Vapi sends one.
- **Idempotency:** the Vapi `toolCallId` is the idempotency key. A retried tool call returns the first result.
- **Outcome:** `log_call_outcome` is a stub. The backend derives the outcome from what the tools did during the call, then the `end-of-call-report` server message adds the summary, transcript and recording URL. Priority: `escalated` > `booked` > `changed` > `callback` > `answered` > `hung_up`. (`changed` = moved or cancelled; demo-only value.)
- **`transfer`** is a stub: web calls cannot transfer. `escalate` raises the urgent inbox item and the WhatsApp alert instead.
- **Booking `source`** stays `phone` for agent bookings, as in §3.
- **Tools per template:** each vertical lists its tools in `vertical.yaml` (`tools:`). The backend only registers and serves those; a tool not in the list returns the error text "Tool not available".

### 1.11 Wholesale tools (added 2026-11-10, v0.2)

Same transport, auth, idempotency (`toolCallId`) and plain-text result rule as §1.10. Arguments below are what the voice LLM sends; results are plain text for the LLM, shown here as the facts they must contain.

| Tool | Arguments | Result must contain | Errors (stated in the text) |
|---|---|---|---|
| `get_business_info` | `question` | Approved answers only (C3), or "not found" | — |
| `get_catalog` | `query` (optional words) | Up to 10 matching products: name, pack size, rate in ₹, in stock yes/no | — |
| `check_stock` | `product` | Matched product name, pack size, in stock yes/no, rate | `UNKNOWN_PRODUCT` with up to 3 full catalogue names that fit what was said, or close spellings, for the caller to confirm (never a substitute). Only an exact name (case and punctuation aside) is a match; even a single partial fit is confirmed. A hidden product is "not available". |
| `create_order` | `shop_name`, `contact_name`, `phone`, `items: [{product, qty}]`, `notes` | Order number, each line as name × qty × rate, total | `UNKNOWN_PRODUCT`, `OUT_OF_STOCK` (offer a callback), `VALIDATION` (qty must be a whole number 1–9999) |
| `order_status` | `phone` (the caller's, or the one they give), optional `order_number` | Status, date, item count and total of that phone's order with that number, else its last 3 orders | `NOT_FOUND`. Without a phone the result asks for it: a number alone never reveals an order. |
| `create_callback` | as §1.6 / §1.10 | Callback ID | — |
| `escalate` | as §1.7 / §1.10 | What happens next | — |

`get_clinic_info` (§1.1) and `get_business_info` are the same function; the clinic template exposes the first name, the wholesale template the second.

Rules the wholesale prompt and tools enforce together:
- **Rates come only from the catalogue.** The agent never states a rate, discount or total that a tool did not return. Unknown → `create_callback` with reason `unanswered_question`.
- **Read-back before saving.** The agent reads each line (name, pack size, quantity) back to the caller and gets a yes **before** calling `create_order`.
- **No medical advice, even though the products are medicines.** No dosage, use, side effects, or "X ki jagah Y" (substitutes). Such questions → polite refusal + `create_callback`. Conflicts never offer another product as an alternative: out of stock offers a callback; a duplicate order points to the existing order number.
- `source` is `phone` for agent orders, as for bookings. A saved order counts as `booked` in the call's outcome (§1.10 `log_call_outcome` values).
- The post-call safety check knows the catalogue: product names and pack sizes are not flags, but doses, "take this", diagnosis, reassurance and substitutes are (`backend/src/safety/post_call.py`).

---

## 2. Custom-LLM endpoint (safety guard route)

With a managed platform, its LLM calls go to our endpoint so the guard runs on every reply (ADR-0032).

- `POST /v1/llm/chat/completions` uses an OpenAI-compatible request/response, streaming optional. VERIFY the chosen platform's exact custom-LLM format.
- The flow is: our LLM provider → `safety.guard.check(reply)` → on block, replace the reply with a safe line and call `escalate` with `grey_zone` → return the reply.
- With Pipecat, the same guard function runs in-process. There is one guard implementation, not two.

---

## 3. Booking schema

Postgres. Every table has `tenant_id` and an RLS policy from its first migration (ADR-0016). No clinic-only names (ADR-0033); labels like "Doctor" come from `vertical.yaml`.

| Table | Purpose | Key columns |
|---|---|---|
| `tenants` | one client business | `id`, `name`, `vertical`, `timezone`, `status` |
| `resources` | who/what gets booked (a doctor, a teacher) | `id`, `tenant_id`, `label`, `active` |
| `services` | what is booked | `id`, `tenant_id`, `name`, `duration_min` (default slot length; per-service length is Phase 2 item 37 but the column exists now) |
| `availability_rules` | recurring working hours | `id`, `tenant_id`, `resource_id`, `weekday` (0–6), `start_time`, `end_time`, `slot_min` |
| `blocks` | leave, breaks, holidays | `id`, `tenant_id`, `resource_id` (null = whole tenant), `starts_at`, `ends_at`, `kind` (`leave`/`break`/`holiday`), `source` |
| `contacts` | the person booking (a patient) | `id`, `tenant_id`, `name`, `phone`, `reminder_opt_out_at` |
| `bookings` | one appointment | `id`, `tenant_id`, `resource_id`, `service_id`, `contact_id`, `starts_at`, `ends_at`, `status`, `source`, `reason`, `created_by` |
| `callbacks` | inbox items | `id`, `tenant_id`, `contact_id`, `call_id`, `reason`, `note`, `urgent`, `done_at`, `done_by` |
| `escalations` | medical/staff escalations | `id`, `tenant_id`, `call_id`, `category`, `matched_rule_id`, `summary`, `triggered_at`, `done_at`, `done_by` |
| `contact_chain` | transfer/alert targets in order | `id`, `tenant_id`, `position`, `label`, `phone`, `ring_seconds`, `whatsapp_alerts` |
| `whatsapp_senders` | numbers allowed to give commands | `id`, `tenant_id`, `phone`, `role` (`owner`/`staff`) |
| `calls` | one row per call | `id`, `tenant_id`, `started_at`, `ended_at`, `outcome`, `language`, `flags` |
| `transcripts` | call text (personal data, DPDP) | `id`, `tenant_id`, `call_id`, `turns jsonb` |
| `knowledge_entries` | doctor-approved answers | `id`, `tenant_id`, `question`, `answer`, `embedding vector`, `confirmed_at`, `superseded_by` |

Enums:
- `bookings.status`: `booked`, `arrived`, `no_show`, `done`, `cancelled`.
- `bookings.source`: `phone`, `whatsapp`, `walk_in`.
- `calls.outcome`: `booked`, `answered`, `escalated`, `callback`, `hung_up`.

**No double-booking.** This is enforced by the database, not app code:

```sql
CREATE EXTENSION IF NOT EXISTS btree_gist;
ALTER TABLE bookings ADD CONSTRAINT bookings_no_overlap
  EXCLUDE USING gist (
    tenant_id WITH =,
    resource_id WITH =,
    tstzrange(starts_at, ends_at, '[)') WITH &&
  ) WHERE (status IN ('booked', 'arrived'));
```

A conflicting insert raises an exclusion violation, which the API maps to `SLOT_TAKEN`. Cancelled and no-show rows don't block, so a freed slot opens immediately.

**Validation rules (setup):**
- `contact_chain.phone` must differ from every number that forwards to the agent.
- `whatsapp_senders` must be non-empty before go-live.

### 3.1 Phase 2 tables (v0.2, 2026-11-10)

Phase 2 runs on one thin SQL layer: SQLite locally and in tests, Postgres (`DATABASE_URL`) in production (ADR-0039). The SQL stays in the subset both support: integer IDs from the database for rows (`RETURNING id`), UUID text IDs for businesses and users, ISO-8601 text dates, integer money, `ON CONFLICT`, partial unique indexes. Isolation is enforced in app code by one scoping helper plus tests that business A can never read or change business B's data; Postgres RLS is a stretch goal (ADR-0016 departure recorded in ADR-0039).

Every table below except `tenants` has `tenant_id`, and every query on it filters by `tenant_id`.

| Table | Purpose | Key columns |
|---|---|---|
| `tenants` | one business | `id` (UUID), `public_id` (random URL slug, unique; demo businesses use `demo-<template>`), `name`, `template` (`clinic` \| `wholesale`), `settings` (JSON: city, address, landmark, hours, closed days, resources, services, FAQs, emergency text, minimum order, delivery area), `owner_whatsapp` (E.164, **unique across businesses**), `vapi_assistant_id`, `tool_secret`, `is_demo`, `created_at` |
| `tenant_whatsapp_numbers` | WhatsApp routing index | `number` (E.164, unique), `tenant_id`: the owner number plus `settings.whatsapp_numbers`, rebuilt on every settings save and at startup |
| `users` | the owner's login | `id`, `tenant_id`, `name`, `email` (unique, lowercased), `password_hash` (`hashlib.scrypt`, per-user salt), `failed_logins`, `locked_until`, `last_active_at`, `created_at` |
| `sessions` | logins | `token_hash` (SHA-256 of the cookie token), `user_id`, `tenant_id` (null for admin), `kind` (`user` \| `admin`), `expires_at`, `created_at` |
| `bookings`, `blocks`, `inbox`, `calls`, `tool_calls`, `pending_actions` | as today (demo schema) | + `tenant_id`. Slot lock: unique (`tenant_id`, `resource_id`, `date`, `time`) where status is active. `tool_calls` key (`tenant_id`, `id`). |
| `products` | wholesale catalogue | `id`, `tenant_id`, `name`, `name_key` (normalised, unique per tenant), `pack_size`, `rate_paise`, `in_stock`, `active`, `updated_at` |
| `orders` | one order | `id`, `tenant_id`, `number` (per-tenant counter, unique per tenant), `shop_name`, `contact_name`, `phone`, `notes`, `status`, `source`, `call_id`, `idempotency_key` (unique per tenant), `created_at`, `updated_at` |
| `order_items` | order lines | `id`, `tenant_id`, `order_id`, `product_id`, `name`, `pack_size`, `qty`, `rate_paise` (name and rate are copied at order time) |
| `instruction_versions` | owner custom instructions | `id`, `tenant_id`, `text` (accepted lines only, ≤ 500 chars), `rejected` (JSON list of `{line, reason}`), `source` (`web` \| `whatsapp`), `active`, `created_at` |
| `events` | usage evidence | `id`, `tenant_id`, `user_id` (nullable), `type`, `created_at`. **No payload column**, so counts can never carry names or numbers. Types so far: `web_call_started` (the call caps count these). |
| `feedback` | in-app feedback | `id`, `tenant_id`, `person_name`, `person_role`, `text`, `type`, `decision`, `decision_reason`, `shipped_on`, `evidence_url`, `partner_reaction`, `created_at` |
| `schema_version` | migrations | `version` |

Enums:
- `tenants.template`: one folder name under `verticals/` that is not `_template`.
- `orders.status`: `new` → `confirmed` → `dispatched` → `delivered`; `new` or `confirmed` → `cancelled`. Any other transition is `INVALID_TRANSITION`.
- `orders.source`: `phone`, `whatsapp`, `walk_in` (same as bookings).
- `events.type`: `signup`, `login`, `booking_created`, `booking_status`, `order_created`, `order_status`, `callback_created`, `call_ended`, `wa_command`, `settings_saved`, `instructions_saved`, `catalog_updated`, `feedback_sent`.
- `feedback.type`: `bug`, `feature`, `usability`, `data_integration`, `pricing_business`.
- `feedback.decision`: `shipped`, `in_progress`, `planned`, `wont_do` (needs `decision_reason`).

Personal data kept: business details, the owner's name, email and WhatsApp, and patient/shop **name and phone** on bookings and orders. No medical data: booking `reason` stays short and non-clinical (§1.3); order `notes` are delivery notes.

---

## 4. WhatsApp command format

The doctor writes in free text (Hinglish/English). An LLM extracts the intent into this schema, validated with Pydantic, and fails closed on parse error (coding rules).

```json
{ "intent": "block_day | block_range | set_hours | query_today | unknown",
  "resource_id": null,
  "params": { "date": "2026-11-04", "start": null, "end": null },
  "confidence": 0.93 }
```

| Doctor says | Intent | Preview reply |
|---|---|---|
| "kal chhutti hai" | `block_day` | "Kal, 4 Nov (Budhvaar), Doctor A ke saare slots band. 2 booked patients ko callback list mein daal dein? Sahi hai? Haan/Nahi" |
| "aaj 11 baje se" | `set_hours` (today only) | "Aaj Doctor A 11 baje se available. Sahi hai? Haan/Nahi" |
| "aaj ke appointments?" | `query_today` | Read-only: today's bookings per resource + pending callbacks. No preview needed. |

Rules:
- Only numbers in `whatsapp_senders` for the tenant are accepted. Others get no action, and the attempt is logged by ID only.
- **Every write is previewed.** It applies only after "Haan" (also accepted: "haan", "ha", "yes", "ok"), then the system replies "Ho gaya — live hai." On "Nahi" or no reply within the expiry window, nothing changes. The expiry window is a config value (proposed default 30 min).
- If a write affects existing bookings, the preview says how many and what happens to them.
- If the intent is `unknown` or confidence is below a configured threshold, the reply is "Samajh nahi aaya — hamari team aaj hi dekh legi." An ops task is created, and our team handles it manually the same day (C8).
- Each vertical enables commands in `vertical.yaml` (`whatsapp.commands`).

**Routing (v0.2).** One Twilio sandbox number serves every business. The backend finds the business by the sender's number: its owner number or one of the numbers in its settings' `whatsapp_numbers` (e.g. a second doctor), compared normalised (E.164). Every such number belongs to exactly one business (`tenant_whatsapp_numbers`, unique): a settings save that lists another business's number is `409 WHATSAPP_TAKEN`, and so is a signup with one. There is no open demo mode: a business with no numbers takes no commands. An unknown number gets: "Yeh number kisi Catalyst business se juda nahi hai. {PUBLIC_APP_URL}/signup par apna front desk banaiye, ya Settings mein yahi WhatsApp number daaliye." Nothing else happens, and the attempt is logged by ID only.

**Wholesale commands (v0.2).** Rule-parsed first; the LLM parser is a fallback. Every write is previewed.

| Owner says | Intent | Write? | Preview / reply |
|---|---|---|---|
| "aaj ke orders" | `orders_today` | no | Today's orders: number, shop, item count, status |
| "rate Paracetamol 500 42" / "rate <item> <price>" | `set_rate` | yes | "Paracetamol 500 (10x10): ₹38 → ₹42. Sahi hai? Haan/Nahi" |
| "stock khatam <item>" | `stock_out` | yes | "<item> ko out of stock kar dein? Agent naye orders mein yeh nahi lega. Haan/Nahi" |
| "stock aa gaya <item>" | `stock_in` | yes | "<item> ko in stock kar dein? Haan/Nahi" |
| "order 42 dispatch" (also confirm, delivered, cancel) | `order_status` | yes | "Order 42 (<shop>) ko dispatched mark karein? Haan/Nahi". An invalid transition replies with the current status and changes nothing. |
| "summary" | `summary` | no | Today's and this week's counts |

An item name that isn't an exact catalogue name replies with the closest names and asks for the full name; it never guesses. Rate and stock changes don't re-sync the assistant (rates aren't in the prompt; the tools read them live).

**Which commands a business has.** The template's module picks the parser (bookings: the clinic commands above; orders: these), and `vertical.yaml` `whatsapp.commands` lists the enabled intents (`help` always works).

**Custom instructions on WhatsApp (both templates).** "agent ko bolo <text>" → intent `add_instruction`. The text goes through the same screening as the settings page (§6). The preview shows what will be added and any rejected line with its reason; on "Haan" a new `instruction_versions` row is saved, the prompt is rebuilt, and only that business's assistant is PATCHed. "Ho gaya — agent ab yeh maanega." If every line is rejected, nothing is saved and no preview is offered.

Patient-side:
- Reminder replies of `STOP` (case-insensitive; also "band karo") set `contacts.reminder_opt_out_at` permanently and send one confirmation.
- No other patient commands exist in the MVP (item 43 is Phase 2).

---

## 5. Alert and summary formats

All of these are WhatsApp utility templates and need Meta approval (D5). The wording below is draft.

**Urgent escalation alert.** Goes to everyone in `contact_chain` with `whatsapp_alerts = true`:

```
URGENT: patient call needs a doctor
Name: {name}  Phone: {phone}
{summary_line_1}
{summary_line_2}
Reply DONE {code} or mark done on the desk screen.
```

It repeats every `alerts.repeat_minutes` (from `vertical.yaml`, proposed default 5) until marked done on WhatsApp or in the web inbox. `{code}` is a short per-alert code.

**Urgent callback alert** (`create_callback` with `urgent: true`) uses the same shape with the heading "URGENT callback".

**Patient reminder.** Sent at a clinic-set time before the visit; service message only:

```
Namaste {name}, {tenant_name} mein aapka appointment {day} {date}, {time} ko {resource_label} ke saath hai. Reminders band karne ke liye STOP likhein.
```

**Weekly summary** to the owner:

```
Is hafte: {total} calls — {booked} booked, {answered} answered, {escalated} escalated, {callback} callbacks, {hung_up} hung up.
Calls saved vs. baseline: {calls_saved}.
Pending callbacks: {pending}.
```

**Ops alerts.** These go to our team only, never to the clinic:
- forwarding appears broken (calls to the test path fail);
- no calls for `ops.silence_hours` on a weekday during clinic hours;
- reminder sends failing.

The channel is the team's WhatsApp/ops group; the exact channel is TBD with D7.

---

## 6. Browser API (v0.2, 2026-11-10)

The frontend pages (Vite + React, ADR-0042) call these. Built and consumed in parallel by the backend and frontend tracks; change here first.

- **Origin.** In production the pages call `/api/...` on their own (Vercel) origin and Vercel rewrites it to the backend (ADR-0041), so the session cookie is first-party. Locally the Vite dev server proxies `/api` to FastAPI, so pages and API share one origin (the old static pages, still served by FastAPI until M8 replaces them, are same-origin too).
- **Session cookie.** `catalyst_session`: random token signed with HMAC-SHA256 (`SESSION_SECRET`), `HttpOnly`, `Secure` (except on `http://localhost`), `SameSite=Lax`, `Path=/`, 30-day expiry. The DB stores only the token's SHA-256 hash. Logout deletes the row.
- **CSRF.** Every write is a JSON `POST`/`PUT`/`DELETE` (except CSV upload, which sends the file as the raw body with `Content-Type: text/csv`) and must carry header `X-Requested-With: catalyst`; the backend rejects writes without it (`403`). Together with `SameSite=Lax` this blocks cross-site form posts.
- **Errors.** Every non-2xx body is `{ "detail": "<one plain sentence for the page>", "code": "<CODE>", "fields": {"<field>": "<message>"}?, "alternatives": [ ... ]? }`. Pages show `detail` as-is. Never a stack trace.

Common codes: `VALIDATION` (422, with `fields`), `UNAUTHENTICATED` (401), `FORBIDDEN` (403), `NOT_FOUND` (404), `EMAIL_TAKEN`, `WHATSAPP_TAKEN`, `SLOT_TAKEN` (409, `alternatives` = up to 3 free slots), `DUPLICATE_ORDER` (409, `alternatives` = the existing order), `INVALID_TRANSITION` (409), `OUT_OF_STOCK` (409, no alternatives: never another product), `TRY_AGAIN` (409, several orders took the same number at once; save again), `UNKNOWN_PRODUCT` (422, `alternatives` = up to 3 catalogue spellings of the name asked for), `LOCKED` (429, too many failed logins), `MINUTES_USED_UP` (429), `VOICE_NOT_CONFIGURED` (503), `INTERNAL` (500, generic sentence).

### 6.1 Endpoints

Auth column: **public**, **user** (session, scoped to the user's business; `401 UNAUTHENTICATED` without one), **admin** (admin session). There is no Basic auth: the demo clinic is a business like any other, with an owner login whose password comes from `DEMO_LOGIN_PASSWORD` (checked at every start: unset removes the login and its sessions, a new email retires the old one) (email `demo.clinic@example.com`, or `DEMO_LOGIN_EMAIL`).

| Method + path | Auth | Purpose |
|---|---|---|
| `GET /api/templates` | public | Templates with labels and onboarding defaults (from `verticals/*/`) |
| `GET /api/templates/{template}/sample-catalog.csv` | public | Sample catalogue CSV |
| `POST /api/signup` | public | Account + business in one step (onboarding form). Body: `user {name, email, password}`, `business {template, name, city, address, landmark, hours, closed_weekdays, owner_whatsapp, consent: true}`, `details` (the template section: `doctors`, `services`, `slot_min`, `emergency_instruction` for a bookings template; `min_order`, `delivery_area` for an orders template), optional `faqs`, `instructions` (≤ 500 chars). Instructions are screened at signup like any save (`PUT /api/instructions`); the accepted lines become the first instruction version before the assistant is built. Consent is recorded as `settings.consent = {at, version}`. Creates the assistant (failure is not fatal: the business is created and the test page shows `VOICE_NOT_CONFIGURED` with a retry). Sets the cookie. Returns `{public_id, template, agent, instructions, rejected}` where `instructions` is `"saved"` (some lines accepted), `"rejected"` (the owner wrote some and every line was rejected; nothing saved) or `"none"`, `rejected` is `[{line, reason}]`, and `agent` is `"updated"` \| `"not_configured"` \| `"failed"`. A template with no `agent-prompt.md` yet (wholesale until M4) is `not_configured`. |
| `POST /api/login` / `POST /api/logout` | public / user | Email + password. 5 failures → 15 min lock (`LOCKED`). |
| `GET /api/me` | user | User name, business name, template, labels, `public_id` |
| `GET /api/try/{public_id}` | public | `{public_id, name, city, template, modules, labels, voice, try_saying}`. `voice` is `{public_key, assistant_id}` or `null` (no assistant, or `VAPI_PUBLIC_KEY` unset); a `null` still returns 200 so the rest of the page loads. The assistant is the business's own (`tenants.vapi_assistant_id`); only the demo clinic, while its row has none, falls back to `.env` `VAPI_ASSISTANT_ID`. `try_saying` comes from the template's `vertical.yaml`. Unknown `public_id` → `404 NOT_FOUND` (these links are meant to be shared). |
| `POST /api/try/{public_id}/start` | public | Call-cap check before a web call (§1.10). No body; needs the CSRF header. `200 {max_call_seconds}` (and the call is counted as a `web_call_started` event), `429 MINUTES_USED_UP` over either daily cap (IST day), `503 VOICE_NOT_CONFIGURED` when `voice` would be `null`. |
| `GET /api/try/{public_id}/board` | public | Names masked ("Ramesh G."), never a phone number. Bookings template: `{kind: "bookings", days: [{date, label, short, closed, columns: [{resource, slots: [{time, state, booking}]}]}]}` for today and tomorrow, `state` one of `free` \| `booked` \| `blocked` \| `past`, `booking` `{id, name, source}` or `null`. Orders template: `{kind: "orders", orders: [{id, number, shop, items, total, status, source, created_at}]}`, today's, newest first (empty until M4). Polled every few seconds during a call. |
| `GET /api/desk/day?date=` · `POST /api/desk/bookings` · `POST /api/desk/bookings/{id}/status` | user | Schedule (bookings template). A business without the `bookings` module gets `404 NOT_FOUND`. A taken slot is `409 SLOT_TAKEN` with `alternatives: [{doctor_id, date, time}]`; a time that is closed, past or not a slot start is `422 VALIDATION` with the same `alternatives` when there are free times nearby. Also `GET /api/staff/meta` (business name, today, WhatsApp status for the old desk page) and `POST /api/desk/summary/send` (today's summary to the owner's WhatsApp numbers). |
| `GET /api/orders?status=&date=` · `POST /api/orders` · `POST /api/orders/{id}/status` | user | Order board (orders template; others get `404 NOT_FOUND`). An order is `{id, number, shop_name, contact_name, phone, notes, status, next, source, items: [{product_id, name, pack_size, qty, rate_paise, rate, amount}], total_paise, total, created_at, updated_at}`; `next` lists the statuses it may move to. `GET` returns `{orders, next_before_id}`, newest first, up to `limit` (default and max 200); `date` is the IST creation day; when `next_before_id` is set, pass it as `before_id` for the next page. `POST /api/orders` body `{shop_name, contact_name?, phone?, notes?, items: [{product_id, qty}], source: walk_in \| whatsapp, idempotency_key?, allow_duplicate?}`; rates and names are copied from the catalogue at that moment. `idempotency_key` from the page means a resend after a lost connection returns the same order. The same phone (else shop name) with the same items, still open, the same day is `409 DUPLICATE_ORDER` unless `allow_duplicate`. Lifecycle: `new → confirmed → dispatched → delivered`; `new` and `confirmed` can become `cancelled`; anything else is `409 INVALID_TRANSITION`. |
| `GET /api/catalog` · `POST /api/catalog` · `PUT /api/catalog/{id}` · `POST /api/catalog/import` (CSV) | user | Catalogue (orders template). A product is `{id, name, pack_size, rate_paise, rate, in_stock, active}`; `GET` returns active ones (`?all=true` for all). `POST` body `{name, pack_size, rate, in_stock}` with `rate` in rupees (`"120.50"`); `PUT` changes any of those plus `active`. A name already in the catalogue (case and punctuation ignored; letters of any script count) is `422`. Import: the CSV as the raw body (`Content-Type: text/csv`, ≤ 1 MB, header row required) keeps good rows, updates names already there, and returns `{added, updated, errors: [{row, message}]}` (row numbers as in a spreadsheet, header = 1). The whole file is checked before anything is saved, and the good rows are saved together; a file that can't be read as CSV saves nothing and returns one error. A body over 1 MB is refused before it is read. CSV columns: `name,pack_size,rate,in_stock`. |
| `GET /api/inbox` · `POST /api/inbox/{id}/done` · `GET /api/calls` · `GET /api/stats` | user | Shared desk panels |
| `GET /api/settings` · `PUT /api/settings` | user | Business settings. `GET` returns `{settings, blocks, agentConfigured}`. Save rebuilds the prompt and PATCHes only this business's assistant. Returns `{saved: true, agent, settings}`, where `agent` is one plain sentence for the page (updated, not set up, or failed). The `PUT` body is the template's shape: bookings (`name, city, address, landmark, sessions, closed_weekdays, faqs, whatsapp_numbers, voice, slot_min, doctors, services, red_flags, emergency_instruction`) or orders (the same common fields plus `min_order, delivery_area`; products live in the catalogue). |
| `POST /api/settings/blocks` · `DELETE /api/settings/blocks/{id}` | user | Leave and holidays (bookings template) |
| `GET /api/instructions` · `PUT /api/instructions` · `POST /api/instructions/undo` | user | Custom instructions. `GET` → `{text, version_id, rejected, max_chars, history: [{id, text, rejected, source, active, created_at}]}` (newest first, 10). `PUT` body `{text}` (≤ 500 chars) → `{accepted: [line], rejected: [{line, reason}], version_id, agent}`: each line or sentence is screened, the accepted ones become the new active version, and only this business's assistant is re-synced. Empty text clears the instructions. If every line is rejected nothing changes and `version_id` is `null`. Rejected: medical advice, prices or discounts, pretending to be human, ID/bank/OTP details, changing the rules, turning off safety or escalation. Undo makes the previous version active again → `{text, version_id, agent}`; `404 NOT_FOUND` when there is nothing to undo. In the prompt the text sits in a fenced section after every locked rule, with a line saying it can never override them. |
| `GET /api/settings/whatsapp` | user | Sandbox number and join steps (`join <TWILIO_SANDBOX_JOIN_CODE>`) |
| `POST /api/feedback` | user | `{person_name, person_role, text, type}` |
| `POST /api/admin/login` · `GET /api/admin/businesses` · `GET /api/admin/businesses/{id}/usage.csv` · `GET /api/admin/feedback` · `PUT /api/admin/feedback/{id}` · `GET /api/admin/feedback.csv` · `POST /api/admin/reset-demo` | admin | Usage evidence and feedback log (below) |

### 6.2 Admin usage and CSV formats

`GET /api/admin/businesses` returns, per business: `template`, `created_at`, `users`, `records` (bookings or orders created), `calls`, `wa_commands`, `last_active` (latest `events.created_at` or `users.last_active_at`), `is_demo`, and `weeks`: the last 4 ISO weeks (Monday start, IST), oldest first, each `{week_start, events, records, calls, wa_commands}`.

`usage.csv` columns (counts only — never names or phone numbers): `week_start,events,records,calls,wa_commands,logins`, one row per week for the last 4 weeks, plus a `total` row.

`feedback.csv` columns, newest first, matching the team's feedback Google Sheet: `Date,Partner and person,What they said,Type,Decision,Shipped on,Evidence,Partner's reaction`. "Partner and person" is `<business name> — <person name> (<role>)`. "Decision" for `wont_do` includes the reason.
