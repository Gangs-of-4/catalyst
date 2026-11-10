# `backend/src/core/`

**Purpose.** Shared config, the database layer with tenant scoping, business (tenant) records, logging with PII redaction, app-wide utilities.

**Capabilities served.** C11 (business isolation, no PII in logs), C12 (businesses as config).

**Contracts used.** `contracts.md` §3.1 (Phase 2 tables, `tenant_id` on every tenant table).

- `db.py` is one thin SQL layer for SQLite (local and tests) and Postgres (`DATABASE_URL`, production; ADR-0039).
  - Write SQLite-style SQL with `?` in the subset both databases share. Inserts that need the new id use `RETURNING id`. Upserts use `ON CONFLICT`.
  - A unique-key clash raises `db.Conflict` on both databases.
  - `db.connect()` gives a connection. Scope it to one business with `.for_tenant(id)`, and use `conn.tid` in every query.
  - A query that touches a tenant table without mentioning `tenant_id` raises `db.ScopeError` before it runs. `db.connect_unchecked()` skips that check: tests and cross-business admin counts only.
  - An old single-clinic demo SQLite file is moved aside to `*.legacy` on first start. Its data was fictional.
- `tenancy.py` creates and finds businesses by id, `public_id` or owner WhatsApp number. It also loads and saves each business's settings JSON.
- `settings.py` holds helpers for one business's settings (doctors, fuzzy doctor match).

Postgres row-level security is a stretch goal (ADR-0039). Until then, isolation rests on the scope check plus `backend/tests/test_tenancy.py`.

**Must not.** Import other feature modules, or contain feature logic.
