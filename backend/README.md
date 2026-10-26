# Backend

Python 3.12 + FastAPI. Owns the brain: knowledge, schedule, rules, safety and alerts (ADR-0032). No application code yet, only the module skeleton. Each module's `README.md` says what it does and what it must not do.

- Layout and rules: `context/coding-rules.md`
- Interfaces: `context/contracts.md`
- Design: `context/architecture.md`

## Run (target commands, not runnable until M0 lands)

Linux / macOS:

```bash
cd backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn src.main:app --reload
```

Windows (PowerShell):

```powershell
cd backend
py -3.12 -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
alembic upgrade head
uvicorn src.main:app --reload
```

## Tests

`backend/tests/` holds unit and contract tests. The safety-suite scripts live in `verticals/<name>/tests/`, and the test-only `demo_coaching` vertical lives in `tests/fixtures/verticals/`.
