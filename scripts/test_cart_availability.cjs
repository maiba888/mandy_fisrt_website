const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const source=fs.readFileSync(path.join(__dirname,'../src/app.js'),'utf8');
const products=[{id:'active',price:2,weight:.1,published:true},
  {id:'draft',price:3,weight:.1,published:false},
  {id:'archived',price:4,weight:.1,published:true,archived_at:1}];
const cart=['active','draft','archived','missing'].map(id=>({id,qty:2,price:9,weight:.2}));
const ctx=vm.createContext({products,cart,state:{shippingCountry:'Europe'}});
const start=source.indexOf('  function cartLines()');
const end=source.indexOf('  function shadeOptions(',start);
vm.runInContext(source.slice(start,end),ctx);
assert.deepEqual(Array.from(ctx.cartLines(),p=>p.available),[true,false,false,false]);
assert.equal(ctx.cartTotals().productTotal,4);
assert.equal(ctx.cartTotals().totalWeight,.2);
products.length=0;
assert.equal(ctx.cartTotals().productTotal,0);
assert.equal(ctx.cartTotals().shipping,0);
assert.ok(!source.includes('products = initialProducts;\n      apiOnline = false'));
console.log('PASS: stale cart entries unavailable, excluded from totals; missing catalog cannot estimate shipping');
