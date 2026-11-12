# Scripts

Ops CLIs that our team runs, not end users. Run them from the repo root with the backend venv active.

## CI

- `python scripts/check_provider_boundary.py` fails if any file in `backend/src/` outside `providers/` imports a vendor SDK or names a vendor API host. CI runs it on every PR.

## Demo build (ADR-0035)

- `python scripts/setup_vapi.py` creates the clinic's Vapi assistant on the first run and updates it after. It writes `VAPI_ASSISTANT_ID` and `CATALYST_TOOL_SECRET` into `.env` and prints the page and Twilio webhook URLs. Rerun it whenever the tunnel URL changes.
- `python scripts/doctor.py` checks every `.env` value, the tunnel, the Vapi key and assistant (including a stale webhook URL), and the Twilio credentials, in plain words.

## Phase 2 demo data (M9)

- `python scripts/seed_demo.py` resets the two demo businesses (`demo-clinic`, `demo-wholesale`): it clears their bookings, orders, catalogue, calls, inbox and events, then seeds today's data and the last 4 weeks of fictional usage again, anchored to today. Settings and the demo logins stay. It uses `DATABASE_URL` when set (the deployed database), else the local SQLite file. Run it before a demo, or monthly, so the history stays fresh until the program ends. It replaces the admin page's reset button (cut, phase2-plan cut order 3).

## Planned

### Clinic setup CLI (C12)

`setup-tenant`: sets up a clinic with one command from a tenant config file plus `verticals/<name>/`.

- Validates the config against the vertical template.
- Rejects a contact chain that contains a forwarding number.
- Requires at least one registered WhatsApp sender.
- Seeds the approved knowledge, resources and availability.

Tenant config files contain personal data (phone numbers), so they **never** go in the repo.

### Call review CLI (C10)

`review-calls`: lists the week's calls flagged `misunderstood`, plus a sample of the rest, for the weekly team review. It also prints the misunderstood share.

Transcripts are read from our database and never written to files in the repo.
