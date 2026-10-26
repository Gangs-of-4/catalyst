# Frontend: Try-it page, receptionist desk, clinic settings

**Demo build (ADR-0035):** plain HTML, CSS and JS served by the backend. There is no build step and nothing to `npm install`. The planned Next.js app (ADR-0013) replaces this before the pilot.

| Page | File | Who | Capability |
|---|---|---|---|
| `/` | `index.html`, `static/try.js` | Public: prospects try the agent with a web call and watch the register | C2, C4 |
| `/desk` | `desk.html`, `static/desk.js` | The receptionist: day grid per doctor, walk-ins, statuses, inbox, call log | C7, C10 |
| `/setup` | `setup.html`, `static/setup.js` | Our team or the clinic: settings, leave days, agent sync | C12, C8 |

`/desk` and `/setup` use HTTP Basic auth with `DESK_PASSWORD` (any username). The public page shows first names and an initial only, never phone numbers.

**Design.** The motif is the paper appointment register: ruled rows, one column per doctor, bookings "written in" with ink. Font: Mukta (Devanagari and Latin). Colours: cool off-white paper, deep green-teal ink, saffron for live states, sindoor red only for urgent items. All in `static/app.css`.

**Rules.** Pages hold no business rules and never touch the database. They call the backend API only, and don't keep patient data in browser storage.

## Vapi Web SDK bundle

`static/vapi.bundle.js` is `@vapi-ai/web` **2.7.1** (MIT; it bundles `@daily-co/daily-js`, BSD-2-Clause), built once as an IIFE that sets `window.Vapi`. It is committed so nobody needs Node to run the demo. To rebuild it (Node LTS needed), in an empty folder outside the repo:

```
npm init -y
npm install @vapi-ai/web@2.7.1 esbuild@0.25.10
echo import Vapi from '@vapi-ai/web'; window.Vapi = Vapi; > entry.js
npx esbuild entry.js --bundle --format=iife --minify --platform=browser --target=es2019 --outfile=vapi.bundle.js
```

Then copy `vapi.bundle.js` into `frontend/static/`. Don't move to 3.x without testing; it was days old when this was built.
