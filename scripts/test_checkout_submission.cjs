const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../src/app.js'), 'utf8');
async function main() {
  let finishRefresh;
  let posts = 0;
  let windows = 0;
  const state = {shippingCountry:'Europe'};
  const ctx = vm.createContext({
    state, cart:[{id:'one',color:'01',qty:2}], renderCart() {},
    refreshProducts:() => new Promise(resolve => {finishRefresh = resolve;}),
    cartTotals:() => ({lines:[{id:'one',color:'01',qty:2,available:true}]}),
    apiFetch:async () => {posts++; return {orderNo:'test'};},
    window:{open() {windows++;}}, whatsappTarget:() => 'test',
    whatsappMessage:no => no, encodeURIComponent,
  });
  vm.runInContext(source.slice(source.indexOf('  async function createOrderAndContact('),
    source.indexOf('  function renderAdmin()', source.indexOf('  async function createOrderAndContact('))), ctx);
  const first = ctx.createOrderAndContact();
  assert.equal(state.orderSubmitting, true);
  await ctx.createOrderAndContact();
  assert.equal(posts, 0);
  finishRefresh();
  await first;
  assert.equal(posts, 1);
  assert.equal(windows, 1);
  assert.equal(state.orderSubmitting, false);
  ctx.refreshProducts = async () => {throw new Error('Catalog offline');};
  await ctx.createOrderAndContact();
  assert.equal(state.orderSubmitting, false);
  assert.equal(posts, 1);
  assert.equal(state.orderStatus, 'Catalog offline');
  console.log('PASS: pending checkout cannot submit twice; failed refresh never submits and unlocks retry');
}
main().catch(error => {console.error(error); process.exitCode = 1;});
