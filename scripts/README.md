# Scripts

Ops CLIs that our team runs, not end users. Run them from the repo root with the backend venv active.

## Demo build (ADR-0035)

- `python scripts/setup_vapi.py` creates the clinic's Vapi assistant on the first run and updates it after. It writes `VAPI_ASSISTANT_ID` and `CATALYST_TOOL_SECRET` into `.env` and prints the page and Twilio webhook URLs. Rerun it whenever the tunnel URL changes.
- `python scripts/doctor.py` checks every `.env` value, the tunnel, the Vapi key and assistant (including a stale webhook URL), and the Twilio credentials, in plain words.

## Planned

## Clinic setup CLI (C12)

`setup-tenant`: sets up a clinic with one command from a tenant config file plus `verticals/<name>/`.

- Validates the config against the vertical template.
- Rejects a contact chain that contains a forwarding number.
- Requires at least one registered WhatsApp sender.
- Seeds the approved knowledge, resources and availability.

Tenant config files contain personal data (phone numbers), so they **never** go in the repo.

## Call review CLI (C10)

`review-calls`: lists the week's calls flagged `misunderstood`, plus a sample of the rest, for the weekly team review. It also prints the misunderstood share.

Transcripts are read from our database and never written to files in the repo.
