# `backend/src/models/`

**Purpose.** Pydantic schemas and DB row models shared across modules; migrations live alongside once chosen.

**Capabilities served.** C4, C11 (schema), all (payload validation)

**Contracts used.** `contracts.md` §1 (request/response shapes), §3 (tables, enums, exclusion constraint)

**Must not.** Name tables or columns after clinic-only concepts; ship a tenant table without RLS.
