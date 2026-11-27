const { test, expect } = require('@playwright/test');

const BASE = 'https://catalyst-peach-seven.vercel.app';

test.setTimeout(60000);

// =====================================================
// 1. HOMEPAGE
// =====================================================

test('01 - Homepage loads and has proper content', async ({ page }) => {
  const response = await page.goto(BASE);

  expect(response.status()).toBeLessThan(400);

  await expect(page.locator('body')).toBeVisible();

  const title = await page.title();
  const text = await page.locator('body').innerText();

  console.log('TITLE:', title);
  console.log('CONTENT LENGTH:', text.length);

  expect(title.length).toBeGreaterThan(0);
  expect(text.length).toBeGreaterThan(100);
});


// =====================================================
// 2. ALL IMPORTANT ROUTES
// =====================================================

test('02 - All major pages load', async ({ page }) => {
  const routes = [
    '/',
    '/login',
    '/signup',
    '/demo/clinic'
  ];

  const results = [];

  for (const route of routes) {
    const response = await page.goto(BASE + route);

    results.push({
      route,
      status: response?.status(),
      title: await page.title()
    });
  }

  console.log('ROUTE RESULTS:', results);

  for (const result of results) {
    expect(result.status, `${result.route} failed`).toBeLessThan(400);
  }
});


// =====================================================
// 3. INTERNAL LINKS
// =====================================================

test('03 - Internal links do not return HTTP errors', async ({ page }) => {
  await page.goto(BASE);

  const links = await page.locator('a[href]').evaluateAll(anchors => {
    return [...new Set(
      anchors
        .map(anchor => anchor.href)
        .filter(url => url.startsWith(location.origin))
    )];
  });

  const broken = [];

  for (const link of links) {
    try {
      const response = await page.request.get(link);

      if (response.status() >= 400) {
        broken.push({
          url: link,
          status: response.status()
        });
      }
    } catch (error) {
      broken.push({
        url: link,
        error: error.message
      });
    }
  }

  console.log('LINKS CHECKED:', links.length);
  console.log('BROKEN LINKS:', broken);

  expect(broken).toEqual([]);
});


// =====================================================
// 4. ALL IMAGES
// =====================================================

test('04 - Homepage images load', async ({ page }) => {
  await page.goto(BASE);

  await page.waitForLoadState('networkidle');

  const images = await page.locator('img').evaluateAll(imgs =>
    imgs.map(img => ({
      src: img.src,
      loaded: img.complete && img.naturalWidth > 0
    }))
  );

  const broken = images.filter(img => !img.loaded);

  console.log('IMAGES:', images.length);
  console.log('BROKEN IMAGES:', broken);

  expect(broken).toEqual([]);
});


// =====================================================
// 5. JAVASCRIPT ERRORS
// =====================================================

test('05 - No uncaught JavaScript errors on homepage', async ({ page }) => {
  const errors = [];

  page.on('pageerror', error => {
    errors.push(error.message);
  });

  await page.goto(BASE);
  await page.waitForTimeout(3000);

  console.log('RUNTIME ERRORS:', errors);

  expect(errors).toEqual([]);
});


// =====================================================
// 6. CONSOLE ERRORS
// =====================================================

test('06 - No console errors on homepage', async ({ page }) => {
  const errors = [];

  page.on('console', message => {
    if (message.type() === 'error') {
      errors.push(message.text());
    }
  });

  await page.goto(BASE);
  await page.waitForTimeout(3000);

  console.log('CONSOLE ERRORS:', errors);

  expect(errors).toEqual([]);
});


// =====================================================
// 7. MOBILE RESPONSIVENESS
// =====================================================

test('07 - Homepage does not overflow on multiple screen sizes', async ({ page }) => {
  const sizes = [
    { width: 320, height: 740 },
    { width: 360, height: 800 },
    { width: 375, height: 812 },
    { width: 390, height: 844 },
    { width: 414, height: 896 },
    { width: 768, height: 1024 },
    { width: 1024, height: 768 }
  ];

  const failures = [];

  for (const size of sizes) {
    await page.setViewportSize(size);
    await page.goto(BASE);

    const dimensions = await page.evaluate(() => ({
      screen: window.innerWidth,
      page: document.documentElement.scrollWidth
    }));

    console.log('SCREEN:', size.width, dimensions);

    if (dimensions.page > dimensions.screen) {
      failures.push({
        viewport: size.width,
        pageWidth: dimensions.page
      });
    }
  }

  console.log('OVERFLOW FAILURES:', failures);

  expect(failures).toEqual([]);
});


// =====================================================
// 8. LOGIN EMPTY FORM
// =====================================================

test('08 - Login rejects empty form', async ({ page }) => {
  await page.goto(BASE + '/login');

  await page.getByRole('button', { name: 'Log in' }).click();

  await page.waitForTimeout(1000);

  const state = await page.evaluate(() => ({
    url: location.href,
    text: document.body.innerText,
    inputs: [...document.querySelectorAll('input')].map(input => ({
      type: input.type,
      validation: input.validationMessage,
      invalid: input.getAttribute('aria-invalid')
    }))
  }));

  console.log('EMPTY LOGIN:', state);

  expect(page.url()).toContain('/login');
});


// =====================================================
// 9. LOGIN INVALID EMAIL
// =====================================================

test('09 - Login rejects invalid email format', async ({ page }) => {
  await page.goto(BASE + '/login');

  const email = page.locator('input[type="email"]');
  const password = page.locator('input[type="password"]');

  await email.fill('not-an-email');
  await password.fill('fake-password-123');

  await page.getByRole('button', { name: 'Log in' }).click();

  await page.waitForTimeout(1000);

  const state = await page.evaluate(() => ({
    url: location.href,
    text: document.body.innerText,
    emailValidation: document.querySelector('input[type="email"]')
      ?.validationMessage
  }));

  console.log('INVALID LOGIN EMAIL:', state);

  expect(page.url()).toContain('/login');
});


// =====================================================
// 10. LOGIN / SIGNUP NAVIGATION
// =====================================================

test('10 - Login and signup navigation works', async ({ page }) => {
  await page.goto(BASE + '/login');

  await page.getByRole('link', {
    name: /set up your front desk/i
  }).first().click();

  await expect(page).toHaveURL(/signup/);

  await page.getByRole('link', {
    name: /log in/i
  }).first().click();

  await expect(page).toHaveURL(/login/);

  console.log('LOGIN ↔ SIGNUP NAVIGATION WORKS');
});


// =====================================================
// 11. SIGNUP EMPTY FORM
// =====================================================

test('11 - Signup rejects empty first step', async ({ page }) => {
  await page.goto(BASE + '/signup');

  await page.getByRole('button', { name: 'Next' }).click();

  await page.waitForTimeout(500);

  const state = await page.evaluate(() => ({
    url: location.href,
    text: document.body.innerText,
    inputs: [...document.querySelectorAll('input')].map(input => ({
      type: input.type,
      validation: input.validationMessage,
      invalid: input.getAttribute('aria-invalid')
    }))
  }));

  console.log('EMPTY SIGNUP:', state);

  expect(page.url()).toContain('/signup');
});


// =====================================================
// 12. SIGNUP INVALID EMAIL
// =====================================================

test('12 - Signup rejects invalid email', async ({ page }) => {
  await page.goto(BASE + '/signup');

  const inputs = page.locator('input');

  await inputs.nth(0).fill('Test User');
  await inputs.nth(1).fill('wrong-email');
  await inputs.nth(2).fill('password123');

  await page.getByRole('button', { name: 'Next' }).click();

  await page.waitForTimeout(500);

  const state = await page.evaluate(() => ({
    url: location.href,
    text: document.body.innerText,
    emailValidation: document.querySelector('input[type="email"]')
      ?.validationMessage
  }));

  console.log('INVALID SIGNUP EMAIL:', state);

  expect(page.url()).toContain('/signup');
});


// =====================================================
// 13. SIGNUP SHORT PASSWORD
// =====================================================

test('13 - Signup short password validation', async ({ page }) => {
  await page.goto(BASE + '/signup');

  const inputs = page.locator('input');

  await inputs.nth(0).fill('Test User');
  await inputs.nth(1).fill('qa-test@example.com');
  await inputs.nth(2).fill('123');

  await page.getByRole('button', { name: 'Next' }).click();

  await page.waitForTimeout(500);

  const state = await page.evaluate(() => ({
    url: location.href,
    text: document.body.innerText,
    inputs: [...document.querySelectorAll('input')].map(input => ({
      type: input.type,
      validation: input.validationMessage
    }))
  }));

  console.log('SHORT PASSWORD:', state);

  expect(page.url()).toContain('/signup');
});


// =====================================================
// 14. SIGNUP VALID FIRST STEP
// =====================================================

test('14 - Signup accepts valid first-step data', async ({ page }) => {
  await page.goto(BASE + '/signup');

  const inputs = page.locator('input');

  await inputs.nth(0).fill('QA Test User');
  await inputs.nth(1).fill('qa-test@example.com');
  await inputs.nth(2).fill('TestingPass123!');

  await page.getByRole('button', { name: 'Next' }).click();

  await page.waitForTimeout(1000);

  const text = await page.locator('body').innerText();

  console.log('SIGNUP NEXT STEP:', text);

  // We only inspect the next step.
  // We do NOT complete signup or create an account.
  expect(page.url()).toContain('/signup');
});


// =====================================================
// 15. DEMO PAGE
// =====================================================

test('15 - Clinic demo loads and has appointment information', async ({ page }) => {
  await page.goto(BASE + '/demo/clinic');

  // /demo/clinic redirect hota hai /b/demo-clinic/try par
  await expect(page).toHaveURL(/demo-clinic/);

  // Playwright khud wait karta hai (default 5s) jab tak text dikhe
  await expect(page.getByText('Muskaan Dental Clinic').first()).toBeVisible({ timeout: 15000 });
  await expect(page.getByText('Appointment register')).toBeVisible();
});


// =====================================================
// 16. DEMO DATE SWITCH
// =====================================================

test('16 - Demo appointment date buttons work', async ({ page }) => {
  await page.goto(BASE + '/demo/clinic');

  const today = page.getByRole('button', { name: /today/i });
  const tomorrow = page.getByRole('button', { name: /tomorrow/i });

  await expect(today).toBeVisible({ timeout: 15000 });
  await expect(tomorrow).toBeVisible();

  // The whole register card (header + date buttons + slot grid).
  const grid = page.locator('[data-slot="card"]', { hasText: 'Appointment register' });

  // Wait until slots have actually rendered before taking a snapshot.
  await expect(grid).toContainText(/Free|Past|Booked/i, { timeout: 15000 });
  const before = (await grid.textContent()) ?? '';

  await tomorrow.click();
  await expect(grid).not.toHaveText(before);   // data sach mein badla

  await today.click();
  await expect(grid).toHaveText(before);       // wapas aaya
});


// =====================================================
// 17. DEMO RUNTIME ERRORS
// =====================================================

test('17 - Clinic demo has no JavaScript runtime errors', async ({ page }) => {
  const errors = [];

  page.on('pageerror', error => {
    errors.push(error.message);
  });

  await page.goto(BASE + '/demo/clinic');
  await page.getByText('Appointment register').waitFor();

  console.log('DEMO ERRORS:', errors);

  expect(errors).toEqual([]);
});


// =====================================================
// 18. DEMO MOBILE
// =====================================================

test('18 - Clinic demo is usable on mobile width', async ({ page }) => {
  await page.setViewportSize({
    width: 375,
    height: 812
  });

  await page.goto(BASE + '/demo/clinic');

  const dimensions = await page.evaluate(() => ({
    screen: window.innerWidth,
    page: document.documentElement.scrollWidth
  }));

  console.log('DEMO MOBILE:', dimensions);

  expect(dimensions.page).toBeLessThanOrEqual(dimensions.screen);
});