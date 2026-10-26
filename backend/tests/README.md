# Backend tests

Planned MVP tests (`context/coding-rules.md` → Testing):

- **Tool contracts:** every `/v1/tools/*` endpoint matches `context/contracts.md` §1.
- **Double-booking:** concurrent `book` calls on one slot produce exactly one booking (exclusion constraint).
- **Dummy vertical:** `fixtures/verticals/demo_coaching/` loads and validates with no core change.
- **Safety suite runner:** runs `verticals/<name>/tests/safety-suite.yaml`; the clinic must pass at 100%.
- **RLS:** tenant A can never read tenant B's rows.
- **WhatsApp:** no write happens without "Haan", and unregistered senders are ignored.
- **Provider contracts:** one shared suite per interface.

Fixtures use fake data only.
