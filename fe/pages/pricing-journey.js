/* Purchase facts and a bounded return to the selected dataset. */
(function () {
    'use strict';
    const J = window.VDJourney;
    const context = J.cleanContext(Object.fromEntries(new URLSearchParams(location.search))) || J.recalled();
    if (context) J.remember(context);
    let facts = null;
    let ready = false;
    const number = n => n.toLocaleString('vi-VN');
    function resumeHref() { return context ? J.route(context) : new URL('../index.html#data/portal', location.href).href; }
    function renderFacts() {
        if (!facts) return;
        const free = facts.find(p => p.key === 'free');
        const paid = facts.find(p => p.key === PLANS[_billingPeriod].key);
        document.getElementById('free-quota').textContent = `${number(free.monthly)} request/tháng · ${free.burst_per_sec} request/giây`;
        document.getElementById('paid-quota').textContent = `${number(paid.monthly)} request/tháng`;
        document.getElementById('paid-burst').textContent = `Tối đa ${paid.burst_per_sec} request/giây`;
        const amount = _studentVerified ? paid.amount / 2 : paid.amount;
        document.getElementById('billing-footer-note').textContent = `Thanh toán một lần ${number(amount)}đ cho ${paid.days} ngày · Không tự động gia hạn`
            + (paid.days === 365 ? ` · Quy đổi ${number(Math.round(amount / 12))}đ/tháng` : '');
    }
    async function loadPlans() {
        const status = document.getElementById('plan-status');
        try {
            const response = await fetch(`${J.api}/payment/plans`);
            if (!response.ok) throw new Error('Plans unavailable');
            const json = await response.json();
            if (!json.success || !Array.isArray(json.data)) throw new Error('Invalid plans');
            for (const key of ['free', 'pro_monthly', 'pro_yearly']) {
                const p = json.data.find(p => p.key === key);
                if (!p || !Number.isFinite(p.amount) || !Number.isFinite(p.monthly) || !Number.isFinite(p.burst_per_sec) || (key !== 'free' && !(p.days > 0))) throw new Error('Incomplete plans');
            }
            facts = json.data;
            for (const period of ['monthly', 'yearly']) {
                const p = facts.find(p => p.key === PLANS[period].key);
                Object.assign(PLANS[period], {amount: p.amount, amountStudent: p.amount / 2,
                    display: number(p.amount), displayStudent: number(p.amount / 2), period: `/${p.days} ngày`,
                    confirmLabel: `Thanh toán ${number(p.amount)}₫ / ${p.days} ngày →`,
                    confirmLabelStu: `Thanh toán ${number(p.amount / 2)}₫ / ${p.days} ngày →`});
            }
            ready = true;
            document.getElementById('btn-pro').disabled = false;
            status.textContent = 'Giá và hạn mức được đọc từ cấu hình thanh toán hiện hành. API có quota, không phải unlimited.';
            switchBilling(_billingPeriod);
        } catch (_) {
            ready = false;
            document.getElementById('btn-pro').disabled = true;
            status.replaceChildren(J.el('span', 'Chưa kiểm tra được giá và hạn mức. Chưa mở thanh toán để tránh hiển thị sai. '));
            const retry = J.el('button', 'Thử lại', 'btn-data-secondary'); retry.onclick = loadPlans; status.append(retry);
        }
    }
    function init() {
        if (context) {
            const root = document.getElementById('purchase-context'); root.hidden = false;
            const d = J.selectedDataset(context);
            root.append(J.el('h2', 'Dữ liệu bạn đang quan tâm: ' + J.name(d)),
                J.el('p', `Cách dùng: ${context.method === 'excel' ? 'Google Sheets' : context.method === 'api' ? 'API' : 'Tải file'} · Kỳ biểu đồ: ${context.period || 'mặc định'}`),
                J.el('p', 'Miễn phí để kiểm tra dữ liệu và thử API. Nâng cấp tăng hạn mức gọi API; không mở thêm lịch sử độc quyền.'),
                J.link('Tiếp tục dùng miễn phí với dataset này', resumeHref()));
            const range = J.el('p', 'Đang kiểm tra phạm vi bản xem trước…'); root.append(range);
            J.snapshot(d).then(s => { range.textContent = 'Snapshot công khai: ' + J.coverage(s.rows); }).catch(() => { range.textContent = 'Chưa tải được phạm vi snapshot. Hãy kiểm tra trên trang dataset trước khi mua.'; });
        }
        const grid = document.getElementById('pricing-catalog');
        J.catalog.forEach(d => {
            const item = J.el('article', null, 'journey-dataset');
            item.append(J.link(J.name(d), J.route({id: d.id}), ''), J.el('small', `${d.source} · ${d.unit}`));
            const range = J.el('small', 'Đang kiểm tra snapshot…'); item.append(range);
            item.append(J.el('small', d.endpoint ? 'CSV snapshot · Google Sheets · API' : 'CSV snapshot · Chưa có API riêng'));
            grid.append(item);
            J.snapshot(d).then(s => { range.textContent = J.coverage(s.rows); }).catch(() => { range.textContent = 'Snapshot tạm không khả dụng'; });
        });
        // Fuel is a standalone product page, not a chart in the SPA overview, so it
        // stays out of J.catalog (tests pin catalog to VDOverview.REGISTRY).
        const fuel = J.el('article', null, 'journey-dataset');
        fuel.append(J.link('Giá xăng dầu & dự báo', new URL('fuel-forecast.html', location.href).href, ''),
            J.el('small', 'Bộ Công Thương · VND/lít'));
        const fuelRange = J.el('small', 'Đang kiểm tra dữ liệu…'); fuel.append(fuelRange);
        fuel.append(J.el('small', 'E5RON92 · Diesel 0.05S · Kịch bản dự báo'));
        grid.append(fuel);
        fetch(`${J.api}/fuel-forecast/E5RON92`)
            .then(r => { if (!r.ok) throw new Error('Fuel data unavailable'); return r.json(); })
            .then(json => { fuelRange.textContent = J.coverage(json.data.history); })
            .catch(() => { fuelRange.textContent = 'Dữ liệu tạm không khả dụng'; });
        loadPlans();
    }
    window.VDPricing = {resumeHref, renderFacts, ready: () => ready};
    document.addEventListener('DOMContentLoaded', init);
})();
