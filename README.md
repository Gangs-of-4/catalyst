# Catalyst

An AI front-desk assistant for small Indian businesses. It answers the phone the way a polite receptionist would. Our team sets it up, and the owner controls it from WhatsApp, never from a complicated dashboard.

**First customer type: small clinics.** Coaching institutes come next.

> **North star:** A small clinic never misses a patient call. The agent answers, books correctly into one shared schedule, and sends anything medical to a human. The doctor controls everything from WhatsApp.

## Status

**Pre-code.** The MVP, contracts, architecture and module skeleton are defined, but no feature code exists yet. We are at **M0: foundation and week-1 spikes** (`context/roadmap.md`).

Two big decisions are still open: the voice stack for the pilot (D1) and a real phone number for the pilot (D2). Both are in `context/decisions.md`.

## Where to read

| You want… | Read |
|---|---|
| What we're building and when it's done | `context/mvp.md` |
| What's next | `context/roadmap.md` |
| How it fits together | `context/architecture.md`, `context/contracts.md` |
| What's decided and what's open | `context/decisions.md` |
| Who works on what | `context/team.md` |
| Instructions for coding agents | `CLAUDE.md` (also `AGENTS.md`) |

## Quickstart

These are target commands. They become runnable as M0 lands.

**Prerequisites:**
- Git
- Python 3.12
- Node.js LTS
- Docker with Compose (on Windows and macOS this usually means Docker Desktop; VERIFY its licence terms for the team, see `open-source/open-source.md`)

### Windows (PowerShell)

```powershell
git clone https://github.com/Gangs-of-4/catalyst.git; cd catalyst
Copy-Item .env.example .env        # fill in values from the team; never commit .env
docker compose up -d               # Postgres + pgvector (from M0)

cd backend
py -3.12 -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn src.main:app --reload

cd ..\frontend
npm install; npm run dev
```

If PowerShell blocks the venv activation script, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once.

### Linux / macOS

```bash
git clone https://github.com/Gangs-of-4/catalyst.git && cd catalyst
cp .env.example .env               # fill in values from the team; never commit .env
docker compose up -d               # Postgres + pgvector (from M0)

cd backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn src.main:app --reload

cd ../frontend
npm install && npm run dev
```

## Repo layout

```
context/      product, contracts, architecture, decisions, roadmap, team
verticals/    customer types as config (clinic = DRAFT)
backend/      Python 3.12 + FastAPI; module skeleton under backend/src/
frontend/     receptionist web app (Next.js)
scripts/      ops CLIs (clinic setup, call review)
.claude/      optional Claude Code helper commands
mcp/ open-source/   integration notes and dependency licences
```

## Team

A four-person, part-time student team. See `context/team.md`.

## License

MIT. See `LICENSE`.
