# Contracts

Shared interfaces that the four work areas build against. **If your change touches this file, say so clearly in the PR description** — other members depend on it.

Status: **v0.1 draft, 2026-10-26.** Shapes are a starting point for M0 stubs; field names may change in review, but change them here first, then in code.

Contents: 1. Agent tools API · 2. Custom-LLM endpoint · 3. Booking schema · 4. WhatsApp command format · 5. Alert and summary formats.

Conventions everywhere:
- Times are ISO 8601 with offset, clinic-local (`Asia/Kolkata`), e.g. `2026-11-03T17:00:00+05:30`.
- Phone numbers are E.164 (`+91…`) in storage and APIs. **Never logged** — log IDs only.
- IDs are UUIDs as strings.
- `tenant_id` is never sent by the voice layer or the LLM. The backend resolves it from the call session or the authenticated user.

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

- **Endpoint:** `POST /vapi/webhook` for both tool calls and server messages.
- **Auth:** header `x-catalyst-secret: <CATALYST_TOOL_SECRET>`, set by `scripts/setup_vapi.py` on each tool and on the assistant's server. Missing or wrong → `401`. If the secret is unset on our side, everything is rejected.
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
