# Spikes (Week 1)

Run these before heavy building. Each spike answers one question with evidence. Fill in **Result** and **Decision** when done, and link any recordings or data. The data itself (consented call audio) stays outside the repo.

## S1 — Call forwarding into the voice stack

- **Question:** Can a call forwarded from an Indian SIM or landline reach the chosen voice stack reliably? Does an Indian telephony provider (e.g. Exotel) have to sit in between?
- **Plan:**
  1. Set conditional forwarding (busy, no answer, unreachable) from a test SIM to a candidate number.
  2. Call it from several networks, at busy and at no-answer.
  3. Test transfer out to a separate mobile.
  4. Check caller-ID passthrough.
- **Regulatory:** VERIFY whether a foreign virtual number may receive forwarded Indian calls, and what an Indian provider requires (KYC, DLT for inbound vs outbound).
- **Feeds:** D2 / ADR-0030, D1.
- **Owner:** TBD · **Result:** _pending_ · **Decision:** _pending_

## S2 — Hinglish speech-to-text

- **Question:** Which of 2–3 STT options handles Hinglish clinic-style calls, Indian names and dates best?
- **Plan:**
  1. Collect a small set of real recorded Hinglish clinic-style calls **with consent**.
  2. Transcribe each with every candidate.
  3. Compare word error rate on names, dates and times ("kal shaam 5 baje"), plus latency.
- **Feeds:** D1, C2.
- **Owner:** TBD · **Result:** _pending_ · **Decision:** _pending_

## S3 — Latency and voice acceptance

- **Question:** What is the real end-to-end latency on the chosen stack, including our custom-LLM guard hop? Do older listeners accept the voice?
- **Plan:**
  1. Measure the time from end of caller speech to the first audio of the reply, over 20+ turns; report p50 and p95.
  2. Have a few older people listen to sample calls and say whether they'd stay on the line.
- **Target:** under ~1 s (C2). ADR-0015 assumed 1.2–2 s for self-hosted.
- **Feeds:** D1, ADR-0015.
- **Owner:** TBD · **Result:** _pending_ · **Decision:** _pending_
