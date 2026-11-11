# Catalyst design system

The source of truth for how every Catalyst page looks (phase2-plan §6, ADR-0042). The tokens live in `app/src/index.css`, and the components in `app/src/components/`. Run the app locally (`npm run dev`) and open `/styleguide` to see all of them on one page; it isn't on the live site.

**Origin.** Adapted from a public analysis of Cal.com's marketing site (`VoltAgent/awesome-design-md`, `design-md/cal/DESIGN.md`): a white canvas, near-black actions, neutral greys, soft 12px cards and product UI shown directly. We keep the restraint and change the rest for our users:

- the brand is **Catalyst only**, with no Cal.com names, marks or the Cal Sans font;
- **Inter + Noto Sans Devanagari**, so Hindi reads as well as English;
- greys are darkened where the original fails AA;
- there is one warm accent, for *live* and *urgent* states only.

**Who it's for.** Clinic owners, receptionists and shop owners, often on a mid-range Android phone, in a hurry, between patients or customers. So every screen must be calm, obvious and fast. Nothing should look like a template.

---

## 1. Colour

Light theme only for Phase 2. All values are CSS variables on `:root` in `app/src/index.css`, mapped to Tailwind classes (`bg-background`, `text-muted-foreground`…).

| Token | Value | Use |
|---|---|---|
| `background` | `#ffffff` | Page canvas |
| `foreground` | `#111111` | Headings, primary text, icons |
| `body` | `#3f3f46` | Long-form body text |
| `muted` | `#f4f4f5` | Grey surface: feature cards, table header, secondary button |
| `muted-foreground` | `#5c5c66` | Hints, captions, placeholders, timestamps |
| `surface-soft` | `#fafafa` | Alternate page band |
| `card` | `#ffffff` | Cards on the canvas (with `border`) |
| `border` | `#e4e4e7` | Hairlines: card edges, dividers (decorative) |
| `input` | `#8b8b94` | Form control borders (≥ 3:1, WCAG 1.4.11) |
| `ring` | `#111111` | Keyboard focus ring |
| `primary` / `primary-foreground` | `#111111` / `#ffffff` | The one main action per screen |
| `destructive` | `#b91c1c` (soft `#fef2f2`, text `#991b1b`) | Errors, cancel/delete |
| `live` | `#c2410c` (soft `#fff7ed`, text `#9a3412`) | **Only** live and urgent states: a call in progress, an escalation, "needs a human" |
| `success` | `#047857` (soft `#ecfdf5`, text `#065f46`) | Saved, booked, confirmed |

**Rules.**
- Actions are monochrome. Primary buttons are near-black, never coloured.
- `live` is scarce. If more than one or two things on a screen are orange, none of them stand out.
- Never use colour alone to carry meaning. Pair it with a word or an icon ("Urgent", "Saved ✓").

**Contrast (WCAG 2.2 AA), checked per pair:**

| Pair | Ratio | Needs |
|---|---|---|
| foreground on background | 18.9 | 4.5 |
| body on background | 10.4 | 4.5 |
| muted-foreground on background | 6.6 | 4.5 |
| muted-foreground on muted | 6.0 | 4.5 |
| primary-foreground on primary | 18.9 | 4.5 |
| destructive on background | 6.5 | 4.5 |
| destructive text on destructive soft | 7.6 | 4.5 |
| live on background | 5.2 | 4.5 |
| live text on live soft | 6.9 | 4.5 |
| success on background | 5.5 | 4.5 |
| success text on success soft | 7.3 | 4.5 |
| input border on background | 3.4 | 3.0 (UI) |
| ring on background | 18.9 | 3.0 (UI) |

Re-run the check (`npm run check:contrast` in `app/`; CI runs it too) whenever a colour changes.

## 2. Type

- **Fonts:** `Inter Variable` for Latin, `Noto Sans Devanagari Variable` for Hindi. Both are self-hosted through Fontsource, so no Google Fonts request is made. The stack is `"Inter Variable", "Noto Sans Devanagari Variable", system-ui, sans-serif`, so mixed Hinglish lines render in the right face per script.
- **Weights:** 400 body, 500 labels and nav, 600 headings and buttons. Never 700+.
- **Scale** (Tailwind classes in brackets):

| Role | Size / line height | Notes |
|---|---|---|
| Display | 36px / 1.15 (`text-4xl`) | Landing hero only; `tracking-tight` |
| Page title | 28px / 1.2 (`text-[28px]`) | One per page; `tracking-tight` |
| Section title | 18px / 1.4 (`text-lg`) | Card and section headings |
| Body | 16px / 1.5 (`text-base`) | Default. Never smaller for anything a user must read to act |
| Small | 14px / 1.5 (`text-sm`) | Buttons, labels, table cells |
| Caption | 13px / 1.4 (`text-[13px]`) | Timestamps, helper text |

- Devanagari needs room. Keep `leading-normal` or looser on any text that may be Hindi, and never cap its height.
- Write numbers and times the Indian way: `₹1,500`, `10:30 am`, `Mon, 4 Nov`.

## 3. Space, size and shape

- **Spacing:** a 4px base, with the 8-pt rhythm in practice (`gap-2`, `gap-4`, `p-6`, `p-8`). Cards use `p-6` (24px) on mobile and `p-8` (32px) from `sm`.
- **Radius:** 8px (`rounded-md`) for buttons, inputs and tabs. 12px (`rounded-lg`) for cards. 16px (`rounded-xl`) only for one hero card. `rounded-full` for avatars and pills. Nothing larger.
- **Touch targets:** controls are 40px tall by default (`h-10`), and 44px (`size="lg"`) for the main action on mobile. Icon buttons are at least 40×40.
- **Width:** content maxes out at 1200px (`max-w-6xl`) for marketing pages and 720px (`max-w-2xl`) for forms. It must work at **360px** width with no horizontal scroll and a 16px side gutter.
- **Elevation:** almost flat. Cards use a hairline `border`, plus `shadow-xs` only when raised (a dialog, a popover). No glass, no neumorphism, no gradient blobs.

## 4. Components

All of these are in `app/src/components/` and shown on `/styleguide`.

| Component | File | Notes |
|---|---|---|
| Button | `ui/button.tsx` | Variants: `default` (primary), `secondary`, `outline`, `ghost`, `destructive`, `link`. Sizes: `sm`, `default`, `lg`, `icon`. One `default` per screen |
| Input, Textarea | `ui/input.tsx` | 40px, `input` border, `ring` focus. Errors set `aria-invalid` |
| Label | `ui/label.tsx` | Always visible above the control; never a placeholder-only label |
| Field | `field.tsx` | Label + control + hint + error, wired with `aria-describedby`. The error text comes straight from the API's `fields` (contracts.md §6) |
| Card | `ui/card.tsx` | White card with hairline border. Header, title, description, content, footer |
| Badge | `ui/badge.tsx` | Status pills: `neutral`, `live`, `success`, `destructive` |
| Toast | `ui/sonner.tsx` | Short confirmations ("Saved"). Errors that need action stay on the page, not in a toast |
| Offline banner | `offline-banner.tsx` | Shown while the browser is offline: "You're offline. Changes won't save until you're back." |
| Connection banner | `connection-banner.tsx` | Shown when an API call can't reach the backend (a network failure, or a 5xx without our JSON error body, i.e. from Vercel's rewrite or Vite's dev proxy rather than the backend; the backend's own errors such as `VOICE_NOT_CONFIGURED` don't count). Retries `/healthz` at 2, 4, 8, 15, then every 30 s, has "Retry now", and toasts "Connected again." Hidden while the offline banner shows |
| Waking-up gate | `wake-gate.tsx` | Wraps pages that need the backend. If `/healthz` doesn't answer within 1.5 s, it shows "Waking up your front desk…" (the free host sleeps; up to a minute) and keeps trying for 90 s, then "Try again". Skipped for 2 minutes after a good answer |
| Empty state | `empty-state.tsx` | Icon + one line on why it's empty + the next action |
| App header | `app-header.tsx` | Catalyst wordmark left, actions right; 64px tall, sticky, white |

**Icons:** `lucide-react` line icons, 16–20px, `stroke-width` 2, `aria-hidden` unless they are the only label. No emoji icons.

**Taking components from shadcn/ui or 21st.dev:** first replace their colours, radii and fonts with these tokens, remove anything decorative (gradients, glows, motion for its own sake), and type every prop. Show the result on `/styleguide` before using it on a page.

## 5. Writing

- Write for the reader and their moment: "Calls answered while you're with a patient", not "AI-powered omnichannel solution".
- Error messages say what happened and what to do, in one plain sentence. The backend already returns them in `detail`, so show it as-is.
- Use Hindi in Devanagari where it helps the owner ("मरीज़ों की कॉल कभी मिस नहीं"), never as decoration.
- Say "business" in the UI. `tenant` is a code word only.

## 6. Accessibility and quality checklist (every page, every PR)

- [ ] Works at 360px and at desktop width, with no horizontal scroll.
- [ ] Every control is reachable by keyboard, in order, with a visible focus ring.
- [ ] Every input has a visible label. Errors are announced (`aria-invalid` + `aria-describedby`).
- [ ] New colour pairs pass AA (run the contrast script).
- [ ] Hindi text renders in Noto Sans Devanagari and isn't clipped.
- [ ] No patient or customer data in `localStorage`, `sessionStorage` or logs.
- [ ] Loading, empty, error and offline states exist, not just the happy path.
- [ ] Respects `prefers-reduced-motion`.
