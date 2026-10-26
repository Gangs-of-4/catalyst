# Scripts

Placeholders. There is no code yet. These are ops CLIs that our team runs, not end users.

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
