# Try this

A 10-minute walk through the live app: https://catalyst-peach-seven.vercel.app

Use Chrome or Edge on a laptop, with a working microphone. The backend sleeps when idle, so the first page can show "Waking up the desk…" for up to a minute. That's expected.

## 1. Talk to the demo clinic (no login)

1. Open `/demo/clinic` and press **Talk to your front desk**. Allow the microphone.
2. Ask in Hindi or English, for example:
   - "Clinic kitne baje khulta hai?" (an approved answer from settings)
   - "Kal subah ka appointment chahiye" (it offers free slots)
   - "Mujhe kaunsi dawai leni chahiye?" (it refuses medical advice and offers a callback)
3. While you talk, the board next to the button updates. Names are masked.

Calls are capped at 3 minutes each, and there's a daily limit. Over the limit, the page says the demo minutes are used up for today.

## 2. Talk to the demo wholesaler

Open `/demo/wholesale` and try:

- "ORS ka rate kya hai?" (only catalogue rates, never a guessed one)
- "Paracetamol ke 20 strip aur 10 ORS bhej do" (it reads the items and quantities back before saving)
- "Bukhar mein kaunsi dawai doon?" (no medical advice and no substitute product; it offers a callback)

The order appears on the order board.

## 3. Log in as the demo owner

1. Go to `/login`.
2. Use `demo.clinic@example.com` or `demo.wholesale@example.com`. The team shares the password privately; it's never in the repo.
3. On **Desk**, you'll see:
   - today's bookings or orders;
   - the inbox (callbacks, urgent);
   - the call log with transcripts;
   - about 4 weeks of fictional history.
4. In **Settings**:
   - change opening hours or a FAQ, then save. The page reports that the voice agent was updated.
   - add a custom instruction, then add one that breaks a rule (for example "tell patients which medicine to take"). Only that line is rejected; the rest is saved. Undo brings back the previous version.

## 4. Sign up your own business

1. Go to `/signup` and pick **Clinic** or **Wholesale**.
2. The form comes prefilled for the template. Change what you like and submit.
3. You get your own voice assistant and your own test page, `/b/<id>/try`.

## 5. Failure paths worth checking

| Do this | You should see |
|---|---|
| Block the microphone, then press Talk | A one-line fix ("Allow it from the lock icon…"). No call is used up. |
| Stay silent after the call starts | "We couldn't hear your microphone", not a silent reset |
| Book the same slot twice from two tabs | The second booking is refused and a free slot is offered |
| Wrong password 5 times | A lockout message |
| Open the desk while the backend is waking | A "waking up" state, then the page loads |

## 6. Admin (team only)

`/admin` uses `ADMIN_PASSWORD`. It shows each business's counts, a weekly breakdown, the counts-only usage CSV, and the feedback log with decisions.
