# `backend/src/channels/whatsapp/`

**Purpose.** Owner commands with preview-and-confirm, urgent alerts, summaries, patient reminders and STOP opt-out. One sandbox number serves every business: `api/whatsapp.py` finds the business from the sender (`tenancy.for_sender`). `commands.py` holds the bookings (clinic) commands and the shared flow; `order_commands.py` the orders (wholesale) ones: today's orders, order status, rate, stock in/out, summary.

**Capabilities served.** C6 (alerts), C8, C9, C10 (summary)

**Contracts used.** `contracts.md` §4 (command format), §5 (alert/summary formats)

**Must not.** Apply any write without an explicit "Haan" (ADR-0017, ADR-0034); accept commands from a number no business owns or lists; guess a product name; send promotional messages.
