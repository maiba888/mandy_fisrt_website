// Exercise the actual storefront/admin parsing functions without booting the UI.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../src/app.js'), 'utf8');
const start = source.indexOf('  function cleanColorList(');
const end = source.indexOf('  function normalizeAssetUrl(', start);
assert.ok(start >= 0 && end > start);
const context = vm.createContext({});
vm.runInContext(source.slice(start, end), context);
const parse = (text, info = '') => Array.from(context.extractColorOptions(info, text.split('/')));
for (const count of [28, 100, 1000]) {
  const shades = Array.from({ length: count }, (_, i) => String(i + 1).padStart(3, '0'));
  assert.deepEqual(parse(shades.join('/')), shades);
  assert.deepEqual(parse('', 'Colors:' + shades.join('/') + ' Size:2*3cm'), shades);
}
const literal = ['Garnet', 'Magnetic Rose', 'Oversized', 'net weight', 'ACME', '#01', '-02-', '1 2 3', '1-2-3', '5g', 'A*B'];
assert.deepEqual(parse(literal.join('/'), 'Colors:old Size:2cm'), literal);
assert.deepEqual(parse(' 01 / / 02 /01 '), ['01', '02']);
assert.ok(!/maxlength\s*=|\.slice\(0,\s*18\)/i.test(source));
console.log('PASS: complete shade lists, literal labels, slash-only splitting and no input maxlength');
