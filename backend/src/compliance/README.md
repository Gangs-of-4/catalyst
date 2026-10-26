# `backend/src/compliance/` [Post-MVP parts noted]

**Purpose.** PII guard helpers, consent records; the fail-closed outbound DLT gate, calling window, DND (Post-MVP).

**Capabilities served.** C9 (opt-out respected), C11

**Contracts used.** `architecture.md` §9, §12

**Must not.** Default the DLT gate to allow. Hold the clinical safety guard (that is `safety/`).
