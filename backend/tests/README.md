# Backend tests

Run from `backend/`: `python -m pytest -q`. Every test gets its own SQLite file, an empty `.env` and a fixed clock (`conftest.py`).

**Postgres.** Set `TEST_DATABASE_URL` to run the same suite on Postgres. CI does this in the "Pytest (Postgres)" job. The public schema of that database is **dropped before every test**, so use a throwaway database only. `DATABASE_URL` is always ignored by tests.

**Fixtures.**
- `conn`: scoped to the demo clinic.
- `raw`: unchecked, for asserting stored state.
- `settings`: the demo clinic's settings.

Covered:
- **Business isolation** (`test_tenancy.py`): business A can never read or change business B's bookings, blocks, inbox, calls, settings or pending WhatsApp actions. Unscoped queries on tenant tables are refused.
- **Double-booking:** the slot lock refuses a second active booking, even from a second connection.
- **Verticals** (`test_verticals.py`): every vertical and the `fixtures/verticals/demo_coaching/` dummy load and validate with no core change.
- **Vapi webhook, WhatsApp commands, desk, setup, safety post-call scan, spoken dates and times.**

Planned:
- **Safety suite runner:** runs `verticals/<name>/tests/safety-suite.yaml`; the clinic must pass at 100%.
- **Endpoint-level isolation**, once desk and settings are scoped to the logged-in business (Phase 2 M2).
- **Provider contracts:** one shared suite per interface.

Fixtures use fake data only.
