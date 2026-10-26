# `backend/src/channels/whatsapp/`

**Purpose.** Doctor commands with preview-and-confirm, urgent alerts, weekly summary, patient reminders and STOP opt-out.

**Capabilities served.** C6 (alerts), C8, C9, C10 (summary)

**Contracts used.** `contracts.md` §4 (command format), §5 (alert/summary formats)

**Must not.** Apply any write without an explicit "Haan" (ADR-0017, ADR-0034); accept commands from unregistered numbers; send promotional messages.
