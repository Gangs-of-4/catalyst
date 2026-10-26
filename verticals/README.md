# Verticals

Each customer type is config, not code (ADR-0033). Core code never branches on vertical.

| Folder | Status |
|---|---|
| `_template/` | Copy-to-start. Every key here must exist in each vertical. |
| `clinic/` | **DRAFT, team to review.** The MVP vertical. |

Start a new one with `/new-vertical <name>`, or copy `_template/` by hand. The test-only `demo_coaching` fixture lives in `backend/tests/fixtures/verticals/`, not here.

No real names, clinic names or phone numbers in any vertical file. Use `{placeholders}`.
