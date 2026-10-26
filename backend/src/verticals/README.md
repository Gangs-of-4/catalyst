# `backend/src/verticals/`

**Purpose.** Loads and validates `verticals/<name>/` config against `_template/`.

**Capabilities served.** C12, and the dummy-vertical done-criterion

**Contracts used.** `architecture.md` §5; `verticals/_template/vertical.yaml`

**Must not.** Contain vertical-specific behaviour. It only loads and validates.
