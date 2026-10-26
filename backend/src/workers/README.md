# `backend/src/workers/`

**Purpose.** Scheduled and background jobs: reminders, weekly summary, repeating urgent alerts, ops health checks.

**Capabilities served.** C6 (alert repeats), C9, C10 (summary), C11 (ops alerts)

**Contracts used.** `contracts.md` §5 (alert and summary formats)

**Must not.** Place outbound calls or send SMS (Post-MVP, DLT-gated). Scheduler choice is open (D7) — keep jobs as plain functions.
