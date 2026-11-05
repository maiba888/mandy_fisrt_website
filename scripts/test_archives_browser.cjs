// Run only against the isolated archive fixture on localhost:4191.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');

(async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  try {
    const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
    await context.addCookies([{ name: 'fixture_admin', value: 'yes', url: 'http://127.0.0.1:4191' }]);
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto('http://127.0.0.1:4191/#admin');
    await page.locator('[data-action="admin-product-status"]').waitFor();
    await page.locator('[data-action="admin-search"]').fill('dior');
    assert.equal(await page.locator('.admin-row').count(), 1);
    await page.locator('[data-action="admin-product-status"]').selectOption('archived');
    assert.equal(await page.locator('[data-restore="archived"]').count(), 1);
    await page.locator('[data-edit="archived"]').click();
    await page.locator('[data-admin-form] input[name="name"]').fill('Dior edited archive');
    await page.locator('[data-admin-form] button[type="submit"]').click();
    await page.waitForFunction(() => document.querySelector('[data-save-feedback]')?.textContent.includes('successfully'));
    assert.equal(await page.locator('[data-restore="archived"]').count(), 1);
    const stillHidden = await page.request.get('http://127.0.0.1:4191/product/archived');
    assert.equal(stillHidden.status(), 404);
    await page.locator('[data-restore="archived"]').click();
    await page.locator('.admin-product-feedback').filter({ hasText: 'restored and published' }).waitFor();
    assert.equal(await page.locator('.admin-row').count(), 0);
    await page.locator('[data-action="admin-product-status"]').selectOption('active');
    assert.equal(await page.locator('.admin-row').count(), 2);
    const detail = await page.request.get('http://127.0.0.1:4191/product/archived');
    assert.equal(detail.status(), 200);
    await page.locator('[data-delete="archived"]').click();
    await page.locator('.admin-product-feedback').filter({ hasText: 'Product archived.' }).waitFor();
    assert.equal(await page.locator('.admin-row').count(), 1);
    await page.locator('[data-action="admin-product-status"]').selectOption('archived');
    await page.screenshot({ path: process.argv[2], fullPage: false });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.locator('[data-action="admin-product-status"]').scrollIntoViewIfNeeded();
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    assert.deepEqual(errors, []);
    console.log('PASS archive search/filter/edit/restore/archive and mobile layout.');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
