# `backend/src/providers/voice_orchestrator/`

**Purpose.** `VoiceOrchestrator` interface: managed platform (pilot, if ADR-0029 is accepted) or Pipecat (long-term).

**Capabilities served.** C1, C2, C6 (failover message)

**Contracts used.** `architecture.md` §8; `contracts.md` §1 (the voice layer calls these tools)

**Must not.** Hold booking, knowledge or safety logic — the voice layer only talks (ADR-0032).
