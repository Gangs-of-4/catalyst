# `backend/src/providers/telephony/`

**Purpose.** `TelephonyProvider`: inbound answer, transfer, end call. Provider decided by spike S1 / D2.

**Capabilities served.** C1, C6 (live transfer)

**Contracts used.** `architecture.md` §7–8; `contracts.md` §1.8 (`transfer`)

**Must not.** Transfer to the forwarding clinic number (loop). Place outbound calls outside the DLT gate (Post-MVP).
