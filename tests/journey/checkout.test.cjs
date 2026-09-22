/* Exercise payment confirmation UI and telemetry without a browser or secrets. */
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '../..');
class Element {
    constructor(tag) { this.tag = tag; this.children = []; this.textContent = ''; }
    append(...nodes) { this.children.push(...nodes); }
    replaceChildren(...nodes) { this.children = nodes; }
    get text() { return this.textContent + this.children.map(n => n.text).join(' '); }
}
function setup(search, responses) {
    const banner = new Element('div'), events = [], storage = new Map(); let calls = 0;
    const context = {URLSearchParams, console, sessionStorage: {getItem:k=>storage.get(k),setItem:(k,v)=>storage.set(k,v)},
        location:{search}, document:{getElementById:()=>banner,createElement:tag=>new Element(tag)},
        window:{VDPricing:{resumeHref:()=>'/fe/index.html#data/portal/chart/fxrate'}, VDAnalytics:{track:(...event)=>events.push(event)}},
        setTimeout:fn=>fn(), fetch: async()=> { calls++; const r = responses.shift() || {success:true,status:'PENDING'}; if(r instanceof Error)throw r;return {ok:true,json:async()=>r}; }};
    vm.runInNewContext(fs.readFileSync(root+'/fe/pages/checkout-feedback.js','utf8'),context);
    return {context,banner,events,calls:()=>calls,run:()=>context.window.VDCheckout.confirmReturn('https://example.test')};
}
const paid = {success:true,status:'paid',activated:true,order_type:'subscription',plan:'pro_monthly',amount:45000};
(async()=>{
    const valid = setup('?payment=success&order=123',[paid]);await valid.run();
    assert.match(valid.banner.text,/Thanh toán thành công/);
    assert.equal(valid.events[0][0],'purchase');assert.equal(valid.events[0][1].value,45000);
    valid.context.window.VDCheckout.reportPurchase('123',paid);assert.equal(valid.events.length,1);
    const spoof = setup('?payment=success&order=123',[{activated:true}]);await spoof.run();
    assert.equal(spoof.events.length,0);assert.doesNotMatch(spoof.banner.text,/Thanh toán thành công/);assert.equal(spoof.calls(),4);
    const delayed = setup('?payment=success&order=123',[{status:'PENDING'},paid]);await delayed.run();assert.equal(delayed.calls(),2);assert.equal(delayed.events.length,1);
    const failed = setup('?payment=success&order=123',[new Error('offline')]);await failed.run();assert.match(failed.banner.text,/Chưa xác minh/);assert.equal(failed.events.length,0);
    const retry = failed.banner.children.at(-1).children.find(n=>n.tag==='button');assert(retry && retry.onclick);
    const injection = setup('?payment=success&order=%3Cscript%3E',[]);await injection.run();assert.equal(injection.calls(),0);
    const topup = setup('?payment=success&order=123',[{...paid,order_type:'credit_topup',activated:false}]);await topup.run();assert.equal(topup.events.length,0);assert.match(topup.banner.text,/nạp credits/);
    // Main pricing inline code must still parse after extracting the return handler.
    const html = fs.readFileSync(root+'/fe/pages/pricing.html','utf8');
    for (const match of html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g)) if(match[1].trim())new vm.Script(match[1]);
    console.log('PASS: verified payment, spoofed URL, pending polling, retry, duplicate purchase and topup separation.');
})().catch(e=>{console.error(e);process.exitCode=1;});
