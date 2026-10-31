// Read-only production check: cart stays in an isolated browser; no order submitted.
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
(async () => {
  const [base, firstId, secondId, screenshot] = process.argv.slice(2);
  if (!base || !firstId || !secondId || !screenshot) throw new Error('Supply URL, two product IDs and screenshot path');
  const browser = await chromium.launch({channel:'msedge',headless:true});
  try {
    const page = await browser.newPage({viewport:{width:1440,height:1000}});
    const errors = [];
    page.on('pageerror', e => errors.push(e.message));
    const payload = await (await page.request.get(base+'/api/products')).json();
    const products = [firstId,secondId].map(id=>payload.products.find(p=>p.id===id));
    assert.ok(products.every(Boolean));
    for (const product of products) {
      await page.goto(base+'/product/'+encodeURIComponent(product.id));
      const add = page.locator('[data-add]');
      await add.waitFor();
      await page.locator('[data-action="qty"]').fill('5');
      await add.click();
      assert.equal(new URL(page.url()).pathname,'/product/'+encodeURIComponent(product.id));
      assert.equal(await page.locator('.tag').filter({hasText:/^SKU /}).count(),0);
    }
    await page.locator('.nav [data-view="cart"]').click();
    await page.locator('.cart-item').first().waitFor();
    assert.equal(await page.locator('.cart-item').count(),2);
    for (let i=0;i<2;i++) {
      const row = page.locator('.cart-item').nth(i);
      assert.ok((await row.innerText()).includes(products[i].name));
      assert.equal(await row.locator('input').inputValue(),'5');
      assert.ok((await row.innerText()).includes('$'+(products[i].price*5).toFixed(2)));
    }
    const stored = await page.evaluate(()=>JSON.parse(localStorage.getItem('luxe-trade-cart')));
    assert.deepEqual(stored.map(p=>p.id),[firstId,secondId]);
    await page.screenshot({path:screenshot,fullPage:true});
    await page.setViewportSize({width:390,height:844});
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    assert.deepEqual(errors,[]);
    console.log('PASS: two products stay independent at 5 PCS each, correct prices, SKU hidden, mobile cart fits; no order submitted');
  } finally { await browser.close(); }
})().catch(e=>{console.error(e);process.exitCode=1;});
