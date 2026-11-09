# Frontend: Try-it page, receptionist desk, clinic settings

**Demo build (ADR-0035):** plain HTML, CSS and JS served by the backend. There is no build step and nothing to `npm install`. The planned Next.js app replaces this before the pilot.

**Hosting (ADR-0036):** the same files are deployed to Vercel by `.github/workflows/deploy-frontend.yml` on every push to `main` that touches `frontend/`. See [Deploying to Vercel](#deploying-to-vercel).

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

## Deploying to Vercel

Production deploys come only from GitHub Actions (`.github/workflows/deploy-frontend.yml`); Vercel's Git integration is off (`vercel.json`). The workflow runs `vercel pull`, `vercel build --prod` and `vercel deploy --prebuilt --prod`. Because the repo is public, Vercel Hobby deploys a merge by any teammate (its commit-author check applies only to private org repos). **Keep the repo public**; see ADR-0036. GitHub records the deployed SHA under the `production` environment.

- `vercel.json` runs `node build.mjs`, which copies the pages and `static/` into `dist/` and writes `dist/static/config.js` from `NEXT_PUBLIC_API_URL`.
- `NEXT_PUBLIC_API_URL` is the backend's public HTTPS URL, set in the Vercel project's **Production** environment variables. Empty = same-origin `/api` (local FastAPI behaviour). The backend must list the Vercel domain in `CORS_ALLOWED_ORIGINS`.
- Vercel only serves files. Never add rewrites or functions that proxy `/api` — patient data must not pass through non-India infrastructure (rule 4).
- `/desk` and `/setup` use Basic auth, which browsers don't prompt for cross-origin. With `DESK_PASSWORD` set they won't work from Vercel until auth changes (ADR-0036).

One-time setup: Vercel project with Root Directory `frontend` and no Git connection; repo secrets `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID`.
