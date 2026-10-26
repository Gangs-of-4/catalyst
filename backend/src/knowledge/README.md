# `backend/src/knowledge/`

**Purpose.** Doctor-approved answers: storage, retrieval (pgvector), re-embedding after confirmed updates.

**Capabilities served.** C3, C8 (approved updates)

**Contracts used.** `contracts.md` §1.1 (`get_clinic_info`), §3 (`knowledge_entries`)

**Must not.** Return unapproved (`confirmed_at` null) entries to a caller; write without an explicit confirmation.
