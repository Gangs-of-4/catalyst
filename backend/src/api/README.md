# `backend/src/api/`

**Purpose.** FastAPI routers: REST for the receptionist web app and the agent tools API (`/v1/tools/*`), plus the custom-LLM endpoint and webhooks (WhatsApp, voice platform).

**Capabilities served.** C1–C8, C10 (transport for all of them)

**Contracts used.** `contracts.md` §1 (tools API), §2 (custom-LLM), §4 (WhatsApp webhooks)

**Must not.** Hold business logic — routers validate (Pydantic), set tenant context, and call service modules. No vendor SDKs.
