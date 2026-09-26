/* Shared dataset discovery, preview and purchase context. No credentials stored. */
(function () {
    'use strict';
    const scriptURL = new URL(document.currentScript.src);
    const appURL = new URL('../index.html', scriptURL);
    // Standalone pages also have /pages aliases; static snapshots live at /fe/data.
    const dataURL = new URL('/fe/data/', scriptURL);
    const api = location.hostname === 'localhost' || location.hostname === '127.0.0.1'
        ? 'http://127.0.0.1:8000/api/v1' : 'https://api.vietdataverse.online/api/v1';
    const vi = () => document.documentElement.lang !== 'en';
    const t = (a, b) => vi() ? a : b;
    const catalog = [
        ['gold', 'Giá vàng SJC', 'SJC gold', 'gold_SJC_1y.json', 'gold?type=SJC&period=all', 'VND/lượng', '24h.com.vn / giavang.org', 'daily', 'report'],
        ['silver', 'Giá bạc Phú Quý', 'Phu Quy silver', 'silver_1y.json', 'silver?period=all', 'VND/lượng', 'Phú Quý', 'daily', 'report'],
        ['termdepo', 'Lãi suất tiền gửi ACB', 'ACB deposit rates', 'termdepo_ACB_1y.json', 'termdepo?bank=ACB&period=all', '%/năm', 'ACB', 'monthly', 'report'],
        ['interbank', 'Lãi suất liên ngân hàng', 'Interbank rates', 'sbv_1y.json', 'sbv-interbank?period=all', '%/năm', 'NHNN', 'daily', 'model'],
        ['policy', 'Lãi suất điều hành', 'Policy rates', 'sbv_policy_all.json', null, '%/năm', 'NHNN', 'event', 'model'],
        ['fxrate', 'Tỷ giá trung tâm USD/VND', 'USD/VND central rate', 'fxrate_SBV_USD_1y.json', 'sbv-rate?bank=SBV&currency=USD&period=all', 'VND/USD', 'NHNN', 'daily', 'report'],
        ['global', 'Thị trường quốc tế', 'Global markets', 'global_1y.json', 'global-macro?period=all', 'USD / index', 'Yahoo Finance', 'daily', 'model'],
        ['cpi', 'CPI Việt Nam', 'Vietnam CPI', 'cpi_monthly.json', 'macro/cpi?view=monthly&years=20', '%', 'GSO / NSO', 'monthly', 'model'],
        ['gdp', 'Tăng trưởng GDP', 'GDP growth', 'gdp_quarterly.json', 'macro/gdp?years=20', '%', 'GSO / NSO', 'quarterly', 'model'],
        ['trade', 'Xuất nhập khẩu', 'Foreign trade', 'trade_monthly.json', 'macro/trade?years=20', 'tỷ USD', 'GSO / NSO', 'monthly', 'model']
    ].map(([id, name, en, file, endpoint, unit, source, cadence, job]) => ({id, name, en, file, endpoint, unit, source, cadence, job}));
    const byId = id => catalog.find(d => d.id === id);
    const name = d => t(d.name, d.en);
    function selectedDataset(ctx) {
        const d = {...byId(ctx.id)};
        if (ctx.id === 'termdepo' && ctx.bank && ctx.bank !== 'ACB') {
            d.name = d.name.replace('ACB', ctx.bank); d.en = d.en.replace('ACB', ctx.bank);
            d.file = d.file.replace('ACB', ctx.bank); d.source = ctx.bank;
            d.endpoint = d.endpoint.replace('ACB', ctx.bank);
        }
        return d;
    }
    const cache = new Map();
    const contextKey = 'vd.dataset.intent.v1';
    let active = null;
    let revision = 0;
    const el = (tag, text, cls) => {
        const n = document.createElement(tag);
        if (text != null) n.textContent = text;
        if (cls) n.className = cls;
        return n;
    };
    const link = (label, href, cls = 'btn-data-secondary') => {
        const a = el('a', label, cls); a.href = href; return a;
    };
    function rowsOf(json) {
        const data = json.data || json;
        if (Array.isArray(data)) return data;
        if (!Array.isArray(data.dates)) return [];
        const fields = Object.keys(data).filter(k => k !== 'dates' && Array.isArray(data[k]) && data[k].length === data.dates.length);
        return data.dates.map((date, i) => Object.fromEntries([['date', date], ...fields.map(k => [k, data[k][i]])]));
    }
    function snapshot(d) {
        if (!cache.has(d.file)) cache.set(d.file, fetch(new URL(d.file, dataURL)).then(r => {
            if (!r.ok) throw new Error('Snapshot unavailable');
            return r.json();
        }).then(json => ({rows: rowsOf(json), generated: json.generated_at || null})).catch(e => { cache.delete(d.file); throw e; }));
        return cache.get(d.file);
    }
    function cleanContext(raw) {
        if (!raw || !byId(raw.id)) return null;
        return {id: raw.id, period: /^(7d|1m|1y|5y|10y|all|0|1|3|5|10|20)$/.test(raw.period) ? raw.period : '',
            method: ['download', 'excel', 'api'].includes(raw.method) ? raw.method : 'download',
            bank: ['ACB', 'CTG', 'SHB'].includes(raw.bank) ? raw.bank : 'ACB'};
    }
    function remember(ctx) { try { sessionStorage.setItem(contextKey, JSON.stringify({...ctx, saved: Date.now()})); } catch (_) {} }
    function recalled() {
        try { const raw = JSON.parse(sessionStorage.getItem(contextKey)); return raw && Date.now() - raw.saved < 86400000 ? cleanContext(raw) : null; } catch (_) { return null; }
    }
    function route(ctx) {
        const url = new URL(appURL);
        url.hash = 'data/portal/chart/' + ctx.id + '?' + new URLSearchParams({period: ctx.period || '', bank: ctx.bank || 'ACB', method: ctx.method || 'download'});
        return url.href;
    }
    function pricingLink(ctx) {
        remember(ctx);
        const url = new URL('pricing.html', scriptURL);
        url.search = new URLSearchParams(ctx).toString();
        return url.href;
    }
    function track(event, ctx) {
        if (typeof window.gtag === 'function') window.gtag('event', event, {dataset: ctx.id, method: ctx.method});
    }
    function coverage(rows) {
        const dates = rows.map(r => String(r.date || r.period || (r.year ? `${r.year}${r.quarter ? '-Q' + r.quarter : ''}` : ''))).filter(Boolean).sort();
        return dates.length ? `${dates[0]} → ${dates[dates.length - 1]} · ${rows.length.toLocaleString('vi-VN')} ${t('bản ghi', 'records')}` : t('Chưa có dữ liệu', 'No data available');
    }
    function csv(rows) {
        const keys = [...new Set(rows.flatMap(r => Object.keys(r)))];
        const cell = value => '"' + (typeof value === 'number' ? String(value) : String(value == null ? '' : value).replace(/^[=+@\-\t\r]/, "'$&")).replace(/"/g, '""') + '"';
        return '\uFEFF' + [keys.map(cell).join(','), ...rows.map(r => keys.map(k => cell(r[k])).join(','))].join('\r\n');
    }
    function download(rows, id) {
        const url = URL.createObjectURL(new Blob([csv(rows)], {type: 'text/csv;charset=utf-8'}));
        const a = link('', url); a.download = 'vietdataverse_' + id + '_preview.csv';
        document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    }
    function table(rows) {
        const wrap = el('div', null, 'journey-table');
        const grid = el('table'); const head = el('tr');
        const keys = [...new Set(rows.flatMap(r => Object.keys(r)))].filter(k => !['crawl_time', 'id'].includes(k));
        keys.forEach(k => head.append(el('th', k))); const thead = el('thead'); thead.append(head); grid.append(thead);
        const body = el('tbody');
        rows.slice(-8).reverse().forEach(r => {
            const tr = el('tr'); keys.forEach(k => tr.append(el('td', r[k] == null ? '—' : typeof r[k] === 'number' ? r[k].toLocaleString('vi-VN') : String(r[k])))); body.append(tr);
        });
        grid.append(body); wrap.append(grid); return wrap;
    }
    function buildDiscovery() {
        const root = document.getElementById('data-discovery'); if (!root) return;
        root.replaceChildren(el('h2', t('Bạn cần dữ liệu cho việc gì?', 'What do you need data for?')));
        const filters = el('div', null, 'journey-actions'); const grid = el('div', null, 'journey-catalog');
        const render = job => {
            grid.replaceChildren();
            catalog.filter(d => job === 'all' || job === 'api' && d.endpoint || d.job === job).forEach(d => {
                const a = link(name(d), route({id: d.id}), 'journey-dataset');
                a.dataset.datasetId = d.id;
                a.append(el('small', d.source + ' · ' + d.unit)); grid.append(a);
            });
        };
        [['all', 'Tất cả dữ liệu', 'All datasets'], ['report', 'Cập nhật báo cáo', 'Update a report'], ['model', 'Lập mô hình lịch sử', 'Historical analysis'], ['api', 'Kết nối dashboard / API', 'Dashboard / API']].forEach(([key, a, b]) => {
            const btn = el('button', t(a, b), 'btn-data-secondary'); btn.type = 'button'; btn.setAttribute('aria-pressed', String(key === 'all'));
            btn.onclick = () => { filters.querySelectorAll('button').forEach(n => n.setAttribute('aria-pressed', String(n === btn))); render(key); };
            filters.append(btn);
        });
        root.append(filters, grid); render('all');
    }
    async function show(chart, context = {}) {
        if (!byId(chart.id)) return;
        const version = ++revision;
        active = cleanContext({id: chart.id, period: context.period || chart.detailPeriod, method: context.method, bank: context.bank});
        const d = selectedDataset(active);
        const intro = document.getElementById('dataset-intro');
        const panel = document.getElementById('dataset-tools');
        if (!intro || !panel) return;
        document.querySelector(`[data-lazy-section="${chart.section}"]`).append(panel);
        intro.hidden = panel.hidden = false;
        intro.replaceChildren(el('h2', name(d)), el('p', `${t('Nguồn', 'Source')}: ${d.source} · ${t('Đơn vị', 'Unit')}: ${d.unit}`));
        const cadence = {daily: t('Theo ngày quan sát', 'Daily observations'), monthly: t('Theo tháng', 'Monthly'), quarterly: t('Theo quý', 'Quarterly'), event: t('Theo quyết định điều hành', 'Policy decisions')};
        intro.append(el('p', cadence[d.cadence] + ' · ' + t('Không phải dữ liệu giao dịch realtime.', 'Not a real-time trading feed.')));
        const introCoverage = el('small', t('Đang kiểm tra phạm vi bản xem trước…', 'Checking preview coverage…'), 'journey-status');
        intro.append(introCoverage);
        if (d.id === 'fxrate') intro.append(el('p', t('Tỷ giá trung tâm không phải tỷ giá mua/bán tại ngân hàng.', 'The central rate is not a bank transaction rate.')));
        panel.replaceChildren(el('h3', t('Đưa dữ liệu vào công việc', 'Use this dataset')));
        const methods = el('div', null, 'journey-actions');
        const content = el('div'); const status = el('p', t('Đang kiểm tra phạm vi bản xem trước…', 'Checking preview coverage…'), 'journey-status'); status.setAttribute('role', 'status');
        panel.append(status, methods, content);
        let sample = null;
        function select(method) {
            active.method = method; remember(active);
            methods.querySelectorAll('button').forEach(n => n.setAttribute('aria-pressed', String(n.dataset.method === method)));
            content.replaceChildren();
            if (method === 'download') {
                content.append(el('p', t('CSV bản xem trước: miễn phí, không cần đăng nhập. Phạm vi dưới đây là dữ liệu trong snapshot, không phải toàn bộ lịch sử của API.', 'Preview CSV: free, no login. The range below describes the snapshot, not the full API history.')));
                const btn = el('button', t('Tải CSV bản xem trước', 'Download preview CSV'), 'btn-data-primary'); btn.type = 'button'; btn.disabled = !sample || !sample.rows.length;
                btn.onclick = () => { download(sample.rows, d.id); track('dataset_download_success', active); };
                content.append(btn);
                const downloadId = {gold: 'gold-SJC', silver: 'silver', termdepo: 'termdepo-' + active.bank, interbank: 'sbv-interbank', fxrate: 'fxrate-SBV-USD', global: 'global-macro'}[d.id];
                if (downloadId) {
                    const full = el('button', t('Tải lịch sử API (tài khoản miễn phí)', 'Download API history (free account)'), 'btn-data-secondary'); full.type = 'button';
                    full.onclick = async () => {
                        remember(active);
                        try {
                            if (typeof window.isAuthenticated !== 'function' || !await window.isAuthenticated()) {
                                if (typeof window.login === 'function') { const back = new URL(route(active)); await window.login(back.pathname + back.hash); }
                                else status.textContent = t('Đăng nhập chưa sẵn sàng. Vui lòng tải lại trang.', 'Login unavailable. Please reload.');
                                return;
                            }
                            await window.downloadDataset(downloadId, full);
                        } catch (_) { status.textContent = t('Chưa tải được dữ liệu. Vui lòng thử lại.', 'Download unavailable. Please retry.'); }
                    };
                    content.append(document.createTextNode(' '), full);
                }
                if (sample && sample.rows.length) { const details = el('details'); details.append(el('summary', t('Xem các bản ghi gần nhất', 'Inspect recent records')), table(sample.rows)); content.append(details); }
            } else {
                content.append(el('p', method === 'excel'
                    ? t('Copy file Google Sheets mẫu rồi dán API key vào một ô; dùng key miễn phí để thử trước.', 'Copy the Google Sheets template and paste your API key into one cell; try it with your free key first.')
                    : t('API có quota theo tháng. Dùng key hiện có; không cần tạo lại sau khi nâng cấp.', 'API usage is metered monthly. Keep your existing key after upgrading.')));
                if (d.endpoint) {
                    const requestURL = new URL(`${api}/${d.endpoint}`);
                    if (requestURL.searchParams.has('period') && ['7d', '1m', '1y', 'all'].includes(active.period)) requestURL.searchParams.set('period', active.period);
                    const pre = el('pre', `GET ${requestURL}\nX-API-Key: YOUR_API_KEY`, 'journey-code'); content.append(pre);
                    const developer = link(t('Lấy / quản lý API key', 'Get / manage API key'), new URL('developer.html', scriptURL));
                    developer.onclick = async e => {
                        if (typeof window.isAuthenticated !== 'function' || typeof window.login !== 'function') return;
                        e.preventDefault(); remember(active);
                        try {
                            if (await window.isAuthenticated()) location.href = developer.href;
                            else await window.login(new URL(developer.href).pathname);
                        } catch (_) { status.textContent = t('Chưa thể mở trang API key. Vui lòng thử lại.', 'Unable to open API keys. Please retry.'); }
                    };
                    content.append(link(t('Hướng dẫn Google Sheets', 'Google Sheets guide'), new URL('google-sheets.html', scriptURL)), document.createTextNode(' '), developer);
                } else content.append(el('p', t('Bộ này hiện cung cấp snapshot công khai, chưa có endpoint API riêng.', 'This dataset currently has a public snapshot, not a dedicated API endpoint.')));
            }
            const note = el('aside', null, 'journey-upgrade');
            note.append(el('strong', t('Cần cập nhật dữ liệu thường xuyên hơn?', 'Need more frequent data refreshes?')),
                el('p', t('Nâng cấp hạn mức API cho bảng tính và dashboard của bạn. Nguồn và phạm vi dữ liệu không đổi; tiếp tục dùng miễn phí nếu hạn mức hiện tại đã đủ.', 'Get more API capacity for your spreadsheets and dashboards. Data sources and coverage stay the same; stay free if the current quota meets your needs.')));
            const upgrade = link(t('Xem quyền lợi và giá', 'Compare access and pricing'), pricingLink(active));
            upgrade.addEventListener('click', () => { upgrade.href = pricingLink(active); track('dataset_upgrade_view', active); }); note.append(upgrade); content.append(note);
        }
        ['download', 'excel', 'api'].forEach(method => {
            // 'excel' stays as the query value: it is in links already shared.
            const labels = {download: t('Tải file', 'Download'), excel: 'Google Sheets', api: 'API'};
            const b = el('button', labels[method], 'btn-data-secondary'); b.type = 'button'; b.dataset.method = method;
            b.onclick = () => select(method); methods.append(b);
        });
        const shortcuts = el('div', null, 'journey-actions');
        methods.querySelectorAll('button').forEach(button => {
            const shortcut = el('button', button.textContent, 'btn-data-secondary'); shortcut.type = 'button';
            shortcut.onclick = () => { select(button.dataset.method); panel.scrollIntoView({behavior: 'smooth', block: 'start'}); };
            shortcuts.append(shortcut);
        });
        intro.append(shortcuts);
        select(active.method); track('dataset_detail_view', active);
        try {
            sample = await snapshot(d); if (version !== revision) return;
            status.textContent = t('Bản xem trước: ', 'Preview: ') + coverage(sample.rows);
            introCoverage.textContent = status.textContent;
            const latest = sample.rows.map(r => String(r.date || r.period || '')).filter(Boolean).sort().at(-1);
            if (d.cadence === 'daily' && latest && Date.now() - Date.parse(latest) > 4 * 86400000) {
                status.append(el('strong', t(' · Dữ liệu quan sát đã hơn 4 ngày: kiểm tra trước khi sử dụng.', ' · Latest observation is over 4 days old: check before use.')));
            }
            if (sample.generated) status.append(el('span', ' · ' + t('Snapshot tạo lúc: ', 'Snapshot generated: ') + sample.generated.slice(0, 19).replace('T', ' ')));
            select(active.method);
        } catch (_) { if (version === revision) { status.textContent = t('Chưa tải được bản xem trước. Tải lại trang để thử lại; vẫn có thể đọc hướng dẫn kết nối.', 'Preview unavailable. Reload to retry; connection guides remain available.'); introCoverage.textContent = status.textContent; } }
    }
    function hide() { ++revision; active = null; ['dataset-intro', 'dataset-tools'].forEach(id => { const n = document.getElementById(id); if (n) n.hidden = true; }); }
    function updateContext() {
        if (!active) return;
        const card = document.querySelector(`.chart-card[data-chart-id="${active.id}"]`);
        const selected = card && card.querySelector('.filter-btn.active[data-period], .filter-btn.active[data-macro-period], .filter-btn.active[data-policy-period]');
        if (selected) active.period = selected.dataset.period || selected.dataset.macroPeriod || selected.dataset.policyPeriod;
        active.bank = document.getElementById('bankTypeSelect')?.value || 'ACB';
        remember(active);
    }
    function refresh() {
        buildDiscovery();
        if (active && window.VDOverview) show(window.VDOverview.byId(active.id), {...active});
    }
    function downloadError() {
        const status = document.querySelector('#dataset-tools .journey-status');
        if (status) status.textContent = t('Đã chạm hạn mức hoặc giới hạn tốc độ API. Chờ rồi thử lại; xem trang API key để kiểm tra quota trước khi nâng cấp.', 'API quota or rate limit reached. Retry later; check API key usage before upgrading.');
        document.getElementById('dataset-tools')?.scrollIntoView({behavior: 'smooth'});
    }
    window.VDJourney = {catalog, byId, selectedDataset, snapshot, coverage, rowsOf, csv, cleanContext, remember, recalled, route, pricingLink, show, hide, buildDiscovery, updateContext, refresh, downloadError, name, t, el, link, api};
    document.addEventListener('DOMContentLoaded', buildDiscovery);
    document.addEventListener('click', e => {
        if (e.target.closest('.filter-btn[data-period], .filter-btn[data-macro-period], .filter-btn[data-policy-period]')) {
            // Other modules also delegate at document level; read their settled state.
            queueMicrotask(() => { updateContext(); refresh(); });
        }
    });
    document.addEventListener('change', e => { if (e.target.id === 'bankTypeSelect') { updateContext(); refresh(); } });
})();
