# Live-site QA audit (Playwright)

`catalyst-audit.spec.js` is a Playwright audit of the live Catalyst site
(`https://catalyst-peach-seven.vercel.app/`). It covers 18 checks: landing page,
login, signup validation, clinic demo, and more. It only reads the live site and
uses fake credentials. It does not touch the backend database.

## Run

Playwright is not a repo dependency yet. Run it from a scratch folder or install it locally:

```bash
npm i -D @playwright/test
npx playwright install chromium
npx playwright test tests/catalyst-audit.spec.js
```

## Known findings

- Test 15 (clinic demo content) fails and test 16 logs `DEMO BUTTONS: []`. See issue #66.
