# Frontend: Try-it page, receptionist desk, clinic settings

> **Changing (ADR-0042, 2026-11-11):** this folder becomes a **Vite + React + TypeScript + Tailwind + shadcn/ui** app during Phase 2 M8, one page per PR. Until a page's React version merges, the static page below still works as described. Rules for the new app are in `context/coding-rules.md` (Frontend).

**Demo build (ADR-0035):** plain HTML, CSS and JS served by the backend. There is no build step and nothing to `npm install`.

**Hosting (ADR-0036):** the same files are deployed to Vercel by `.github/workflows/deploy-frontend.yml` after CI passes on every push to `main`. See [Deploying to Vercel](#deploying-to-vercel).

| Page | File | Who | Capability |
|---|---|---|---|
| `/` | `index.html`, `static/try.js` | Public: prospects try the agent with a web call and watch the register | C2, C4 |
| `/desk` | `desk.html`, `static/desk.js` | The receptionist: day grid per doctor, walk-ins, statuses, inbox, call log | C7, C10 |
| `/setup` | `setup.html`, `static/setup.js` | Our team or the clinic: settings, leave days, agent sync | C12, C8 |

`/desk` and `/setup` use HTTP Basic auth with `DESK_PASSWORD` (any username). The public page shows first names and an initial only, never phone numbers.

**Design.** The motif is the paper appointment register: ruled rows, one column per doctor, bookings "written in" with ink. Font: Mukta (Devanagari and Latin). Colours: cool off-white paper, deep green-teal ink, saffron for live states, sindoor red only for urgent items. All in `static/app.css`.

**Rules.** Pages hold no business rules and never touch the database. They call the backend API only, and don't keep patient data in browser storage.

## React app (`app/`, ADR-0042)

The new frontend: **Vite + React + TypeScript + Tailwind + shadcn/ui**. It grows one page per PR during Phase 2 M8. Until a page moves here, its old static version above keeps working.

**Run it locally** (needs Node 24 LTS; 20.19+ works):

```
cd frontend/app
npm ci
npm run dev          # http://localhost:5173
```

Start the backend too (`uvicorn` on port 8000, see the repo README). The dev server forwards `/api`, `/vapi` and `/healthz` to it, so the login cookie works as same-origin. To use another backend, set `CATALYST_BACKEND_URL`.

| Command | What it does |
|---|---|
| `npm run dev` | Dev server with hot reload |
| `npm run lint` / `npm run typecheck` | ESLint / TypeScript strict (CI runs both) |
| `npm test` | Vitest unit tests (CI) |
| `npm run check:contrast` | WCAG AA check of the colour tokens in `src/index.css` (CI) |
| `npm run build` | Production build into `app/dist/` |

**Layout:**
- `src/index.css`: the design tokens (CSS variables → Tailwind).
- `src/components/ui/`: shadcn-style primitives.
- `src/components/`: shared Catalyst pieces (Field, OfflineBanner, EmptyState, AppHeader).
- `src/lib/api.ts`: the only way to call the backend. It uses relative `/api` paths, adds the CSRF header and turns errors into plain sentences.
- `src/pages/`: one file per route.

**Pages so far:**

| Route | File | What |
|---|---|---|
| `/signup` | `src/pages/signup.tsx`, `src/features/signup/` | Self-serve onboarding: account + business in one step (`GET /api/templates`, `POST /api/signup`). The template section is picked by the template's `modules`. A success screen shows the voice agent's state. |
| `/styleguide` | `src/pages/styleguide.tsx` | Every token and component, for review |

**Design:** `frontend/DESIGN.md` is the source of truth. `/styleguide` shows every token and component. Check new work there at 360px and desktop width.

**Adding a page:**
1. Add the route in `src/App.tsx`.
2. Add a rewrite for its path to `/app` in `frontend/vercel.json`. Use `/app`, not `/app.html`: with `cleanUrls` on, Vercel serves the shell at `/app`, and a rewrite to `/app.html` returns 404.
3. Delete the old static page in the same PR, if there is one.

**Deploy:** `build.mjs` builds the app, puts its shell at `dist/app.html` and its files in `dist/assets/`, then copies the old pages as before. `vercel.json` rewrites React routes (now: `/signup`, `/styleguide`) to `/app`, where Vercel serves `dist/app.html` because `cleanUrls` is on.

**Rules:** see `context/coding-rules.md` (Frontend).
- Never put patient or customer data in browser storage.
- Never call the backend by absolute URL.
- Never log personal data (ESLint blocks `console.log`).

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
- Vercel only serves files. *ADR-0041 (Proposed) would add one `/api` rewrite to the backend for first-party cookies; no functions or middleware.*
- `/desk` and `/setup` use Basic auth, which browsers don't prompt for cross-origin. With `DESK_PASSWORD` set they won't work from Vercel until auth changes (ADR-0036).

One-time setup: Vercel project with Root Directory `frontend` and no Git connection; repo secrets `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID`.
