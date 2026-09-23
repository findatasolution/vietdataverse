/* Analysis tabs for /pages/admin.html — Tổng quan, API, Tiền, Data Health.
 *
 * Split out of admin.html rather than added to its inline <script>: that file
 * is ~850 lines of operations code (list users, patch a user, reverify an
 * order) and this is reporting. Same split as be/routers/admin_report.py on the
 * server side.
 *
 * Contract with the page: it sets window.VDAdminReport.token before calling
 * anything, and the page owns tab switching. Every loader is idempotent and
 * safe to call again on a period change.
 *
 * Two rules this file keeps, because a report that overstates what it knows
 * stops being read — the exact fate of this project's DQ email:
 *   1. Never render a number the API did not send. Missing is "—", not 0.
 *   2. Surface the API's own `note` fields. They say when a zero means "not
 *      measured" rather than "nothing happened".
 *
 * All cell content goes in via textContent, never innerHTML — these tables
 * render user-supplied strings (emails, endpoints, plan names).
 */
window.VDAdminReport = (function () {
    'use strict';

    let token = null;
    const API = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
        ? 'http://127.0.0.1:8000'
        : window.location.origin;

    const num = n => (n === null || n === undefined) ? '—' : Number(n).toLocaleString('vi-VN');
    const vnd = n => (n === null || n === undefined) ? '—' : Number(n).toLocaleString('vi-VN') + ' ₫';
    const pct = n => (n === null || n === undefined) ? '—' : Number(n).toLocaleString('vi-VN') + '%';
    const dt = s => {
        if (!s) return '—';
        // Backend serialises datetimes with json.dumps(default=str), so they
        // arrive as "2026-09-23 07:56:53.209081" — naive, space-separated, no
        // zone. new Date() would read that as local time and can shift the day,
        // the same trap fuel-forecast.html documents. Read the prefix as text.
        return String(s).slice(0, 19).replace('T', ' ');
    };

    function el(tag, opts = {}) {
        const node = document.createElement(tag);
        if (opts.text !== undefined) node.textContent = opts.text === null ? '—' : String(opts.text);
        if (opts.cls) node.className = opts.cls;
        if (opts.style) node.style.cssText = opts.style;
        if (opts.title) node.title = opts.title;
        return node;
    }

    // APPENDS a table. It must never clear the container: each tab renders a
    // heading, then a table, then another heading, then another table into the
    // same root. An earlier version called container.replaceChildren() here,
    // so every call erased everything before it and only the last table
    // survived — the funnel cards rendered and then vanished.
    function table(container, headers, rows, emptyMsg) {
        if (!rows.length) {
            container.appendChild(el('p', {
                text: emptyMsg || 'Chưa có dữ liệu',
                style: 'color:var(--text-tertiary);padding:18px 0;font-size:13px;'
            }));
            return;
        }
        const t = el('table', {cls: 'admin-table'});
        const thead = el('thead');
        const hr = el('tr');
        headers.forEach(h => hr.appendChild(el('th', {text: h})));
        thead.appendChild(hr);
        t.appendChild(thead);
        const tb = el('tbody');
        rows.forEach(cells => {
            const tr = el('tr');
            cells.forEach(c => {
                const td = el('td');
                if (c && typeof c === 'object' && !Array.isArray(c)) {
                    td.textContent = c.text === null || c.text === undefined ? '—' : String(c.text);
                    if (c.cls) td.className = c.cls;
                    if (c.style) td.style.cssText = c.style;
                    if (c.title) td.title = c.title;
                } else {
                    td.textContent = c === null || c === undefined ? '—' : String(c);
                }
                tr.appendChild(td);
            });
            tb.appendChild(tr);
        });
        t.appendChild(tb);
        const scroller = el('div', {style: 'overflow-x:auto;'});
        scroller.appendChild(t);
        container.appendChild(scroller);
    }

    function note(container, text) {
        if (!text) return;
        container.appendChild(el('p', {
            text,
            style: 'color:var(--text-tertiary);font-size:12px;margin:8px 0 0;line-height:1.5;'
        }));
    }

    function heading(container, text) {
        container.appendChild(el('div', {text, cls: 'section-h', style: 'font-size:14px;margin-top:24px;'}));
    }

    async function get(path) {
        const res = await fetch(`${API}${path}`, {headers: {Authorization: `Bearer ${token}`}});
        if (!res.ok) throw new Error(`${path} → HTTP ${res.status}`);
        return res.json();
    }

    function failed(container, err) {
        container.replaceChildren();
        container.appendChild(el('p', {
            text: 'Không tải được: ' + err.message,
            style: 'color:#ef5350;font-size:13px;padding:18px 0;'
        }));
    }

    /* ── Tab: Tổng quan ─────────────────────────────────────────────────── */

    async function loadOverview(period) {
        const root = document.getElementById('report-funnel');
        if (!root) return;
        try {
            const d = await get(`/api/v1/admin/report/funnel?period=${encodeURIComponent(period)}`);
            root.replaceChildren();

            // The funnel is the point of this tab: each step shows how many of
            // the PREVIOUS step's people got here, which is the number that
            // says where to spend effort.
            const wrap = el('div', {cls: 'kpi-grid'});
            d.steps.forEach(s => {
                const card = el('div', {cls: 'kpi-card'});
                card.appendChild(el('div', {cls: 'kpi-label', text: s.label}));
                card.appendChild(el('div', {cls: 'kpi-value', text: num(s.value)}));
                const sub = el('div', {cls: 'kpi-sub'});
                const bits = [];
                if (s.from_prev_pct !== null && s.from_prev_pct !== undefined) bits.push(`${pct(s.from_prev_pct)} của bậc trước`);
                if (s.warning) bits.push(s.warning);
                if (s.note) bits.push(s.note);
                sub.textContent = bits.join(' · ');
                card.appendChild(sub);
                wrap.appendChild(card);
            });
            root.appendChild(wrap);

            heading(root, 'Đơn hàng');
            const o = d.orders;
            table(root,
                ['Phạm vi', 'Đơn tạo', 'Đơn đã trả', 'Tỉ lệ trả'],
                [
                    ['Trong kỳ', num(o.period.created), num(o.period.paid),
                     o.period.created ? pct(Math.round(1000 * o.period.paid / o.period.created) / 10) : '—'],
                    ['Toàn bộ', num(o.all_time.created), num(o.all_time.paid), pct(o.all_time.paid_pct)],
                ]);
            note(root, 'Đơn "tạo" là đơn đã bấm thanh toán nhưng chưa trả tiền. '
                     + 'Khoảng cách giữa hai cột này là chỗ mất khách rõ nhất trong dữ liệu hiện có.');
        } catch (e) { failed(root, e); }
    }

    /* ── Tab: API ───────────────────────────────────────────────────────── */

    async function loadApi(period) {
        const root = document.getElementById('report-api');
        if (!root) return;
        try {
            const d = await get(`/api/v1/admin/report/api?period=${encodeURIComponent(period)}`);
            root.replaceChildren();

            heading(root, 'Theo ngày');
            table(root, ['Ngày', 'Tổng', 'Thành công', 'Bị từ chối', 'Ẩn danh'],
                d.by_day.map(r => [r.day, num(r.total), num(r.ok), num(r.rejected), num(r.anonymous)]),
                'Không có lượt gọi nào trong kỳ');

            heading(root, 'Theo endpoint');
            table(root, ['Endpoint', 'Lượt gọi', 'Thành công', 'Từ chối', 'Người gọi'],
                d.by_endpoint.map(r => [r.endpoint, num(r.calls), num(r.ok), num(r.rejected), num(r.users)]));

            heading(root, 'Theo mã trạng thái');
            table(root, ['HTTP', 'Lượt gọi', 'Nghĩa'],
                d.by_status.map(r => [r.status_code, num(r.calls), statusMeaning(r.status_code)]));

            heading(root, 'Người gọi & mức tiêu quota tháng này');
            table(root,
                ['Email', 'Level', 'Gói', 'Lượt gọi', 'Từ chối', 'Qua key', 'Đã dùng/Hạn mức', '%', 'Gọi gần nhất'],
                d.callers.map(c => [
                    c.email, c.user_level, c.current_plan || '—',
                    num(c.calls), num(c.rejected), num(c.via_key),
                    c.quota_limit === null || c.quota_limit === undefined
                        ? `${num(c.quota_used)} / không giới hạn`
                        : `${num(c.quota_used)} / ${num(c.quota_limit)}`,
                    {text: pct(c.quota_pct),
                     style: c.quota_pct >= 80 ? 'color:#ef5350;font-weight:600;' : ''},
                    dt(c.last_call),
                ]),
                'Chưa ai gọi API trong kỳ này');
            note(root, 'Hạn mức lấy trực tiếp từ be/quota.py theo level + gói của từng người, '
                     + 'không phải số viết cứng trong trang.');

            heading(root, 'Lượt gọi ẩn danh — nhu cầu chưa đăng ký');
            table(root, ['Endpoint', 'HTTP', 'Lượt gọi'],
                d.anonymous.rows.map(r => [r.endpoint, r.status_code, num(r.calls)]),
                'Chưa ghi nhận lượt gọi ẩn danh nào trong kỳ');
            note(root, d.anonymous.note
                     + (d.anonymous.recording_since
                        ? ` Dòng ẩn danh đầu tiên: ${dt(d.anonymous.recording_since)}.`
                        : ' Chưa có dòng ẩn danh nào.'));
        } catch (e) { failed(root, e); }
    }

    function statusMeaning(code) {
        const map = {
            200: 'OK', 304: 'Không đổi',
            401: 'Chưa đăng nhập / key sai — người muốn dùng nhưng bị chặn',
            403: 'Sai tier (ví dụ free gọi endpoint premium)',
            429: 'Hết quota tháng hoặc vượt burst',
            500: 'Lỗi máy chủ',
        };
        return map[code] || '';
    }

    /* ── Tab: Tiền ──────────────────────────────────────────────────────── */

    async function loadMoney(period) {
        const root = document.getElementById('report-money');
        if (!root) return;
        try {
            const d = await get(`/api/v1/admin/report/money?period=${encodeURIComponent(period)}`);
            root.replaceChildren();

            heading(root, 'Đơn hàng theo trạng thái');
            table(root, ['Trạng thái', 'Số đơn', 'Giá trị'],
                d.orders.by_status.map(r => [r.status, num(r.orders), vnd(r.amount)]));

            heading(root, 'Đơn hàng theo gói');
            table(root, ['Gói', 'Trạng thái', 'Số đơn', 'Giá trị'],
                d.orders.by_plan.map(r => [r.plan, r.status, num(r.orders), vnd(r.amount)]));
            note(root, 'Gói không còn trong catalog (premium_monthly, dev_yearly, monthly…) là đơn cũ '
                     + 'chưa thanh toán; chúng không thể kích hoạt lại được nữa.');

            heading(root, 'Doanh thu theo tháng (toàn bộ lịch sử)');
            table(root, ['Tháng', 'Số đơn', 'Doanh thu'],
                d.revenue_by_month.map(r => [r.month, num(r.orders), vnd(r.amount)]),
                'Chưa có đơn nào được thanh toán');

            const m = d.marketplace;
            heading(root, 'Agent Market & subscription');
            if (!m.available) {
                note(root, m.note);
            } else {
                const grid = el('div', {cls: 'kpi-grid'});
                [['Sản phẩm', m.products], ['Người bán', m.sellers],
                 ['Lượt mua', (m.purchases[0] || {}).purchases],
                 ['Credit đã tiêu', (m.purchases[0] || {}).credits],
                 ['Credit về người bán', m.seller_earnings]].forEach(([label, value]) => {
                    const c = el('div', {cls: 'kpi-card'});
                    c.appendChild(el('div', {cls: 'kpi-label', text: label}));
                    c.appendChild(el('div', {cls: 'kpi-value', text: num(value)}));
                    grid.appendChild(c);
                });
                root.appendChild(grid);

                heading(root, 'Sổ credit');
                table(root, ['Loại', 'Bút toán', 'Credit'],
                    m.credit_ledger.map(r => [r.kind, num(r.entries), num(r.credits)]));

                heading(root, 'Subscription nền tảng');
                table(root, ['Sản phẩm', 'Trạng thái', 'Số lượng'],
                    m.subscriptions.map(r => [r.product_code, r.status, num(r.subs)]),
                    'Chưa có subscription nào');
                table(root, ['Sự kiện', 'Số lần', 'Gần nhất'],
                    m.subscription_events.map(r => [r.event, num(r.events), dt(r.last_at)]),
                    'Chưa có sự kiện subscription nào');
                note(root, m.note);
            }
        } catch (e) { failed(root, e); }
    }

    /* ── Tab: Data Health ───────────────────────────────────────────────── */

    const STATUS_LABEL = {
        ok: 'Tươi', late: 'Đang trễ', stale: 'Đứng im',
        empty: 'Rỗng', error: 'Lỗi truy vấn',
    };
    const STATUS_STYLE = {
        ok: 'color:#66bb6a;font-weight:600;',
        late: 'color:#ffa726;font-weight:600;',
        stale: 'color:#ef5350;font-weight:700;',
        empty: 'color:#ef5350;font-weight:600;',
        error: 'color:#ef5350;font-weight:600;',
    };

    async function loadDataHealth() {
        const root = document.getElementById('report-data');
        if (!root) return;
        try {
            const d = await get('/api/v1/admin/report/data-health');
            root.replaceChildren();

            const s = d.summary;
            const grid = el('div', {cls: 'kpi-grid'});
            [['Bảng theo dõi', s.total], ['Tươi', s.ok], ['Đang trễ', s.late],
             ['Đứng im', s.stale], ['Rỗng / lỗi', s.empty + s.error]].forEach(([label, value]) => {
                const c = el('div', {cls: 'kpi-card'});
                c.appendChild(el('div', {cls: 'kpi-label', text: label}));
                c.appendChild(el('div', {cls: 'kpi-value', text: num(value)}));
                grid.appendChild(c);
            });
            root.appendChild(grid);

            Object.keys(d.groups).forEach(cadence => {
                heading(root, cadence);
                table(root,
                    ['Nguồn', 'Bảng', 'DB', 'Mới nhất', 'Tuổi (ngày)', 'Ngưỡng', 'Số dòng', 'Trạng thái'],
                    d.groups[cadence].map(e => [
                        e.label, e.table, e.db,
                        e.latest ? String(e.latest).slice(0, 10) : '—',
                        e.age_days === null || e.age_days === undefined ? '—' : num(e.age_days),
                        num(e.max_age_days), num(e.rows),
                        {text: STATUS_LABEL[e.status] || e.status,
                         style: STATUS_STYLE[e.status] || '',
                         title: e.error || ''},
                    ]));
            });
            note(root, '"Tuổi" tính từ kỳ dữ liệu mới nhất trong bảng tới hôm nay, không phải từ lần '
                     + 'crawl cuối — một crawler chạy đều mà nguồn ngừng cập nhật vẫn phải hiện ra ở đây. '
                     + 'Ngưỡng đặt theo nhịp thật của từng nguồn; quá gấp đôi ngưỡng thì coi là đứng im.');
        } catch (e) { failed(root, e); }
    }

    return {
        set token(v) { token = v; },
        get token() { return token; },
        loadOverview, loadApi, loadMoney, loadDataHealth,
    };
})();
