# Frontend: receptionist web app (C7)

Placeholder. There is no code yet.

**Purpose.** One responsive web app on the device already at the clinic desk.
- Today's bookings from every channel, tagged by source.
- One column per doctor (per resource; the label comes from `vertical.yaml`).
- Add walk-in and WhatsApp bookings.
- Mark a booking arrived, no-show or done.
- A callback and urgent inbox with "mark done".

**Stack** (already chosen in the repo): Next.js App Router, TypeScript strict, Tailwind and shadcn/ui. Hosting is per ADR-0013. VERIFY that it still fits once D3 is decided.

**Design bar.** Big buttons, and learnable in 15 minutes. Login is a simple clinic login; OTP, roles and an audit log are Phase 2 (item 88).

**Contracts.** The backend REST API only (`backend/src/api/`). It uses the same booking rules as phone and WhatsApp, and a double-booking attempt returns `SLOT_TAKEN`.

**Must not.**
- Hold business rules.
- Talk to the database directly.
- Store patient data in browser storage beyond the session.

## Run (target commands)

From `frontend/`, the commands are the same on Windows, Linux and macOS:

```
npm install
npm run dev
```
