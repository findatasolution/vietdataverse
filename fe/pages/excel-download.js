/* Download the generated workbook without putting the API key in the URL.
 *
 * There is no hosted file to link to: be/routers/excel_export.py builds the
 * workbook per request, already filled with data, and the metering middleware
 * gates it on the key. The button uses fetch + Blob so the key can be sent in
 * X-API-Key. It is never placed in the address bar,
 * stored in localStorage or embedded in the downloaded workbook.
 */
(function () {
    'use strict';

    const API = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
        ? 'http://127.0.0.1:8000'
        : 'https://api.vietdataverse.online';

    function init() {
        const keyInput = document.getElementById('xl-key');
        const periodSel = document.getElementById('xl-period');
        const button = document.getElementById('xl-download');
        const hint = document.getElementById('xl-hint');
        if (!keyInput || !button) return;

        const en = () => document.documentElement.lang === 'en';
        const t = (vi, eng) => (en() ? eng : vi);

        function update() {
            const key = keyInput.value.trim();
            if (!key) {
                // Disabled as an anchor: no href, and aria-disabled so a screen
                // reader is told too. A click with an empty key would just
                // bounce off a 401 and look like the site is broken.
                button.removeAttribute('href');
                button.setAttribute('aria-disabled', 'true');
                button.style.opacity = '0.5';
                button.style.pointerEvents = 'none';
                if (hint) hint.textContent = t('Dán API key vào ô trên để bật nút tải.',
                                              'Paste your API key above to enable the download.');
                return;
            }
            button.removeAttribute('href');
            button.removeAttribute('aria-disabled');
            button.style.opacity = '';
            button.style.pointerEvents = '';
            if (hint) {
                hint.textContent = t(
                    'Mỗi lần tải tính là một lượt gọi API. Key không được lưu trong file.',
                    'Each download counts as one API call. Your key is not stored in the file.');
            }
        }

        async function download(event) {
            event.preventDefault();
            const key = keyInput.value.trim();
            if (!key) return;
            const period = periodSel ? periodSel.value : '1y';
            const original = button.textContent;
            button.setAttribute('aria-disabled', 'true');
            button.style.pointerEvents = 'none';
            button.textContent = t('Đang tạo file…', 'Building workbook…');
            try {
                const response = await fetch(
                    `${API}/api/v1/excel/workbook?period=${encodeURIComponent(period)}`,
                    {headers: {'X-API-Key': key}}
                );
                if (!response.ok) {
                    let detail = '';
                    try { detail = (await response.json()).detail || ''; } catch (_) {}
                    throw new Error(detail || `HTTP ${response.status}`);
                }
                const blob = await response.blob();
                const disposition = response.headers.get('Content-Disposition') || '';
                const match = disposition.match(/filename="?([^";]+)"?/i);
                const filename = match ? match[1] : `VietDataverse-${period}.xlsx`;
                const objectUrl = URL.createObjectURL(blob);
                const link = document.createElement('a');
                link.href = objectUrl;
                link.download = filename;
                document.body.appendChild(link);
                link.click();
                link.remove();
                URL.revokeObjectURL(objectUrl);
                if (hint) hint.textContent = t(
                    'Đã tải file. Cài Viet Dataverse Add-in một lần để refresh ngay trong Excel.',
                    'Downloaded. Install the Viet Dataverse Add-in once to refresh inside Excel.');
            } catch (error) {
                if (hint) hint.textContent = t('Không tải được file: ', 'Download failed: ') + error.message;
            } finally {
                button.removeAttribute('aria-disabled');
                button.style.pointerEvents = '';
                button.textContent = original;
            }
        }

        keyInput.addEventListener('input', update);
        if (periodSel) periodSel.addEventListener('change', update);
        button.addEventListener('click', download);
        // The En/Vi toggle replaces innerHTML of translated blocks, which would
        // wipe the hint text this script writes — re-run after every switch.
        document.addEventListener('docs-lang-changed', update);
        update();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
