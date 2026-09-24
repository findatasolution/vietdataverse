const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const root = path.resolve(__dirname, '../..');
const source = fs.readFileSync(path.join(root, 'fe/excel-addin/taskpane.js'), 'utf8');
const context = {
    Office: {onReady() {}, HostType: {Excel: 'Excel'}},
    Excel: {},
    localStorage: {getItem() { return null; }, setItem() {}},
    document: {},
    console,
    fetch,
    URLSearchParams,
};
vm.createContext(context);
vm.runInContext(source, context);

assert.equal(context._excelDateSerial('2026-09-23'), 46288);
assert.equal(context._excelDateSerial('2026-09'), '2026-09');
const built = context._workbookRows({
    headers: ['date', 'value', 'period'],
    rows: [['2026-09-23', 12.5, '2026-09']],
});
assert.deepEqual(Array.from(built.dateColumns), [0]);
assert.deepEqual(Array.from(built.values[0]), [46288, 12.5, '2026-09']);
assert.match(source, /\/excel\/refresh-data\?period=/);
assert.match(source, /\/developer\/verify-key/);
assert.match(source, /'X-API-Key': _apiKey/);
assert.match(source, /table\.resize\(target\)/);
assert.match(source, /getRange\('C7'\)/);
assert.match(source, /Excel\.run/);

console.log('PASS: Excel add-in refresh converts dates and updates workbook tables.');
