/* The return URL is a hint only; the server must confirm payment and product. */
(function () {
    'use strict';
    function paidSubscription(data) {
        return data.success === true && data.status === 'paid' && data.order_type === 'subscription'
            && (data.activated === true || data.already_paid === true);
    }
    function reportPurchase(order, data) {
        if (!paidSubscription(data) || !Number.isFinite(data.amount) || data.amount <= 0) return;
        const key = 'vd.purchase.' + order;
        try { if (sessionStorage.getItem(key)) return; } catch (_) { /* Storage can be blocked. */ }
        window.VDAnalytics?.track('purchase', {transaction_id: String(order), currency: 'VND', value: data.amount,
            plan: data.plan, items: [{item_id: data.plan, item_name: 'API Supper Lite', price: data.amount, quantity: 1}]});
        try { sessionStorage.setItem(key, '1'); } catch (_) { /* GA also deduplicates transaction IDs. */ }
    }
    function node(tag, text, cls) {
        const n = document.createElement(tag); n.textContent = text; if (cls) n.className = cls; return n;
    }
    async function confirmReturn(api) {
        const params = new URLSearchParams(location.search);
        const payment = params.get('payment');
        const order = params.get('order');
        const banner = document.getElementById('result-banner');
        if (!payment || !banner) return;
        const link = (label, href, cls = 'btn-home') => { const n = node('a', label, cls); n.href = href; return n; };
        function render(title, description, success = false, retry = false) {
            banner.className = success ? 'success' : 'cancelled';
            banner.replaceChildren(node('div', title, 'result-title'), node('p', description, 'result-desc'));
            const actions = node('div', '', 'result-actions');
            if (success) {
                actions.append(link('Lấy / kiểm tra API key', 'developer.html', 'btn-cta-sm'),
                    link('Mẫu kết nối Excel', 'excel.html#starter', 'btn-data-secondary'));
            }
            actions.append(link('Trở lại dữ liệu đã chọn', window.VDPricing?.resumeHref() || '../index.html#data/portal'));
            if (retry) {
                const button = node('button', 'Kiểm tra lại thanh toán', 'btn-cta-sm');
                button.type = 'button'; button.onclick = () => confirmReturn(api); actions.append(button);
            }
            banner.append(actions);
        }
        if (payment === 'cancelled') {
            render('Bạn đã rời trang thanh toán', 'Nếu đã chuyển tiền, hãy kiểm tra tài khoản trước khi tạo đơn mới.'); return;
        }
        if (payment !== 'success' || !/^\d{1,16}$/.test(order || '')) {
            render('Chưa xác định được đơn hàng', 'Mở lại đường dẫn trả về từ PayOS hoặc kiểm tra tài khoản.'); return;
        }
        render('Đang xác nhận thanh toán…', 'Đang kiểm tra trạng thái đơn hàng với PayOS.');
        try {
            for (let attempt = 0; attempt < 4; attempt++) {
                const response = await fetch(`${api}/api/v1/payment/verify-order/${order}`, {method: 'POST'});
                if (!response.ok) throw new Error('Verification unavailable');
                const data = await response.json();
                if (paidSubscription(data)) {
                    render('Thanh toán thành công!', 'Gói API đã được kích hoạt. Đăng nhập bằng đúng email thanh toán để lấy API key. Key đang dùng giữ nguyên.', true);
                    reportPurchase(order, data); return;
                }
                if (data.success && data.status === 'paid' && data.order_type === 'credit_topup') {
                    render('Đã xác nhận nạp credits', 'Kiểm tra số dư trong ví của bạn. Đây là đơn nạp ví.', false); return;
                }
                if (['CANCELLED', 'EXPIRED'].includes(data.status)) {
                    render('Đơn hàng đã huỷ hoặc hết hạn', 'Nếu đã chuyển tiền, hãy liên hệ hỗ trợ và không thanh toán lại.'); return;
                }
                if (attempt < 3) await new Promise(resolve => setTimeout(resolve, 1500));
            }
            render('Đang chờ xác nhận thanh toán', 'Chưa xác nhận gói đã kích hoạt. Nếu đã chuyển tiền, không thanh toán lại; hãy kiểm tra lại sau ít phút.', false, true);
        } catch (_) {
            render('Chưa xác minh được thanh toán', 'Chưa xác nhận gói đã kích hoạt. Nếu đã bị trừ tiền, không thanh toán lại. Bạn có thể kiểm tra lại đơn này.', false, true);
        }
    }
    window.VDCheckout = {confirmReturn, paidSubscription, reportPurchase};
})();
