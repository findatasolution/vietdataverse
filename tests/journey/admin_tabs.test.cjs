/* Admin report tabs render, lazily, with no console errors.
 *
 * Everything is stubbed — auth.js, the Auth0 SDK and every /api/v1/admin/*
 * response — so this touches no production data and needs no admin account.
 * What it proves is the wiring the server-side tests cannot: that each tab's
 * panel exists, that opening it fetches exactly once, that a period change
 * refetches only the visible tab, and that the numbers land in the DOM.
 *
 * Run: node tests/journey/admin_tabs.test.cjs
 */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const http = require('node:http');
const {spawn} = require('node:child_process');

const root = path.resolve(__dirname, '../..');
const chromePath = process.env.CHROME_BIN || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const artifacts = fs.mkdtempSync(path.join(os.tmpdir(), 'vd-admin-'));
const mime = {'.html': 'text/html', '.js': 'application/javascript', '.css': 'text/css', '.json': 'application/json'};

// Stub for /fe/auth.js: admin.html calls these four before touching the API.
const authStub = `
window.isAuthenticated = async () => true;
window.getToken = async () => 'test-token';
window.getUser = async () => ({email: 'admin@test.local'});
window.login = async () => {};
`;

const fixtures = {
    'payment/status': {user_level: 'admin'},
    // Shape copied from the real /admin/dashboard response, not invented — a
    // fixture that does not match the server teaches the test nothing.
    'admin/dashboard': {
        period: {label: '24 giờ qua'},
        revenue: {period_total: 99000, this_month: 0, last_month: 0, ytd: 99000},
        subscribers: {new_in_period: 5, total_users: 5, active_by_tier: {}},
        logins: {unique_in_period: 3},
        users: {total: 5, new_today: 0, new_week: 0, new_month: 0, ever_logged_in: 3,
                dau: 1, wau: 2, mau: 3},
        api: {total: 68, successful: 65, rejected: 3, recognized: 65, public_anonymous: 1,
              anonymous_or_invalid: 2, api_key_calls: 20, bearer_calls: 45, unique_users: 4},
        top_endpoints: [], top_api_keys: [],
        feedback: {total: 4, avg_rating: 4.2, with_text: 2, ratings: [], groups: [], recent: []},
        website_traffic: {active_users: 10, pageviews: 30, sessions: 12, new_users: 8},
    },
    'admin/signup-trend': {granularity: 'day', data: [{bucket: '2026-09-22', count: 1}]},
    // Both list endpoints answer {data: [...], total: n} — checked against the
    // page's own reader, not guessed.
    'admin/users': {data: [], total: 0},
    'admin/payment-orders': {data: [], total: 0},
    'admin/report/funnel': {
        success: true, period: '7d',
        steps: [
            {key: 'signup', label: 'Đã đăng ký', value: 5, from_prev_pct: null, note: '5 tài khoản mới trong kỳ'},
            {key: 'logged_in', label: 'Đã đăng nhập ít nhất 1 lần', value: 3, from_prev_pct: 60},
            {key: 'has_key', label: 'Đã tạo API key', value: 1, from_prev_pct: 33.3},
            {key: 'called', label: 'Đã gọi API bằng key', value: 2, from_prev_pct: null,
             warning: 'Bậc này không phải tập con của bậc trước — tỉ lệ không có nghĩa'},
            {key: 'paid', label: 'Đã thanh toán', value: 1, from_prev_pct: 50},
        ],
        orders: {period: {created: 12, paid: 1}, all_time: {created: 12, paid: 1, paid_pct: 8.3}},
    },
    'admin/report/api': {
        success: true, period: '7d',
        by_day: [{day: '2026-09-23', total: 3, ok: 1, rejected: 2, anonymous: 3}],
        by_endpoint: [{endpoint: '/api/v1/gold', calls: 29, ok: 28, rejected: 1, users: 3}],
        by_status: [{status_code: 200, calls: 65}, {status_code: 401, calls: 2}],
        callers: [{user_id: 1, email: 'admin@test.local', user_level: 'admin', current_plan: null,
                   calls: 45, rejected: 0, via_key: 20, last_call: '2026-09-23 07:17:30',
                   quota_limit: null, quota_used: 45, quota_pct: null}],
        anonymous: {rows: [{endpoint: '/api/v1/gold', status_code: 401, calls: 2}],
                    recording_since: '2026-09-23 07:56:51',
                    note: 'Lượt gọi ẩn danh chỉ được ghi từ 2026-09-23 (migration 019).'},
        quota_reference: {free: {monthly: 2}}, log_rows_total: 68,
    },
    'admin/report/money': {
        success: true, period: 'ytd',
        orders: {by_status: [{status: 'pending', orders: 11, amount: 5644000}],
                 by_plan: [{plan: 'pro_monthly', status: 'pending', orders: 3, amount: 447000}],
                 recent: []},
        revenue_by_month: [{month: '2026-05', orders: 1, amount: 99000}],
        marketplace: {available: true, products: 26, sellers: 2,
                      purchases: [{purchases: 6, credits: 120}],
                      credit_ledger: [{kind: 'topup', entries: 6, credits: 400}],
                      seller_earnings: 108,
                      subscriptions: [{product_code: 'fuel-forecast-advanced', status: 'active', subs: 1}],
                      subscription_events: [], note: 'Bảng trùng tên trong USER_DB rỗng.'},
    },
    'admin/report/data-health': {
        success: true,
        summary: {total: 17, ok: 15, late: 1, stale: 1, error: 0, empty: 0},
        groups: {
            'Hàng ngày': [{table: 'vn_macro_gold_daily', label: 'Vàng SJC', db: 'crawl',
                           cadence: 'Hàng ngày', max_age_days: 3, rows: 906,
                           latest: '2026-09-23', age_days: 0, status: 'ok'},
                          {table: 'vn_macro_sbv_rate_daily', label: 'Tỷ giá & lãi suất SBV', db: 'crawl',
                           cadence: 'Hàng ngày', max_age_days: 5, rows: 203,
                           latest: '2026-08-01', age_days: 53, status: 'stale'}],
        },
    },
};

function fixtureFor(url) {
    for (const key of Object.keys(fixtures)) if (url.includes('/api/v1/' + key)) return fixtures[key];
    return {success: true};
}

const server = http.createServer((req, res) => {
    const pathname = new URL(req.url, 'http://l').pathname;
    if (pathname === '/fe/auth.js') {
        res.setHeader('Content-Type', 'application/javascript');
        return res.end(authStub);
    }
    const file = path.resolve(root, '.' + pathname);
    if (!file.startsWith(path.join(root, 'fe') + path.sep) || !fs.existsSync(file) || !fs.statSync(file).isFile()) {
        res.writeHead(404); return res.end();
    }
    res.setHeader('Content-Type', mime[path.extname(file)] || 'application/octet-stream');
    fs.createReadStream(file).pipe(res);
});

let chrome, ws;
(async () => {
    await new Promise((resolve, reject) => { server.once('error', reject); server.listen(0, '127.0.0.1', resolve); });
    const origin = `http://127.0.0.1:${server.address().port}`;
    chrome = spawn(chromePath, ['--headless=new', '--no-first-run', '--disable-gpu',
        `--user-data-dir=${artifacts}/profile`, '--remote-debugging-port=0', 'about:blank'],
        {stdio: ['ignore', 'ignore', 'pipe']});
    const browserWS = await new Promise((resolve, reject) => {
        let out = ''; const timer = setTimeout(() => reject(new Error('Chrome startup timed out')), 20000);
        chrome.stderr.on('data', b => {
            out += b; const m = out.match(/DevTools listening on (ws:\/\/\S+)/);
            if (m) { clearTimeout(timer); resolve(m[1]); }
        });
        chrome.on('exit', code => { clearTimeout(timer); reject(new Error('Chrome exited: ' + code)); });
    });
    const target = await (await fetch(new URL('/json/new?about:blank', browserWS.replace('ws:', 'http:')), {method: 'PUT'})).json();
    ws = new WebSocket(target.webSocketDebuggerUrl);
    await new Promise(r => ws.addEventListener('open', r, {once: true}));

    let serial = 0; const pending = new Map(); const errors = []; const apiHits = [];
    const send = (method, params = {}) => new Promise((resolve, reject) => {
        const id = ++serial; pending.set(id, {resolve, reject}); ws.send(JSON.stringify({id, method, params}));
    });
    ws.addEventListener('message', async e => {
        const msg = JSON.parse(e.data);
        if (msg.id) { const p = pending.get(msg.id); pending.delete(msg.id); if (p) msg.error ? p.reject(msg.error) : p.resolve(msg.result); return; }
        if (msg.method === 'Runtime.exceptionThrown') {
            errors.push(msg.params.exceptionDetails.text + ': ' + (msg.params.exceptionDetails.exception?.description || ''));
        }
        if (msg.method === 'Fetch.requestPaused') {
            const {requestId, request} = msg.params;
            // Every cross-origin call raises TWO Fetch events — the CORS
            // preflight (OPTIONS) and the real GET. Counting both made each
            // endpoint look fetched twice and turned the lazy-loading
            // assertion into a false failure.
            if (request.method !== 'OPTIONS') apiHits.push(request.url.replace(origin, ''));
            await send('Fetch.fulfillRequest', {
                requestId, responseCode: 200,
                // The page targets http://127.0.0.1:8000 when served from a
                // 127.0.0.1 host, so every call is cross-origin and the
                // Authorization header forces a preflight. Without
                // Allow-Headers the preflight fails, fetch rejects, and the
                // page shows "Admin only" — which looks like an auth bug.
                responseHeaders: [{name: 'Content-Type', value: 'application/json'},
                                  {name: 'Access-Control-Allow-Origin', value: '*'},
                                  {name: 'Access-Control-Allow-Headers', value: '*'},
                                  {name: 'Access-Control-Allow-Methods', value: '*'}],
                body: Buffer.from(JSON.stringify(fixtureFor(request.url))).toString('base64'),
            });
        }
    });
    await send('Runtime.enable'); await send('Page.enable');
    await send('Fetch.enable', {patterns: [{urlPattern: '*api/v1/*'}]});

    const evaluate = async expression => {
        const r = await send('Runtime.evaluate', {expression, awaitPromise: true, returnByValue: true});
        if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description || r.exceptionDetails.text);
        return r.result.value;
    };
    const until = async expr => {
        for (let n = 0; n < 120; n++) { if (await evaluate(expr)) return; await new Promise(r => setTimeout(r, 100)); }
        // A bare timeout says nothing about why. Dump what the page actually
        // has — this is the difference between "the test is flaky" and "the
        // module never loaded".
        console.error('--- timeout context ---');
        console.error('VDAdminReport:', await evaluate("typeof window.VDAdminReport"));
        console.error('activeTab:', await evaluate("typeof _activeTab !== 'undefined' ? _activeTab : '(undef)'"));
        console.error('funnel html:', (await evaluate("document.getElementById('report-funnel')?.textContent") || '').slice(0, 200));
        console.error('api hits:', JSON.stringify(apiHits));
        console.error('page errors:', JSON.stringify(errors));
        throw new Error('Timed out waiting for: ' + expr);
    };

    await send('Page.navigate', {url: origin + '/fe/pages/admin.html'});
    await until("document.getElementById('admin-app')?.style.display === 'block'");

    // Tổng quan is the landing tab and must be populated without a click.
    await until("document.querySelectorAll('#report-funnel .kpi-card').length >= 5");
    assert.match(await evaluate("document.getElementById('report-funnel').textContent"), /Đã thanh toán/);
    assert.match(await evaluate("document.getElementById('report-funnel').textContent"),
        /tỉ lệ không có nghĩa/, 'a non-nested funnel step must show the warning, not a percentage');

    // Each tab loads on first open.
    await evaluate("switchTab('api')");
    await until("document.getElementById('report-api').textContent.includes('Theo endpoint')");
    assert.match(await evaluate("document.getElementById('report-api').textContent"),
        /migration 019/, 'the API tab must surface why an anonymous zero may mean "not measured"');
    assert.match(await evaluate("document.getElementById('report-api').textContent"),
        /Chưa đăng nhập \/ key sai/, 'status codes are explained, not left as bare numbers');

    await evaluate("switchTab('money')");
    await until("document.getElementById('report-money').textContent.includes('Doanh thu theo tháng')");
    assert.match(await evaluate("document.getElementById('report-money').textContent"), /fuel-forecast-advanced/);

    await evaluate("switchTab('data')");
    await until("document.getElementById('report-data').textContent.includes('Hàng ngày')");
    assert.match(await evaluate("document.getElementById('report-data').textContent"), /Đứng im/,
        'a stale table must be named as stale');

    await evaluate("switchTab('feedback')");
    assert.equal(await evaluate("document.getElementById('tab-feedback').classList.contains('active')"), true);
    await evaluate("switchTab('users')");
    assert.equal(await evaluate("document.getElementById('tab-users').classList.contains('active')"), true);

    // Lazy: each report endpoint fetched exactly once across all that switching.
    for (const ep of ['funnel', 'api', 'money', 'data-health']) {
        const hits = apiHits.filter(u => u.includes('/report/' + ep)).length;
        assert.equal(hits, 1, `${ep} should be fetched once, was ${hits}`);
    }

    // A period change refetches the visible tab only.
    await evaluate("switchTab('data')");
    const before = apiHits.filter(u => u.includes('/report/')).length;
    await evaluate("setReportPeriod('7d', document.querySelector('.report-period-btn[data-period=\"7d\"]'))");
    await new Promise(r => setTimeout(r, 1200));
    const added = apiHits.filter(u => u.includes('/report/')).length - before;
    assert.equal(added, 1, `a period change should refetch only the open tab, refetched ${added}`);

    assert.deepEqual(errors, [], 'console errors: ' + errors.join(' | '));
    console.log('PASS: 6 tabs render, lazy-load once each, period change refetches only the open tab, no console errors.');
    ws.close(); chrome.kill(); server.close(); process.exit(0);
})().catch(err => {
    console.error('FAIL:', err.message);
    try { ws && ws.close(); } catch {}
    try { chrome && chrome.kill(); } catch {}
    server.close(); process.exit(1);
});
