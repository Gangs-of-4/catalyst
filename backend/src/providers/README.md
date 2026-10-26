# `backend/src/providers/`

**Purpose.** The provider abstraction layer. The ONLY place vendor SDKs are imported (ADR-0014).

**Capabilities served.** C1, C2 (indirectly all voice capabilities)

**Contracts used.** `architecture.md` §8 interfaces

**Must not.** Contain business logic. Leak vendor types outside this package.
