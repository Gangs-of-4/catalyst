# Team

Four part-time members on Windows, Linux and macOS. The repo guides; it never blocks. Anyone can work on anything. Work areas exist only so people don't collide.

## Work areas

Owners are TBD (decision D6).

| Area | Covers | Main modules | Owner |
|---|---|---|---|
| A. Voice and phone | Voice stack, forwarding, transfer, failover, latency (C1, C2, transport side of C6) | `providers/voice_orchestrator`, `providers/telephony`, `agents/` | TBD |
| B. Core and schedule | Database, RLS, booking engine, knowledge, agent tools API, setup (C3, C4, C11 data side, C12) | `core/`, `models/`, `booking/`, `knowledge/`, `api/`, `verticals/`, `scripts/` | TBD |
| C. WhatsApp | Doctor control, alerts, reminders, weekly summary (C8, C9, summary side of C10) | `channels/whatsapp/`, `workers/` | TBD |
| D. Safety, web and quality | Safety guard, red flags, safety suite, receptionist screen, call review (C5, C7, review side of C10) | `safety/`, `verticals/clinic/tests/`, `frontend/` | TBD |

## Working agreement

1. **Start with the MVP.** Know which capability (C1–C12) your work moves forward. If the work is outside the MVP, that's fine: either build it or add it to `context/feature-backlog.md`. You decide.
2. **Check for overlap before anything sizeable.** Run `git fetch`, look at remote branches and open PRs touching the same module, and mention any overlap.
3. **Shared contracts.** If you change `context/contracts.md`, say so in the PR description.
4. **When done,** update the module README or docs if behaviour changed, and tick the capability in `context/roadmap.md` if it is now complete.
5. **No personal data** in code, logs, fixtures or docs.

## Light conventions

These are suggestions, not rules.

- Branches named like `feat/booking-slot-lock`, `fix/…`, `docs/…`, `chore/…`.
- Conventional Commits (`feat(booking): …`).
- Use the PR template's checklist as a reminder, not a gate.
- Optional helper commands: `/whats-next`, `/align`, `/new-vertical`, `/standup` (see `.claude/commands/`).
