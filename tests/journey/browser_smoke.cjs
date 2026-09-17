/* Isolated headless Chrome UI checks. No login, payments or production API writes. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const http = require('node:http');
const {spawn} = require('node:child_process');
const root = path.resolve(__dirname, '../..');
const chromePath = process.env.CHROME_BIN || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'vd-journey-'));
const mime = {'.html':'text/html', '.js':'application/javascript', '.css':'text/css', '.json':'application/json', '.png':'image/png', '.webp':'image/webp'};
const plans = {success:true, data:[{key:'free',amount:0,days:null,monthly:1000,burst_per_sec:2},{key:'pro_monthly',amount:45000,days:30,monthly:10000,burst_per_sec:10},{key:'pro_yearly',amount:450000,days:365,monthly:10000,burst_per_sec:10}]};
const server = http.createServer((req,res) => {
    const pathname = new URL(req.url, 'http://localhost').pathname;
    const file = path.resolve(root, '.' + pathname);
    if (!file.startsWith(path.join(root,'fe') + path.sep) || !fs.existsSync(file) || !fs.statSync(file).isFile()) { res.writeHead(404); return res.end(); }
    res.setHeader('Content-Type', mime[path.extname(file)] || 'application/octet-stream'); fs.createReadStream(file).pipe(res);
});
let chrome, ws;
(async () => {
    await new Promise((resolve,reject) => { server.once('error',reject); server.listen(0, '127.0.0.1', resolve); });
    const origin = `http://127.0.0.1:${server.address().port}`;
    chrome = spawn(chromePath, ['--headless=new','--no-first-run','--no-default-browser-check',`--user-data-dir=${artifacts}/profile`,'--remote-debugging-port=0','about:blank'], {stdio:['ignore','ignore','pipe']});
    const browserWS = await new Promise((resolve,reject) => {
        let output = ''; const timer = setTimeout(() => reject(new Error('Chrome startup timed out')), 15000);
        chrome.stderr.on('data', b => { output += b; const m = output.match(/DevTools listening on (ws:\/\/[^\s]+)/); if(m){clearTimeout(timer);resolve(m[1]);} });
        chrome.on('error',reject); chrome.on('exit',code => {clearTimeout(timer);reject(new Error('Chrome exited: '+code));});
    });
    const target = await (await fetch(new URL('/json/new?about:blank', browserWS.replace('ws:','http:')), {method:'PUT'})).json();
    ws = new WebSocket(target.webSocketDebuggerUrl);
    await new Promise(r => ws.addEventListener('open',r,{once:true}));
    let serial = 0, planFailure = false, verifyFailure = false; const pending = new Map(); const errors = [];
    const send = (method,params={}) => new Promise((resolve,reject) => { const id=++serial; pending.set(id,{resolve,reject}); ws.send(JSON.stringify({id,method,params})); });
    ws.addEventListener('message', async e => {
        const msg=JSON.parse(e.data);
        if(msg.id){const p=pending.get(msg.id);pending.delete(msg.id);if(p)msg.error?p.reject(msg.error):p.resolve(msg.result);return;}
        if(msg.method==='Runtime.exceptionThrown') errors.push(msg.params.exceptionDetails.text + ': ' + (msg.params.exceptionDetails.exception?.description || ''));
        if(msg.method==='Fetch.requestPaused') {
            const {requestId,request}=msg.params;
            let response = {};
            if(request.url.endsWith('/payment/plans')) response = plans;
            else if(request.url.includes('/payment/verify-order/')) response = {activated:true};
            else if(request.url.includes('/fuel-forecast/')) response = {success:true,data:{fuel:'E5RON92',tier:'free',history:[{period:'2022-01-21',retail_price:23595},{period:'2026-08-27',retail_price:21763}],forecast:[]}};
            await send('Fetch.fulfillRequest',{requestId,responseCode:(planFailure && request.url.endsWith('/payment/plans') || verifyFailure && request.url.includes('/payment/verify-order/'))?503:200,
                responseHeaders:[{name:'Content-Type',value:'application/json'},{name:'Access-Control-Allow-Origin',value:'*'}],body:Buffer.from(JSON.stringify(response)).toString('base64')});
        }
    });
    await send('Runtime.enable'); await send('Page.enable');
    await send('Fetch.enable',{patterns:[{urlPattern:'*api/v1/*'},{urlPattern:'*google-analytics.com*'},{urlPattern:'*googletagmanager.com*'}]});
    const evaluate = async expression => {
        const r=await send('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});
        if(r.exceptionDetails)throw new Error(r.exceptionDetails.exception?.description || r.exceptionDetails.text);
        return r.result.value;
    };
    const until = async expression => { for(let n=0;n<100;n++){ if(await evaluate(expression))return;await new Promise(r=>setTimeout(r,100)); }throw new Error('Timed out: '+expression); };
    const navigate = async url => { await send('Page.navigate',{url});await until("document.readyState === 'complete'"); };
    await navigate(origin+'/fe/pages/pricing.html?id=gold&period=1y&method=api');
    await until('window.VDPricing?.ready()');
    await until("document.querySelector('#pricing-catalog a[href$=\"fuel-forecast.html\"]')?.closest('article')?.textContent.includes('2022-01-21 → 2026-08-27')");
    assert.equal(await evaluate("document.querySelectorAll('#pricing-catalog article').length"),11);
    assert.match(await evaluate("document.getElementById('paid-quota').textContent"),/10\.000/);
    assert.match(await evaluate('VDPricing.resumeHref()'),/chart\/gold\?period=1y/);
    await evaluate("switchBilling('yearly')");
    assert.match(await evaluate("document.getElementById('billing-footer-note').textContent"),/450\.000đ cho 365 ngày/);
    await evaluate("document.getElementById('checkout-overlay').style.display='flex'; coGoStep('guest'); switchBilling('monthly')");
    assert.equal(await evaluate("document.getElementById('co-guest-price-display').textContent"),'45.000₫');
    await evaluate("switchBilling('yearly')");
    assert.equal(await evaluate("document.getElementById('co-guest-price-display').textContent"),'450.000₫');
    await evaluate("_markStudentVerified(); coGoStep('confirm'); switchBilling('monthly')");
    assert.equal(await evaluate("document.getElementById('co-final-price').textContent"),'22.500');
    assert.match(await evaluate("document.getElementById('billing-footer-note').textContent"),/22\.500đ cho 30 ngày/);
    await evaluate('closeCheckout()');
    for (const width of [390,768,1366]) {
        await send('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:false});
        assert(await evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Pricing overflow at '+width);
        const screenshot=await send('Page.captureScreenshot');fs.writeFileSync(path.join(artifacts,`pricing-${width}.png`),Buffer.from(screenshot.data,'base64'));
    }
    planFailure=true;
    await navigate(origin+'/fe/pages/pricing.html');
    await until("document.getElementById('plan-status')?.textContent.includes('Chưa kiểm tra')");
    assert.equal(await evaluate("document.getElementById('btn-pro').disabled"),true);
    planFailure=false;
    await evaluate("document.querySelector('#plan-status button').click()");await until('VDPricing.ready()');
    await navigate(origin+'/fe/index.html#data/portal/chart/gold?period=1y&method=api');
    await until("document.getElementById('dataset-tools')?.hidden === false");
    assert.match(await evaluate("document.getElementById('dataset-intro').textContent"),/SJC/);
    await until("document.querySelector('#dataset-tools .journey-status').textContent.includes('bản ghi')");
    assert.match(await evaluate("document.querySelector('#dataset-tools pre').textContent"),/period=1y/);
    assert.equal(await evaluate("document.querySelector('.chart-card[data-chart-id=gold] .filter-btn.active').dataset.period"),'1y');
    for (const width of [390,768,1366]) {
        await send('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:false});
        assert(await evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Dataset overflow at '+width);
        const screenshot=await send('Page.captureScreenshot');fs.writeFileSync(path.join(artifacts,`dataset-${width}.png`),Buffer.from(screenshot.data,'base64'));
    }
    await evaluate("document.getElementById('dataset-tools').scrollIntoView({behavior:'instant'})");
    await until("document.getElementById('dataset-tools').getBoundingClientRect().top < innerHeight");
    const toolsShot=await send('Page.captureScreenshot');fs.writeFileSync(path.join(artifacts,'dataset-tools.png'),Buffer.from(toolsShot.data,'base64'));
    await evaluate("document.querySelector('.chart-card[data-chart-id=gold] [data-period=\\\"7d\\\"]').click()");
    await until("document.querySelector('#dataset-tools pre')?.textContent.includes('period=7d')");
    await evaluate("document.querySelector('#dataset-tools .journey-upgrade a').click()");
    await until("location.pathname.endsWith('pricing.html') && window.VDPricing?.ready()");
    assert.match(await evaluate('VDPricing.resumeHref()'),/period=7d/);
    await navigate(origin+'/fe/pages/pricing.html?payment=success&order=123');
    await until("document.getElementById('result-banner')?.textContent.includes('Thanh toán thành công')");
    assert.match(await evaluate("document.querySelector('#result-banner .btn-home').href"),/chart\/gold\?period=7d/);
    verifyFailure=true;
    await navigate(origin+'/fe/pages/pricing.html?payment=success&order=123');
    await until("document.getElementById('result-banner')?.textContent.includes('Chưa xác minh')");
    assert.equal(await evaluate("document.getElementById('result-banner').textContent.includes('Thanh toán thành công')"),false);
    verifyFailure=false;
    await navigate(origin+'/fe/index.html#data/portal');
    await until("document.querySelectorAll('#data-discovery [data-dataset-id]').length === 10");
    await evaluate("document.querySelector('#data-discovery [data-dataset-id=gdp]').click()");
    await until("document.querySelector('#dataset-tools .journey-status')?.textContent.includes('-Q')");
    await evaluate("updateLanguage('en')");
    await until("document.querySelector('#dataset-intro h2')?.textContent === 'GDP growth'");
    await evaluate("document.getElementById('ov-back').click()");
    assert.equal(await evaluate("document.getElementById('dataset-tools').hidden"),true);
    assert.equal(errors.length,0,errors.join('\n'));
    console.log('PASS: pricing facts, billing re-price, safe resume, API outage retry, dataset preview, three viewports.');
    console.log('Screenshots: '+artifacts);
})().catch(e=>{console.error(e);process.exitCode=1;}).finally(()=>{if(ws)ws.close();if(chrome)chrome.kill();server.close();});
