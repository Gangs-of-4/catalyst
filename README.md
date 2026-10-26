# Catalyst

An AI front-desk assistant for small Indian businesses. It answers the phone the way a polite receptionist would. Our team sets it up, and the owner controls it from WhatsApp, never from a complicated dashboard.

**First customer type: small clinics.** Coaching institutes come next.

> **North star:** A small clinic never misses a patient call. The agent answers, books correctly into one shared schedule, and sends anything medical to a human. The doctor controls everything from WhatsApp.

## Status

**Demo build (`feat/demo-mvp`).** A working, demo-able clinic voice agent for a fictional Lucknow dental clinic. A prospect opens our web page and talks to the agent in Hindi, English or Hinglish, then watches a booking appear in the clinic's register. The receptionist runs the day from `/desk`, and the doctor controls the schedule from WhatsApp. The demo takes shortcuts (SQLite, plain HTML pages, web calls, a post-call safety flag instead of the in-call guard), each recorded in **ADR-0035** with a "before the first real clinic pilot" revisit trigger. **It must not take real patient calls.**

The voice stack is decided (Vapi, ADR-0029). A real pilot number (D2, ADR-0030) is still open.

## Where to read

| You want… | Read |
|---|---|
| What we're building and when it's done | `context/mvp.md` |
| What's next | `context/roadmap.md` |
| How it fits together | `context/architecture.md`, `context/contracts.md` |
| What's decided and what's open | `context/decisions.md` |
| Who works on what | `context/team.md` |
| Instructions for coding agents | `CLAUDE.md` (also `AGENTS.md`) |

## Quickstart: run the demo

You need **Git**, **Python 3.11 or newer**, and **cloudflared** (Windows: `winget install --id Cloudflare.cloudflared`). Node is not needed. You also need a **Vapi** account (private and public keys), and optionally a **Twilio** account with the WhatsApp sandbox.

### Windows (PowerShell)

1. Get the code and make a virtual environment:
   ```powershell
   git clone https://github.com/Gangs-of-4/catalyst.git
   cd catalyst\backend
   python -m venv .venv
   ```
2. Activate it:
   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```
   If PowerShell blocks the script, run this once, then activate again:
   ```powershell
   Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
   ```
3. Install, and create your settings file in the repo root:
   ```powershell
   pip install -r requirements.txt
   Copy-Item ..\.env.example ..\.env
   ```
   Open `.env` and fill in `VAPI_PRIVATE_KEY` and `VAPI_PUBLIC_KEY` (Vapi dashboard → API Keys), plus `DESK_PASSWORD`. Fill in the Twilio values if you have them.
4. Start the server (leave this window open):
   ```powershell
   uvicorn src.main:app --port 8000
   ```
   The first start creates `backend/data/clinic.db` with the fictional clinic and a few bookings.
5. In a **second** PowerShell window, open a public HTTPS tunnel:
   ```powershell
   cloudflared tunnel --url http://localhost:8000
   ```
   Copy the `https://….trycloudflare.com` URL it prints into `PUBLIC_URL` in `.env`. There's no need to restart the server: it re-reads `.env` on every request.
6. In a **third** window, from the repo root with the venv active (`.\backend\.venv\Scripts\Activate.ps1`), create the agent:
   ```powershell
   python scripts\setup_vapi.py
   ```
   This writes `VAPI_ASSISTANT_ID` and `CATALYST_TOOL_SECRET` into `.env`, and prints the URLs you need next.
7. **WhatsApp (optional).** In the Twilio console → Messaging → Try it out → WhatsApp sandbox: join the sandbox from the doctor's phone (send the `join <code>` message it shows), then set **"When a message comes in"** to `<PUBLIC_URL>/whatsapp/incoming` (method POST). On `<PUBLIC_URL>/setup`, add the doctor's number under "WhatsApp numbers".
8. Open `<PUBLIC_URL>/` and click **Talk to the receptionist**. Allow the microphone.

To check everything at once: `python scripts\doctor.py`. It says what's missing in plain words, including a stale tunnel URL.

**When the tunnel URL changes** (every time cloudflared restarts): update `PUBLIC_URL` in `.env`, rerun `python scripts\setup_vapi.py`, and paste the new `<PUBLIC_URL>/whatsapp/incoming` into the Twilio sandbox settings.

### Deploy on Render (free tier)

`render.yaml` describes the service. In Render, choose **New → Blueprint**, pick this repo and the `feat/demo-mvp` branch, and fill in the values it asks for. Real environment variables override `.env`. The SQLite file lives in `/tmp`, so data resets on every restart or deploy. A sleeping free service takes about a minute to wake, so the Vapi tool timeout is 90 s. When you have the Render URL, set `PUBLIC_URL` to it in your local `.env`, run `python scripts/setup_vapi.py` locally, and copy `PUBLIC_URL`, `VAPI_ASSISTANT_ID` and `CATALYST_TOOL_SECRET` into Render's Environment settings.

### Linux / macOS

Same steps, with these commands: `python3 -m venv .venv && source .venv/bin/activate`, `cp ../.env.example ../.env`, and `python scripts/setup_vapi.py`.

### Tests

```
cd backend
pytest
```

All Vapi and Twilio traffic is mocked in tests. No keys are needed.

### Pages

| URL | Who | |
|---|---|---|
| `/` | Prospects (public) | Web call to the agent, live transcript, the clinic register with masked names |
| `/desk` | The receptionist (password) | Day grid per doctor, walk-ins, Arrived / No-show / Done / Cancel, urgent inbox, call log, send summary |
| `/setup` | Our team or the clinic (password) | Clinic facts, hours, doctors, fees, FAQs, red flags, WhatsApp numbers, voice, leave days |

### A 5-minute demo for a clinic

Open `/` on the laptop and `/desk` on a second screen, with the doctor's WhatsApp to hand.

1. **Timings.** Ask "Clinic kab khulta hai? Sunday ko?" It answers from the clinic's own settings only.
2. **Book.** "Kal shaam 5 baje appointment chahiye." It asks your name and number and reads the number back. It offers free slots near 5 pm, reads back day, date, time and doctor, and books after your yes.
3. **Watch the register.** The booking is written into tomorrow's page on `/` within 3 seconds, and appears on `/desk`.
4. **Safety.** Say "Kal daant nikalwaya tha, khoon ruk hi nahi raha." It gives the emergency instruction, gives no medical advice, and escalates. An urgent item appears at the top of the desk inbox, and the doctor gets a 🔴 URGENT WhatsApp.
5. **Doctor control.** The doctor sends "kal chhutti" on WhatsApp. The reply is a preview ("Poori clinic — kal (…) chhutti … Sahi hai? Haan/Nahi"). They answer "Haan" and get "Done ✅". Tomorrow's bookings move to the callback list.
6. **Ask again.** Call again and ask for "kal". The agent says the clinic is closed tomorrow and offers the next open day.

Also good: "aaj ke appointments" on WhatsApp, "consultation fee 400" → Haan (then ask the agent the fee), and **Send summary to doctor** on the desk.

### What's next (before a real clinic)

- **Real number forwarding** (C1, ADR-0030): the clinic's number forwards missed and after-hours calls to the agent.
- **Custom-LLM safety guard** (ADR-0032): our code checks every reply *before* it is spoken. Today the demo only flags calls afterwards.
- **Reminders** (C9) on approved WhatsApp templates, and the Meta WhatsApp Business Platform instead of the sandbox (D5).
- **Postgres** with `tenant_id`, RLS and the overlap exclusion constraint, replacing SQLite (ADR-0010, ADR-0016, ADR-0033).
- Live transfer and the backup chain (C6), health alerts (C11), and the 50+ call safety suite at 100% (C5).

## Repo layout

```
context/      product, contracts, architecture, decisions, roadmap, team
verticals/    customer types as config (clinic = DRAFT)
backend/      Python 3.12 + FastAPI; module skeleton under backend/src/
frontend/     demo pages: Try-it, desk, setup (plain HTML; Next.js later)
scripts/      ops CLIs (clinic setup, call review)
.claude/      optional Claude Code helper commands
mcp/ open-source/   integration notes and dependency licences
```

## Team

A four-person, part-time student team. See `context/team.md`.

## License

MIT. See `LICENSE`.
