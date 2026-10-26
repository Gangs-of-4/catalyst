# `backend/src/booking/`

**Purpose.** Resources, services, availability rules, blocks and bookings; slot finding.

**Capabilities served.** C4, C7, C8 (schedule changes)

**Contracts used.** `contracts.md` §1.2–1.5, §3 (schema + exclusion constraint)

**Must not.** Rely on app-level checks alone for double-booking — the DB constraint is the source of truth. No clinic-only names.
