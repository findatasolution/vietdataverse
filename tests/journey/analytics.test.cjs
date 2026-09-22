const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const assert = require('node:assert/strict');
const source = fs.readFileSync(path.resolve(__dirname,'../../fe/pages/site-analytics.js'),'utf8');
function load(hostname) {
    const ctx={URL,Date,location:{hostname,origin:'https://'+hostname,href:'https://'+hostname+'/pages/pricing.html?code=fixture&state=fixture&email=fixture@example.test'},
        document:{referrer:'https://accounts.google.com/path?code=fixture',createElement:()=>({}),head:{append(){}}},window:{}};
    vm.runInNewContext(source,ctx);return ctx;
}
const prod=load('vietdataverse.online');
prod.window.VDAnalytics.track('begin_checkout',{email:'fixture@example.test',token:'fixture',plan:'pro_monthly',value:45000});
const serialized=JSON.stringify(prod.window.dataLayer);
assert(!serialized.includes('fixture'));assert(!serialized.includes('?'));assert(serialized.includes('pro_monthly'));
const dev=load('localhost');dev.window.VDAnalytics.track('begin_checkout');assert.equal(dev.window.dataLayer,undefined);
const other=load('mythreel.studio');assert.equal(other.window.dataLayer,undefined);
console.log('PASS: purchase telemetry strips URL queries and contact fields, disabled off production host.');
