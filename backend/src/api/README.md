# `backend/src/api/`

**Purpose.** FastAPI routers: REST for the receptionist web app and the agent tools API (`/v1/tools/*`), plus the custom-LLM endpoint and webhooks (WhatsApp, voice platform).

**Capabilities served.** C1–C8, C10 (transport for all of them)

**Contracts used.** `contracts.md` §1 (tools API), §2 (custom-LLM), §4 (WhatsApp webhooks)

**Must not.** Hold business logic — routers validate (Pydantic), set tenant context, and call service modules. No vendor SDKs.

**Browser API (Phase 2, contracts.md §6).** `auth.py` (login, logout, me), `onboarding.py` (templates, signup) and `errors.py` (one error shape: `{detail, code, fields?, alternatives?}`) are live. Every write needs the `X-Requested-With: catalyst` header (`deps.require_csrf_header`). Routes that act for a logged-in owner use `deps.get_user_conn`. `desk.py` (schedule, inbox, calls, stats) and `setup.py` (settings, leave) serve only the session's business; schedule routes use `deps.require_bookings`, which is 404 for a template without the bookings module. The old public try page (`public.py`), the legacy Vapi webhook and WhatsApp still use the demo clinic's `deps.get_conn`.
