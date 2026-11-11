# Verticals

Each customer type is config, not code (ADR-0033). Core code never branches on vertical. `modules` in `vertical.yaml` (`bookings` or `orders`) picks the data model and desk board; `tools` lists the agent tools served. The optional `try_saying` list shows example lines on the public test page. A template has a voice agent once it has `agent-prompt.md` (clinic and wholesale do). `backend/src/verticals/loader.py` `validate()` checks every vertical, and `backend/tests/test_verticals.py` runs it on each folder.

| Folder | Status |
|---|---|
| `_template/` | Copy-to-start. Every key here must exist in each vertical. |
| `clinic/` | **DRAFT, team to review.** The MVP vertical. Module: `bookings`. |
| `wholesale/` | **DRAFT, team to review.** Wholesale distributors (ADR-0037). Module: `orders`. `vertical.yaml` only so far; prompt, rules and safety suite land with the wholesale milestone. |

Start a new one with `/new-vertical <name>`, or copy `_template/` by hand. The test-only `demo_coaching` fixture lives in `backend/tests/fixtures/verticals/`, not here.

No real names, clinic names or phone numbers in any vertical file. Use `{placeholders}`.
