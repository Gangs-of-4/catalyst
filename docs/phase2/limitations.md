# Known limitations

These are the honest gaps as of 13 Nov 2026, each with the plan to close it.

## Voice

- **The agent can stall after "let me check the slots".** In a live test on 13 Nov, the clinic agent said it would look up slots and then didn't answer until the caller hung up. Not yet diagnosed: it could be a tool timeout, a cold start or a slow database. Next step: read the call's tool log on Render and in Vapi.
- **Spoken phone numbers are hard.** The agent often needs the number repeated, which uses up the 3-minute call cap. The plan is digit-by-digit read-back in the prompt, or taking the caller ID on real phone calls.
- **Web calls only.** There's no real phone number yet (D2, ADR-0030 Proposed). The test page uses Vapi web calls from the browser.
- **The voice stack is hosted outside India** (Vapi). The target is self-hosted Pipecat + Sarvam in India (ADR-0040, Proposed).

## Limits and cost

- **Failed calls still count against the daily cap.** A call is counted when the page asks to start it, so a call that never goes live also uses one up. The fix is to count it only once the call is live.
- **There's no Vapi budget.** Calls are capped at 3 minutes, with a daily cap across all demos and per business. When the free credit ends, calls stop until someone funds it.
- **Cold starts.** The Render free tier sleeps when idle. A keep-alive ping covers the daytime, but the first request at night can take up to a minute.

## Data and security

- **Hosted in Singapore** (Render + Neon), under the residency exception in ADR-0039. No medical data is collected. Revisit before real calls go live.
- **App-level tenant scoping, not Postgres RLS.** Isolation tests cover it. RLS is a stretch goal.
- **One owner per business.** There are no staff roles or OTP login yet (backlog).

## Product

- **WhatsApp runs on the Twilio sandbox.** Each owner number must send the join code first, and sandbox membership expires. Free-form replies only work within 24 hours of the owner's last message.
- **Custom instructions are screened by rules only.** The LLM screen was cut (cut order item 1).
- **No admin "reset demo data" button.** Use `scripts/seed_demo.py`.
- **Some old endpoints remain** (`/api/public-config`, `/api/register`, `/api/staff/meta`). Removing them needs a contracts change.
