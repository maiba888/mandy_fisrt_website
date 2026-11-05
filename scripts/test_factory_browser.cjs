// Runs on the isolated localhost factory fixture; never submits customer orders.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

(async () => {
  const output = process.argv[2];
  const files = process.argv.slice(3);
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  try {
    const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, acceptDownloads: true });
    await context.addCookies([{ name: 'fixture_admin', value: 'yes', url: 'http://127.0.0.1:4201' }]);
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto('http://127.0.0.1:4201/#admin');
    await page.locator('[data-admin-menu="factory"]').click();
    await page.locator('[data-factory-files]').setInputFiles([
      { name: 'bad-a.xlsx', mimeType: 'application/octet-stream', buffer: Buffer.from('broken') },
      { name: 'bad-b.xlsx', mimeType: 'application/octet-stream', buffer: Buffer.from('also broken') },
    ]);
    await page.locator('[data-factory-validate]').click();
    await page.locator('.factory-errors tbody tr').first().waitFor();
    assert.equal(await page.locator('.factory-errors tbody tr').count(), 2);
    assert.equal(await page.locator('[data-factory-merge]').isDisabled(), true);
    await page.screenshot({ path: path.join(output, 'validation-errors.png'), fullPage: false });
    await page.locator('[data-factory-clear]').click();
    await page.locator('[data-factory-files]').setInputFiles(files);
    await page.locator('[data-factory-validate]').click();
    await page.waitForFunction(() => document.querySelector('.factory-status')?.textContent.includes('All files passed'), null, { timeout: 120000 });
    assert.equal(await page.locator('.factory-file-list li').count(), 4);
    await page.screenshot({ path: path.join(output, 'validated-files.png'), fullPage: false });
    const download = page.waitForEvent('download');
    await page.locator('[data-factory-merge]').click();
    await (await download).saveAs(path.join(output, 'factory-order-summary.xlsx'));
    await page.locator('[data-admin-menu="catalog"]').click();
    await page.locator('[data-admin-menu="factory"]').click();
    assert.equal(await page.locator('.factory-file-list li').count(), 4);
    await page.setViewportSize({ width: 390, height: 844 });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    assert.deepEqual(errors, []);
    console.log('PASS: all-file error display, merge blocked on failure, 4-file validation/download, menu state, mobile.');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
