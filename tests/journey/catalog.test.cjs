const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '../..');
for (const prefix of ['/fe/pages/', '/pages/']) {
    const sandbox = {URL, URLSearchParams, console, location: {hostname:'example.test'},
        document: {currentScript: {src:'https://example.test'+prefix+'data-journey.js'}, documentElement:{lang:'vi'}, addEventListener(){}}, window:{}};
    vm.runInNewContext(fs.readFileSync(root+'/fe/pages/data-journey.js','utf8'),sandbox);
    const J = sandbox.window.VDJourney;
    vm.runInNewContext(fs.readFileSync(root+'/fe/app.overview.js','utf8'), sandbox);
    assert.equal(J.catalog.map(d => d.id).sort().join(','), sandbox.window.VDOverview.REGISTRY.map(d => d.id).sort().join(','));
    assert.equal(J.catalog.length,10);
    for(const d of J.catalog) {
        const rows = J.rowsOf(JSON.parse(fs.readFileSync(root+'/fe/data/'+d.file,'utf8')));
        assert(rows.length > 0,d.id+' has no preview');
        assert.match(J.coverage(rows),/→/);
        assert(new URL(J.route({id:d.id})).origin === 'https://example.test');
    }
    assert.equal(J.cleanContext({id:'https://evil.test'}),null);
    const safe=J.cleanContext({id:'gold',period:'<script>',method:'javascript:',bank:'malicious'});
    assert.equal(safe.period,'');assert.equal(safe.method,'download');assert.equal(safe.bank,'ACB');
    assert.match(J.csv([{value:-1.5,text:'=SUM(A1)'}]),/"-1.5","'=SUM\(A1\)"/);
    assert.match(J.selectedDataset({id:'termdepo',bank:'CTG'}).endpoint,/bank=CTG/);
}
console.log('PASS: 10 snapshots, both page aliases, bounded context and CSV escaping.');
