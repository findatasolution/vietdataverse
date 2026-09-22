/* Ready-to-paste Power Query examples. API keys are entered only inside Excel. */
(function () {
    'use strict';
    const datasets = {
        fxrate: {path: 'sbv-rate', query: {bank: 'SBV', currency: 'USD', period: '1y', page: '1', limit: '500'}, types: [['date', 'type date'], ['buy', 'type number'], ['buy_cash', 'type number'], ['sell', 'type number']]},
        cpi: {path: 'macro/cpi', query: {view: 'monthly', years: '5'}, types: [['period', 'type text'], ['mom_pct', 'type number'], ['yoy_pct', 'type number']]},
        gdp: {path: 'macro/gdp', query: {}, types: [['year', 'Int64.Type'], ['quarter', 'Int64.Type'], ['sector', 'type text'], ['gdp_billion_vnd', 'type number'], ['growth_yoy_pct', 'type number']]}
    };
    function queryFor(id) {
        const d = Object.prototype.hasOwnProperty.call(datasets, id) ? datasets[id] : null;
        if (!d) throw new Error('Unsupported dataset');
        const query = Object.entries(d.query).map(([key, value]) => `${key} = "${value}"`).join(', ');
        const types = d.types.map(([name, type]) => `{"${name}", ${type}}`).join(', ');
        return `let
    ApiKey = "YOUR_API_KEY",
    Response = Json.Document(Web.Contents("https://api.vietdataverse.online", [
        RelativePath = "api/v1/${d.path}",
        Query = [${query}],
        Headers = [#"X-API-Key" = ApiKey],
        Timeout = #duration(0, 0, 0, 30)
    ])),
    Rows = if Response[success] = true then Response[data] else error "API request failed",
    Complete = if Record.FieldOrDefault(Response, "pages", 1) > 1
        then error "More pages available. Narrow the requested period before using this report."
        else Rows,
    Result = Table.FromRecords(Complete, {${d.types.map(([name]) => `"${name}"`).join(", ")}}, MissingField.UseNull),
    Typed = Table.TransformColumnTypes(Result, {${types}}, "en-US")
in
    Typed`;
    }
    function init() {
        const root = document.getElementById('excel-starter-controls');
        if (!root) return;
        const J = window.VDJourney;
        const t = (vi, en) => document.documentElement.lang === 'en' ? en : vi;
        let selection = new URLSearchParams(location.search).get('dataset');
        if (!Object.prototype.hasOwnProperty.call(datasets, selection)) selection = 'fxrate';
        let revision = 0;
        function render() {
            const version = ++revision;
            const label = J.el('label', t('Chọn dữ liệu', 'Choose a dataset')); label.htmlFor = 'starter-dataset';
            const select = J.el('select'); select.id = 'starter-dataset';
            Object.keys(datasets).forEach(id => { const option = J.el('option', J.name(J.byId(id))); option.value = id; select.append(option); });
            select.value = selection;
            select.onchange = () => { selection = select.value; render(); };
            const code = J.el('textarea'); code.readOnly = true; code.rows = 14; code.className = 'journey-code';
            code.setAttribute('aria-label', 'Power Query M'); code.value = queryFor(selection);
            const status = J.el('p', '', 'journey-status'); status.setAttribute('role', 'status');
            const copy = J.el('button', t('Sao chép mẫu Power Query', 'Copy Power Query example'), 'btn-data-primary'); copy.type = 'button';
            copy.onclick = async () => {
                try {
                    await navigator.clipboard.writeText(code.value);
                    status.textContent = t('Đã sao chép. Dán vào Advanced Editor trong Excel.', 'Copied. Paste into the Advanced Editor in Excel.');
                    window.VDAnalytics?.track('excel_query_copy', {dataset: selection, method: 'excel'});
                } catch (_) {
                    code.focus(); code.select();
                    status.textContent = t('Đã chọn mẫu. Nhấn Ctrl+C hoặc ⌘C để sao chép.', 'Example selected. Press Ctrl+C or ⌘C to copy.');
                }
            };
            const actions = J.el('div', null, 'journey-actions');
            actions.append(copy, J.link(t('Lấy API key miễn phí', 'Get a free API key'), 'developer.html', 'btn-data-secondary'),
                J.link(t('Xem gói API 45.000đ', 'View the 45,000 VND API plan'), J.pricingLink({id: selection, method: 'excel'}), 'btn-data-secondary'));
            const preview = J.el('p', t('Đang kiểm tra bản mẫu công khai…', 'Checking the public sample…'), 'journey-status');
            root.replaceChildren(label, select, code, actions, status, preview);
            J.snapshot(J.byId(selection)).then(sample => {
                if (version !== revision) return;
                preview.textContent = t('Bản mẫu công khai (phạm vi có thể khác API): ', 'Public sample (coverage may differ from the API): ') + J.coverage(sample.rows);
                const rows = sample.rows.slice(-3);
                if (!rows.length) return;
                const wrap = J.el('div', null, 'journey-table'); const table = J.el('table');
                const fields = Object.keys(rows[0]).filter(key => !['id', 'crawl_time'].includes(key));
                const head = J.el('thead'); const tr = J.el('tr'); fields.forEach(key => tr.append(J.el('th', key))); head.append(tr); table.append(head);
                const body = J.el('tbody'); rows.forEach(row => { const line = J.el('tr'); fields.forEach(key => line.append(J.el('td', row[key] == null ? '—' : typeof row[key] === 'number' ? row[key].toLocaleString('vi-VN') : String(row[key])))); body.append(line); }); table.append(body); wrap.append(table); root.append(wrap);
            }).catch(() => { if (version === revision) preview.textContent = t('Bản mẫu tạm không tải được. Hãy thử bằng API key miễn phí trước khi mua.', 'Sample unavailable. Test with a free API key before purchasing.'); });
        }
        render();
        window.addEventListener('docs-lang-changed', render);
    }
    window.VDExcelStarter = {queryFor};
    document.addEventListener('DOMContentLoaded', init);
})();
