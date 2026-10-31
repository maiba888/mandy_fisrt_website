const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../src/app.js'), 'utf8');
const products = [
  {id:'RD-2', sku:'RD-2', name:'Eye patches', price:3.68, weight:.1},
  {id:'RD-2--2', sku:'RD-2', name:'Glossy lip set', price:4.2, weight:.2},
];
const cart = products.map(p => ({id:p.id, sku:p.sku, key:p.id+'__default', color:'default', qty:5}));
const context = vm.createContext({products,cart});
const start = source.indexOf('  function cartLines()');
const end = source.indexOf('  function billableShippingWeight(', start);
assert.ok(start >= 0 && end > start);
vm.runInContext(source.slice(start,end),context);
let lines = context.cartLines();
assert.equal(lines.length,2);
assert.equal(lines[0].id,'RD-2'); assert.equal(lines[1].id,'RD-2--2');
assert.equal(lines[0].price,3.68); assert.equal(lines[1].price,4.2);
assert.equal(lines[0].qty,5); assert.equal(lines[1].qty,5);
cart.push({id:'missing',sku:'RD-2',name:'Historical item',color:'01',qty:2});
assert.equal(context.cartLines()[2].id,'missing');
assert.equal(context.cartLines()[2].name,'Historical item');
assert.ok(!source.includes('name="sku"'));
assert.ok(!source.includes('SKU ${'));
console.log('PASS: duplicate SKU never substitutes product identity; SKU admin input and badges removed');
