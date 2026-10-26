# `backend/src/providers/llm/`

**Purpose.** `LLMProvider` interface and implementations (live-call and offline).

**Capabilities served.** C2, C3, C8 (WhatsApp parsing)

**Contracts used.** `architecture.md` §8; `contracts.md` §2

**Must not.** Skip the safety guard on clinic calls — the guard is applied by `safety/`, callers must not bypass it.
