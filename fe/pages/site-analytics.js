/* Purchase-journey measurement. Never send credentials, email or URL queries. */
(function () {
    'use strict';
    const enabled = ['vietdataverse.online', 'www.vietdataverse.online'].includes(location.hostname);
    const measurement = 'G-YB3PKHN2E5';
    const cleanURL = value => {
        if (!value) return '';
        try { const u = new URL(value, location.origin); return u.origin + u.pathname; }
        catch (_) { return ''; }
    };
    const page = () => ({page_location: cleanURL(location.href), page_referrer: cleanURL(document.referrer || '')});
    function track(name, params = {}) {
        if (!enabled || typeof window.gtag !== 'function') return;
        const allowed = ['dataset', 'method', 'plan', 'currency', 'value', 'transaction_id', 'items', 'step'];
        const safe = Object.fromEntries(Object.entries(params).filter(([key]) => allowed.includes(key)));
        window.gtag('event', name, {...safe, ...page(), send_to: measurement});
    }
    window.VDAnalytics = {track};
    if (!enabled) return;
    window.dataLayer = window.dataLayer || [];
    window.gtag = window.gtag || function () { window.dataLayer.push(arguments); };
    window.gtag('js', new Date());
    window.gtag('config', measurement, {...page(), send_page_view: false});
    track('page_view');
    const script = document.createElement('script');
    script.async = true;
    script.src = 'https://www.googletagmanager.com/gtag/js?id=' + measurement;
    document.head.append(script);
})();
