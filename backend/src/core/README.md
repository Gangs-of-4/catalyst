# `backend/src/core/`

**Purpose.** Shared config, DB session with the RLS tenant context, logging with PII redaction, app-wide utilities.

**Capabilities served.** C11 (tenant isolation, no PII in logs)

**Contracts used.** `contracts.md` §3 (tenant_id + RLS on every table)

**Must not.** Import other feature modules, or contain feature logic.
