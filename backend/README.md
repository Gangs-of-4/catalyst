# Backend

Python 3.12 + FastAPI. Owns the brain: knowledge, schedule, rules, safety and alerts (ADR-0032). The demo build (ADR-0035) runs on SQLite with no Docker; see the repo `README.md` quickstart. Each module's `README.md` says what it does and what it must not do.

- Layout and rules: `context/coding-rules.md`
- Interfaces: `context/contracts.md`
- Design: `context/architecture.md`

## Run (demo build)

From `backend/` with the venv active: `uvicorn src.main:app --port 8000`. The database is `backend/data/clinic.db` (git-ignored), created and seeded with the fictional clinic on first start. Delete it to start fresh. Full steps are in the repo `README.md`.

| Module | Demo build |
|---|---|
| `api/` | `vapi.py` (agent webhook), `whatsapp.py` (Twilio), `public.py`, `desk.py`, `setup.py` |
| `agents/` | tool handlers, prompt builder, call tracking |
| `booking/` | slots, bookings, blocks; spoken date and time parsing (`when.py`) |
| `channels/whatsapp/` | doctor commands with preview-and-confirm, alerts, summary |
| `safety/` | post-call safety flag (`post_call.py`) |
| `providers/` | Vapi, Twilio and Groq over plain HTTP (no SDKs) |

## Tests

`pytest` from `backend/`. No keys needed; Vapi, Twilio and Groq are mocked.


`backend/tests/` holds unit and contract tests. The safety-suite scripts live in `verticals/<name>/tests/`, and the test-only `demo_coaching` vertical lives in `tests/fixtures/verticals/`.
