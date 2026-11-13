# Deploy

Everything runs on free tiers (ADR-0039, Proposed). Secrets live only in the Render, Vercel and GitHub dashboards, never in the repo or in chat.

| Part | Where | Notes |
|---|---|---|
| Frontend | Vercel, `catalyst-peach-seven.vercel.app` | Deployed by GitHub Actions after CI passes on `main` (ADR-0036). `/api/*` is rewritten to Render, so cookies are first-party (ADR-0041). |
| Backend | Render free web service, Singapore, root `backend/` | Health check `/healthz`. It sleeps after about 15 min idle; spin-up takes up to a minute (VERIFY). |
| Database | Neon free Postgres, Singapore | Use the **pooled** connection string as `DATABASE_URL`. Local development uses SQLite. Never point local tests at Neon. |
| Keep-alive | cron-job.org | Pings `/healthz` every 10 min in the daytime, so demos rarely hit a cold start. |
| Voice | Vapi | Our backend creates and updates one assistant per business at startup and on settings save. |

## Backend environment (Render)

Names only. Values are in the Render dashboard. `.env.example` explains each one.

| Group | Variables |
|---|---|
| Required | `DATABASE_URL`, `SESSION_SECRET`, `PUBLIC_URL` (the Render URL), `PUBLIC_APP_URL` (the Vercel URL), `ADMIN_PASSWORD` (16+ characters) |
| Voice | `VAPI_PRIVATE_KEY`, `VAPI_PUBLIC_KEY`, `VAPI_MAX_CALL_SECONDS` (180) |
| Call caps | `DEMO_CALLS_PER_DAY`, `CALLS_PER_BUSINESS_PER_DAY` |
| Demo data | `DEMO_LOGIN_PASSWORD`, `DEMO_VOICE=1` (refresh the demo assistants at startup), `DEMO_HISTORY=1` (4 weeks of fictional history, added once) |
| Optional | the `TWILIO_*` variables for the WhatsApp sandbox, and `GROQ_API_KEY` |

## Checks after a deploy

1. `GET /healthz` returns 200.
2. Run `python scripts/doctor.py` against the live URL.
3. Log in with the demo login, open the desk and confirm today's data is there.
4. Make one call on `/demo/clinic` and check its transcript on the desk.

## Reset the demo data

Run `python scripts/seed_demo.py` with `DATABASE_URL` set in your shell, not in a file. It re-anchors the fictional data to today.
