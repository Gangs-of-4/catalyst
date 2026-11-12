# Frontend: Try-it page, receptionist desk, clinic settings

> **Changing (ADR-0042, 2026-11-11):** this folder becomes a **Vite + React + TypeScript + Tailwind + shadcn/ui** app during Phase 2 M8, one page per PR. Until a page's React version merges, the static page below still works as described. Rules for the new app are in `context/coding-rules.md` (Frontend).

**Demo build (ADR-0035):** plain HTML, CSS and JS served by the backend. There is no build step and nothing to `npm install`.

**Hosting (ADR-0036):** the same files are deployed to Vercel by `.github/workflows/deploy-frontend.yml` after CI passes on every push to `main`. See [Deploying to Vercel](#deploying-to-vercel).

| Page | File | Who | Capability |
|---|---|---|---|
| `/setup` | `setup.html`, `static/setup.js` | Our team or the clinic: settings, leave days, agent sync | C12, C8 |

`/desk` and `/setup` need the owner's session login (`/api/login`); they show only that business's data, and without a session they show a "Please log in" link. The public page shows first names and an initial only, never phone numbers.

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
| `/` | `src/pages/landing.tsx`, `src/components/feature-card.tsx` | Public landing page, mobile first: what Catalyst does, how it works, who it's for, the safety rules, and links to sign up, log in and try a demo call. On phones the main action stays in a bar pinned to the bottom. Needs no backend, so no `WakeGate`. The old static `index.html` is no longer deployed |
| `/b/:publicId/try` | `src/pages/try.tsx`, `src/features/try/` | Public test page for one business: talk to its front desk (Vapi web call, after the `POST /api/try/{id}/start` cap check) and watch its register or order board update. Covers voice-not-switched-on, minutes-used-up and microphone-blocked states. Endpoint shapes: issue #24 |
| `/demo/:template` | `src/pages/try.tsx` | Opens the demo business's test page (`/b/demo-<template>/try`) |
| `/login` | `src/pages/login.tsx` | Owner login (`POST /api/login`). Already logged in → straight on. Honors a same-app `?next=` path |
| `/desk` | `src/pages/desk.tsx`, `src/features/desk/` | The receptionist's desk for a business that keeps a schedule (`GET /api/desk/day`, `POST /api/desk/bookings`, `POST /api/desk/bookings/{id}/status`, `/api/inbox`, `/api/calls`, `/api/stats`). **Phones:** one doctor per tab, earlier empty times folded away, an urgent-inbox banner, inbox and calls below. **Wide screens:** doctors side by side, inbox and calls on the right. Walk-ins open a bottom sheet; a taken slot offers the free times nearby as one-tap choices and keeps what was typed. Cancel asks first. Refreshes every 5 s, paused while a form is open. A business without the bookings module (the register answers `404`) gets the **order board** instead: orders as cards, newest first, with Open/New/Confirmed/Dispatched/Done filters and today's counts. Each card has one button for the next status, and Cancel sits in its menu and asks first. The add-order form (shop, phone, type-ahead products with qty, a running total, and an idempotency key so a resend never doubles an order) is in the right column on wide screens. On phones it opens from a pinned "New order" button, and closing it keeps the draft. `DUPLICATE_ORDER` points to the open order with "Save as a new order". `TRY_AGAIN` saves again once by itself. The counts strip and filter counts cover the orders loaded so far (the newest 50, plus any older pages opened); an exact count across all orders would need a backend count or `?status=` call later. `/api/orders`, `/api/orders/{id}/status` and `/api/catalog` (code in `src/features/orders/`). The old `desk.html` is no longer deployed; it stays only because the backend still serves it at `localhost:8000/desk` |
| `/home` | `src/pages/home.tsx` | The owner's signed-in home (`GET /api/me`), with Log out. Logged-out visitors go to `/login?next=/home`. Links to the test page and the desk; settings come later |
| `/signup` | `src/pages/signup.tsx`, `src/features/signup/` | Self-serve onboarding: account + business in one step (`GET /api/templates`, `POST /api/signup`), **one step per screen** (1/3 You, 2/3 Your business, 3/3 the template section + optional + consent) with Back/Next in a bar pinned to the bottom on phones. Next checks only that step; the step is in the URL (`?step=2`) so the phone's back button goes to the previous step. The template section is picked by the template's `modules`. A success screen shows the voice agent's state. |
| `/styleguide` | `src/pages/styleguide.tsx` | Every token and component, for review. **Local only** (`npm run dev`): it isn't part of the live site |

**Failure states** (phase2-plan §5 cold starts, §6):
- Pages that need the backend (`/signup`, `/login`, `/home`, `/desk`, `/b/:publicId/try`) sit behind `WakeGate`, wired in `src/App.tsx`. It pings `/healthz` and shows a "waking up" screen while the free backend host wakes.
- `ConnectionBanner` appears when an API call can't reach the backend mid-session, and retries with backoff. When it reconnects it fires a `catalyst:reconnected` window event that pages can listen for.
- The test page checks `/healthz` again before each call ("Waking up the desk… (up to a minute)") if it hasn't seen the backend lately.
- Forms keep what the owner typed through all of this; nothing is cleared on a failed request.

**Design:** `frontend/DESIGN.md` is the source of truth. `/styleguide` (local `npm run dev` only) shows every token and component. Check new work there at 360px and desktop width.

**Adding a page:**
1. Add the route in `src/App.tsx`.
2. Add a rewrite for its path to `/app` in `frontend/vercel.json`. Use `/app`, not `/app.html`: with `cleanUrls` on, Vercel serves the shell at `/app`, and a rewrite to `/app.html` returns 404.
3. Delete the old static page in the same PR, if there is one. (Exception: the old try page, `index.html` with `static/try.js` and `static/vapi.bundle.js`, is no longer deployed but stays for now because the backend still serves it at `localhost:8000/` for local backend-only use. It goes in a follow-up together with that backend route.)

**Deploy:** `build.mjs` builds the app, puts its shell at `dist/app.html` and its files in `dist/assets/`, then copies the old pages as before. `vercel.json` rewrites React routes (now: `/`, `/b/:publicId/try`, `/demo/:template`, `/desk`, `/home`, `/login`, `/signup`) to `/app`, where Vercel serves `dist/app.html` because `cleanUrls` is on.

**Rules:** see `context/coding-rules.md` (Frontend).
- Never put patient or customer data in browser storage.
- Never call the backend by absolute URL.
- Never log personal data (ESLint blocks `console.log`).

## Vapi Web SDK bundle (old pages only)

> The React app uses `@vapi-ai/web` 2.7.1 from npm instead, behind `app/src/lib/voice.ts`, and loads it only when a call starts. This committed bundle is used only by the old static try page, which is no longer deployed and is kept only for local backend use (`localhost:8000/`) until it is removed.

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

- **Backend rewrites (ADR-0041).** `vercel.json` can't read environment variables, so between `vercel pull` and `vercel build` the workflow runs `node frontend/configure-vercel.mjs`.
  - It reads `NEXT_PUBLIC_API_URL` from the pulled `.vercel/.env.production.local` and adds rewrites of `/api/*` and `/healthz` to that backend.
  - The browser then talks to one origin, so the HttpOnly session cookie is first-party and no CORS is needed.
  - Webhooks (Vapi, Twilio) still call the backend directly. There are no Vercel functions or middleware: the rewrite only forwards.
- `NEXT_PUBLIC_API_URL` is the backend's public **https origin with no path** (e.g. `https://<backend>.onrender.com`), set in the Vercel project's **Production** environment variables.
  - Empty means no backend rewrites, so the deployed pages show the backend as unreachable.
  - The script refuses anything that isn't an https origin.
- `vercel.json` runs `node build.mjs`, which builds the app and copies the old pages. The old pages' `config.js` now always says "call `/api` on this origin", because the rewrite covers them too.
- **VERIFY on the first deploy with a backend:** Vercel's docs don't state that external rewrites pass `Set-Cookie` through, or their timeout. Check that login keeps you logged in, and how a Render cold start behaves.
- `/desk` and `/setup` (old pages) use the session cookie, which reaches the backend first-party through the `/api` rewrite (ADR-0041). Basic auth is gone (#28).

One-time setup: Vercel project with Root Directory `frontend` and no Git connection; repo secrets `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID`.
