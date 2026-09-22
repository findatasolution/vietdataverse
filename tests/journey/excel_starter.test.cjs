const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const assert = require('node:assert/strict');
const ctx={window:{},document:{addEventListener(){}}};
vm.runInNewContext(fs.readFileSync(path.resolve(__dirname,'../../fe/pages/excel-starter.js'),'utf8'),ctx);
for (const id of ['fxrate','cpi','gdp']) {
    const query=ctx.window.VDExcelStarter.queryFor(id);
    assert(query.includes('Headers = [#"X-API-Key" = ApiKey]'));
    assert(query.includes('YOUR_API_KEY'));assert(!query.includes('api_key='));
    assert(query.includes('Table.FromRecords(Complete,'));
    assert(query.includes('Record.FieldOrDefault(Response, "pages", 1) > 1'));
}
assert(ctx.window.VDExcelStarter.queryFor('fxrate').includes('page = "1", limit = "500"'));
assert(ctx.window.VDExcelStarter.queryFor('cpi').includes('view = "monthly"'));
assert.throws(()=>ctx.window.VDExcelStarter.queryFor('https://evil.test'));
console.log('PASS: allowlisted Power Query examples, header credentials and no silent pagination truncation.');
