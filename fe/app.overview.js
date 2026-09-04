/*
 * Open Data — Overview grid.
 *
 * Spec: docs/superpowers/specs/2026-08-17-open-data-overview-design.md
 *
 * Why this file exists at all: #data/portal used to render five sections stacked
 * vertically, so a visitor landed on a hero plus one chart and never learned the
 * other nine existed. This renders every indicator as a small chart in one grid,
 * and clicking one opens it full size.
 *
 * Boundaries — this module owns the OVERVIEW only:
 *   - CHART_REGISTRY: the single declaration of what charts exist
 *   - the grid, the tiles, and their small Chart.js instances
 *   - the overview <-> detail routing decision
 * It does NOT own the full-size charts. Those stay in app.js and are reached
 * through the globals it already exposes (loadChartData, loadPolicyRates,
 * loadMacroCharts, loadVnindexChart, chartInstances, and the number formatters).
 * Duplicating any of that here would let the two drift apart.
 *
 * Exposed as window.VDOverview, following the window.KM precedent in
 * app.knowledge.js.
 */
(function () {
    'use strict';

    /* ── Registry ──────────────────────────────────────────────────────────────
       `family` records which of app.js's four unrelated loading paths a chart
       uses. They are deliberately NOT unified — that refactor carries its own
       risk and does not serve this feature.

       `mini` describes how to draw the small version: which static JSON to read
       and which numeric field to plot. The overview reads static files directly
       rather than calling the metered API, because anonymous visitors get 401
       there and the files are already prefetched for five of these ten. */
    const CHART_REGISTRY = [
        {
            id: 'gold', section: 'gold-silver', family: 'dispatch',
            chartType: 'gold', domCardId: 'gold',
            i18nKey: 'ovGold',
            title: 'Giá vàng trong nước', source: 'DOJI HN', unit: 'triệu/lượng', unitKey: 'unitTrieuLuong',
            detailPeriod: '1m',
            mini: { file: 'data/gold_DOJI_HN_1m.json', series: 'buy_prices',
                    scale: 1e6, decimals: 1, color: '#2f5fde', periodic: true }
        },
        {
            id: 'silver', section: 'gold-silver', family: 'dispatch',
            chartType: 'silver', domCardId: 'silver',
            i18nKey: 'ovSilver',
            title: 'Giá bạc trong nước', source: 'Phú Quý', unit: 'triệu/lượng', unitKey: 'unitTrieuLuong',
            detailPeriod: '1m',
            mini: { file: 'data/silver_1m.json', series: 'buy_prices',
                    scale: 1e6, decimals: 2, color: '#4d4c48', periodic: true }
        },
        {
            id: 'termdepo', section: 'currency', family: 'dispatch',
            // internal chartInstances key is 'td', not 'termdepo'
            chartType: 'td', domCardId: 'termdepo',
            i18nKey: 'ovTermdepo',
            title: 'Lãi suất gửi tiết kiệm', source: 'ACB', unit: '%/năm', unitKey: 'unitPctYear',
            detailPeriod: '1y',
            mini: { file: 'data/termdepo_ACB_1y.json', series: 'term_12m',
                    scale: 1, decimals: 2, color: '#1e3fae', stepped: false, periodic: true }
        },
        {
            id: 'interbank', section: 'currency', family: 'dispatch',
            // internal chartInstances key is 'sbv', not 'interbank'
            chartType: 'sbv', domCardId: 'interbank',
            i18nKey: 'ovInterbank',
            title: 'Lãi suất liên ngân hàng', source: 'SBV', unit: '%/năm', unitKey: 'unitPctYear',
            detailPeriod: '1m',
            mini: { file: 'data/sbv_1m.json', series: 'overnight',
                    scale: 1, decimals: 2, color: '#2f5fde', periodic: true }
        },
        {
            id: 'policy', section: 'currency', family: 'policy',
            // interbank and policy share ONE .chart-card in the DOM (see
            // _tab_data_portal.html) — the interbank chart and the policy stat
            // panel are two blocks inside the same card, not two cards. Detail
            // routing reveals that shared card for either id, then scrolls to
            // scrollAnchor so the policy block is what's in view.
            domCardId: 'interbank', scrollAnchor: 'sbv-policy-anchor',
            i18nKey: 'ovPolicy',
            title: 'Lãi suất điều hành', source: 'NHNN', unit: '%/năm', unitKey: 'unitPctYear',
            detailPeriod: 'all',
            mini: { file: 'data/sbv_policy_all.json', series: 'refinancing',
                    scale: 1, decimals: 2, color: '#16307f', stepped: true }
        },
        {
            id: 'fxrate', section: 'currency', family: 'dispatch',
            chartType: 'fxrate', domCardId: 'fxrate',
            i18nKey: 'ovFxrate',
            title: 'Tỷ giá trung tâm USD/VND', source: 'NHNN', unit: 'VND',
            detailPeriod: '1m',
            // Field is `usd_vnd_rate` in fxrate_SBV_USD_1m.json, not `rates`.
            mini: { file: 'data/fxrate_SBV_USD_1m.json', series: 'usd_vnd_rate',
                    scale: 1, decimals: 0, color: '#2f5fde', periodic: true }
        },
        {
            id: 'global', section: 'global', family: 'dispatch',
            chartType: 'global', domCardId: 'global',
            i18nKey: 'ovGlobal',
            title: 'Vàng thế giới', source: 'Yahoo Finance', unit: '$/oz',
            detailPeriod: '1y',
            mini: { file: 'data/global_1y.json', series: 'gold_prices',
                    scale: 1, decimals: 1, color: '#2f5fde', periodic: true }
        },
        {
            id: 'cpi', section: 'macro', family: 'macro', domCardId: 'cpi',
            i18nKey: 'ovCpi',
            title: 'CPI Việt Nam', source: 'GSO', sourceFull: 'Tổng cục Thống kê — www.nso.gov.vn', unit: '%/năm', unitKey: 'unitPctYear',
            // Detail view opens on the monthly toggle (years=1 in loadMacroCharts,
            // wired to the "Tháng" filter button) rather than the 20-year annual
            // default every other macro chart uses — CPI's own reporting cadence
            // is monthly, so that is the more informative first view.
            detailPeriod: '1',
            // cpi_monthly.json is a bare array of {period, mom_pct, yoy_pct} records —
            // not the {dates:[…], <series>:[…]} shape every other file uses. `period`
            // here is "YYYY-MM". `limit: 12` keeps the glanceable tile to the last
            // year; the detail chart still offers the full Tháng/Năm toggle.
            mini: { file: 'data/cpi_monthly.json', recordsMode: true,
                    dateField: 'period', series: 'yoy_pct', limit: 12,
                    scale: 1, decimals: 2, color: '#FFA726' }
        },
        {
            id: 'gdp', section: 'macro', family: 'macro', domCardId: 'gdp',
            i18nKey: 'ovGdp',
            title: 'Tăng trưởng GDP', source: 'GSO', sourceFull: 'Tổng cục Thống kê — www.nso.gov.vn', unit: '%YoY/quý', unitKey: 'unitPctYear',
            detailPeriod: '20',
            // Static file gdp_quarterly.json exists (like CPI) but `live: 'gdp'`
            // still routes through window.loadGdpSeries() rather than a plain
            // `file:` entry — that function already tries the static file first
            // and falls back to the live API, and reusing it here means the
            // overview tile and the full detail view share the SAME cache
            // (opening the detail after the tile doesn't re-fetch).
            mini: { live: 'gdp', decimals: 2, color: '#26A69A' }
        },
        {
            id: 'trade', section: 'macro', family: 'macro', domCardId: 'trade',
            i18nKey: 'ovTrade',
            title: 'Cán cân thương mại', source: 'GSO', sourceFull: 'Tổng cục Thống kê — www.nso.gov.vn', unit: 'tỷ USD',
            detailPeriod: '20',
            // trade_monthly.json is a bare array of {period, export_billion_usd,
            // import_billion_usd, trade_balance, …} records, period = "YYYY-MM".
            // Mini-tile plots trade_balance (dương = xuất siêu, âm = nhập siêu) —
            // the single figure that summarizes the pair; the detail chart draws
            // exports/imports/balance as three separate lines.
            mini: { file: 'data/trade_monthly.json', recordsMode: true,
                    dateField: 'period', series: 'trade_balance', limit: 24,
                    scale: 1, decimals: 1, color: '#26A69A' }
        },
        {
            id: 'vnindex', section: 'stock', family: 'stock', domCardId: 'vnindex',
            i18nKey: 'ovVnindex',
            title: 'VN-Index', source: 'HSX', unit: 'điểm', unitKey: 'unitPoint',
            detailPeriod: '1y',
            mini: { file: 'data/vnindex_1y.json', series: 'close',
                    scale: 1, decimals: 2, color: '#2f5fde', periodic: true }
        }
    ];

    const SECTIONS = [
        { key: 'gold-silver', i18nKey: 'ovSecGoldSilver', label: 'Vàng & Bạc',          icon: 'fa-coins' },
        { key: 'currency', i18nKey: 'ovSecCurrency',    label: 'Tiền tệ VN',          icon: 'fa-landmark' },
        { key: 'global', i18nKey: 'ovSecGlobal',      label: 'Thị trường quốc tế',  icon: 'fa-globe' },
        { key: 'macro', i18nKey: 'ovSecMacro',       label: 'Vĩ mô',               icon: 'fa-chart-area' },
        { key: 'stock', i18nKey: 'ovSecStock',       label: 'Chứng khoán',         icon: 'fa-chart-line' }
    ];

    const byId = id => CHART_REGISTRY.find(c => c.id === id) || null;

    /* Borrowed from app.js rather than reimplemented — see the header note. */
    const fmtNum = v => (window.formatNumVi ? window.formatNumVi(v) : String(v));

    /* Translation lookup shared with app.js's dictionary (window.i18nText). This
       module BUILDS its markup, so every label here must go through it — text
       written straight into a template string cannot be reached by the
       [data-i18n] sweep and silently stays Vietnamese in EN mode. */
    const T = (key, fallback) => (window.i18nText ? window.i18nText(key, fallback) : fallback);
    const fmtPct = v => (window.formatPctVi ? window.formatPctVi(v) : String(v));

    const miniCharts = {};   // id -> Chart instance (overview only)
    const dataCache  = {};   // file path -> parsed payload

    /* ── Per-section period switching ──────────────────────────────────────────
       The reference layout puts a "7 ngày ⌄" selector beside each section
       heading. It is offered only for sections where EVERY chart is
       `periodic` — i.e. its static file is one of a {7d,1m,1y} set whose name
       ends in the period. CPI (annual records), GDP (live) and the SBV policy
       history (single all-time file) have no such variants, so the macro and
       currency sections show no selector rather than a control that silently
       does nothing to some of their tiles. */
    const PERIODS = [
        { key: '7d', label: '7 ngày',  i18nKey: 'period7d' },
        { key: '1m', label: '1 tháng', i18nKey: 'period1m' },
        { key: '1y', label: '1 năm',   i18nKey: 'period1y' }
    ];
    const sectionPeriod = {};   // section key -> period key

    const isPeriodic = c => !!(c.mini && c.mini.periodic);
    const sectionIsPeriodic = key =>
        CHART_REGISTRY.filter(c => c.section === key).every(isPeriodic);

    /* 'data/gold_DOJI_HN_1m.json' + '7d' -> 'data/gold_DOJI_HN_7d.json' */
    function fileForPeriod(chart, period) {
        if (!isPeriodic(chart) || !period) return chart.mini.file;
        return chart.mini.file.replace(/_(7d|1m|1y)\.json$/, `_${period}.json`);
    }

    /* mini.live -> loader returning [{date, value}, …] directly, already sorted
       ascending. Currently only GDP; window.loadGdpSeries is exported by app.js
       and shares its cache with the full detail view (see app.js comment). */
    const LIVE_LOADERS = {
        gdp: async () => {
            if (typeof window.loadGdpSeries !== 'function') {
                throw new Error('loadGdpSeries not loaded yet');
            }
            // [{year, quarter, sector, growth_yoy_pct}, …] — source:
            // vn_gso_gdp_quarterly (nso.gov.vn). Only 'total' plotted here;
            // quarter mapped to its end month so date-fns parses it correctly.
            const raw = await window.loadGdpSeries();
            const qEndMonth = { 1: '03', 2: '06', 3: '09', 4: '12' };
            return raw
                .filter(d => d.sector === 'total' && d.growth_yoy_pct != null)
                .sort((a, b) => a.year - b.year || a.quarter - b.quarter)
                .map(d => ({ date: `${d.year}-${qEndMonth[d.quarter]}-01`, value: d.growth_yoy_pct }));
        }
    };

    /* Some sources give year-only strings ("2002"). Chart.js's date-fns adapter
       parses those inconsistently across browsers, so pin them to Jan 1. Full
       ISO dates ("2026-08-17") pass through untouched. */
    function normalizeDate(raw) {
        const s = String(raw);
        return /^\d{4}$/.test(s) ? `${s}-01-01` : s;
    }

    /* ── Data ──────────────────────────────────────────────────────────────── */

    async function loadStatic(file) {
        if (dataCache[file]) return dataCache[file];
        const res = await fetch('./' + file);
        if (!res.ok) throw new Error('HTTP ' + res.status);
        const json = await res.json();
        // generate_static_data.py wraps everything as {generated_at, data}.
        dataCache[file] = json.data || json;
        return dataCache[file];
    }

    /* Static JSON in fe/data/ comes in two incompatible shapes:
       - {dates:[…], <series>:[…]} — gold, silver, termdepo, interbank, policy,
         fxrate, global, vnindex. Two parallel arrays, index-aligned.
       - a bare array of records, e.g. cpi_annual.json:
         [{period:"2002", yoy_pct:4.04, months:1}, …]. Set `recordsMode: true`
         and `dateField` in the registry entry for this shape.
       GDP has neither — see loadGdpSeries in renderTile. */
    function extractSeries(payload, cfg) {
        let pairs = [];
        if (cfg.recordsMode) {
            if (!Array.isArray(payload)) return null;
            for (const rec of payload) {
                const v = rec[cfg.series];
                if (v === null || v === undefined) continue;
                pairs.push({ date: normalizeDate(rec[cfg.dateField]), value: v / (cfg.scale || 1) });
            }
            // Overview tile shows a recent window, not the whole file — cpi_monthly.json
            // carries 24 months so the default landing view isn't scanning two years at a
            // glance. The full-size detail chart is unaffected; it reads its own files.
            if (cfg.limit) pairs = pairs.slice(-cfg.limit);
        } else {
            const dates = payload.dates || [];
            const values = payload[cfg.series];
            if (!Array.isArray(values)) return null;
            for (let i = 0; i < dates.length; i++) {
                const v = values[i];
                if (v === null || v === undefined) continue;
                pairs.push({ date: dates[i], value: v / (cfg.scale || 1) });
            }
        }
        return pairs.length ? pairs : null;
    }

    /* ── Tile rendering ────────────────────────────────────────────────────── */

    function tileMarkup(chart) {
        // Title and source are real text, not canvas-only: they are the ten
        // indicator names Google reads on the landing view.
        // Starts `is-loading` (DESIGN.md §11.13 skeleton) — setTileState()
        // removes it the moment data arrives or fails, whichever is first.
        return `
            <button class="ov-tile is-loading" data-chart-id="${chart.id}" type="button"
                    aria-label="${T('ovOpen', 'Mở')} ${T(chart.i18nKey, chart.title)}">
              <span class="ov-tile-head">
                <span class="ov-tile-title" data-i18n="${chart.i18nKey}">${T(chart.i18nKey, chart.title)}</span>
                <span class="ov-tile-src" title="${chart.sourceFull || chart.source}">${chart.source}</span>
              </span>
              <span class="ov-tile-value" data-role="value">—</span>
              <span class="ov-tile-delta" data-role="delta"></span>
              <span class="ov-tile-canvas"><canvas id="ovc-${chart.id}"></canvas></span>
              <span class="ov-tile-msg" data-role="msg" hidden></span>
            </button>`;
    }

    function buildGrid(root) {
        root.innerHTML = SECTIONS.map(sec => {
            const charts = CHART_REGISTRY.filter(c => c.section === sec.key);
            const tiles = charts.map(tileMarkup).join('');
            let picker = '';
            if (sectionIsPeriodic(sec.key)) {
                // Seed from the period the section's own default file already
                // uses, so the highlighted button matches what is drawn.
                if (!sectionPeriod[sec.key]) {
                    const m = /_(7d|1m|1y)\.json$/.exec(charts[0].mini.file);
                    sectionPeriod[sec.key] = m ? m[1] : '1m';
                }
                picker = `<span class="ov-period" data-section="${sec.key}">` +
                    PERIODS.map(p =>
                        `<button type="button" class="ov-period-btn${
                            p.key === sectionPeriod[sec.key] ? ' is-active' : ''
                        }" data-period="${p.key}" data-i18n="${p.i18nKey}"` +
                        `>${T(p.i18nKey, p.label)}</button>`).join('') +
                    `</span>`;
            }
            return `
              <div class="ov-section-head">
                <h2 class="chart-section-heading ov-heading">
                  <i class="fas ${sec.icon}"></i><span data-i18n="${sec.i18nKey}">${T(sec.i18nKey, sec.label)}</span>
                </h2>
                ${picker}
              </div>
              <div class="ov-grid">${tiles}</div>`;
        }).join('');

        root.querySelectorAll('.ov-period-btn').forEach(btn => {
            btn.addEventListener('click', ev => {
                // Tiles are <button>s that route to the detail view; this control
                // sits outside them, but stop propagation anyway so a future
                // wrapper cannot turn a period change into a navigation.
                ev.stopPropagation();
                const wrap = btn.closest('.ov-period');
                const sec = wrap.dataset.section;
                const period = btn.dataset.period;
                if (sectionPeriod[sec] === period) return;
                sectionPeriod[sec] = period;
                wrap.querySelectorAll('.ov-period-btn').forEach(b =>
                    b.classList.toggle('is-active', b === btn));
                // Redraw just this section: destroy its instances so renderTile's
                // "already drawn" guard lets them through again.
                CHART_REGISTRY.filter(c => c.section === sec).forEach(c => {
                    if (miniCharts[c.id]) { miniCharts[c.id].destroy(); delete miniCharts[c.id]; }
                    renderTile(c);
                });
            });
        });
    }

    function setTileState(tileEl, { value, delta, pct, unit, unitKey, msg }) {
        // Skeleton is over the moment there is an outcome, success or failure —
        // never wait past that (DESIGN.md §11.13: skeleton for at most 800ms).
        tileEl.classList.remove('is-loading');
        const valEl = tileEl.querySelector('[data-role="value"]');
        const dltEl = tileEl.querySelector('[data-role="delta"]');
        const msgEl = tileEl.querySelector('[data-role="msg"]');
        const canvasWrap = tileEl.querySelector('.ov-tile-canvas');
        if (msg) {
            // The whole tile is a <button> already (it navigates to the detail
            // view), so a SEPARATE retry button here would be an invalid nested
            // <button>. The detail view's own chart already has a working "Thử
            // lại" button (showChartError in app.js) — word this so the existing
            // click-to-navigate affordance doubles as the retry path.
            msgEl.textContent = msg + T('ovTileErrorHint', ' — nhấn để xem chi tiết');
            msgEl.hidden = false;
            if (canvasWrap) canvasWrap.hidden = true;
            return;
        }
        msgEl.hidden = true;
        if (canvasWrap) canvasWrap.hidden = false;
        // data-i18n on the unit so switching language after load re-translates it —
        // the tile is not rebuilt on toggle, only swept.
        valEl.innerHTML = unitKey
            ? `${value}<small data-i18n="${unitKey}">${unit}</small>`
            : `${value}<small>${unit}</small>`;
        if (pct === null || pct === undefined) {
            dltEl.textContent = '';
            return;
        }
        const sign = delta >= 0 ? '+' : '−';
        dltEl.textContent = `${sign}${fmtPct(Math.abs(pct))}%`;
        dltEl.className = 'ov-tile-delta ' +
            (pct > 0 ? 'is-up' : pct < 0 ? 'is-down' : 'is-flat');
    }

    async function renderTile(chart) {
        const tileEl = document.querySelector(`.ov-tile[data-chart-id="${chart.id}"]`);
        if (!tileEl || miniCharts[chart.id]) return;

        let pairs;
        try {
            if (chart.mini.live) {
                const loader = LIVE_LOADERS[chart.mini.live];
                if (!loader) throw new Error(`no live loader for "${chart.mini.live}"`);
                pairs = await loader();
            } else {
                const file = fileForPeriod(chart, sectionPeriod[chart.section]);
                pairs = extractSeries(await loadStatic(file), chart.mini);
            }
            if (!pairs || !pairs.length) throw new Error('empty series');
        } catch (e) {
            console.warn(`[overview] ${chart.id}:`, e.message);
            // One dead source must not blank the grid.
            setTileState(tileEl, { msg: T('ovTileError', 'Không tải được dữ liệu') });
            return;
        }

        const last  = pairs[pairs.length - 1].value;
        const first = pairs[0].value;
        const delta = last - first;
        const pct   = first ? (delta / first) * 100 : null;
        const d = chart.mini.decimals;
        setTileState(tileEl, {
            value: last.toLocaleString('vi-VN',
                { minimumFractionDigits: d, maximumFractionDigits: d }),
            delta, pct, unit: T(chart.unitKey, chart.unit), unitKey: chart.unitKey
        });

        const canvas = tileEl.querySelector('canvas');
        if (!canvas || !window.Chart) return;
        const ctx2d = canvas.getContext('2d');

        /* Soft gradient under the line, as the approved reference shows.
           Note CLAUDE.md's chart-honesty rule: an area fill implies magnitude
           measured from ZERO, so the full-size gold / USD-VND / VN-Index charts
           deliberately keep fill:false (they start at 135 triệu, 25.000₫, …).
           That rule is about the detail charts and is left intact. These minis
           are the glanceable tier — same role as the KPI ticker sparklines
           above them, which have always been filled — and use `fill: 'start'`,
           which fills to the bottom of the drawn area rather than asserting a
           zero baseline. */
        const gradH = canvas.clientHeight || 195;
        const grad = ctx2d.createLinearGradient(0, 0, 0, gradH);
        grad.addColorStop(0, chart.mini.color + '30');
        grad.addColorStop(1, chart.mini.color + '00');

        miniCharts[chart.id] = new window.Chart(ctx2d, {
            type: 'line',
            data: {
                labels: pairs.map(p => p.date),
                datasets: [{
                    data: pairs.map(p => p.value),
                    borderColor: chart.mini.color,
                    backgroundColor: grad,
                    fill: 'start',
                    borderWidth: 1.8,
                    tension: chart.mini.stepped ? 0 : 0.35,
                    stepped: chart.mini.stepped ? 'before' : false,
                    pointRadius: 0,
                    pointHoverRadius: 3
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                // The mini variant drops legend, axis titles, period buttons and
                // the CSV button. It keeps the axes — that is the whole point of
                // a mini CHART rather than a sparkline: it answers "from what
                // level to what level", not just "which way".
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        mode: 'index', intersect: false,
                        callbacks: {
                            label: ctx => `${fmtNum(ctx.parsed.y)} ${chart.unit}`
                        }
                    }
                },
                scales: {
                    x: {
                        // unit:'month' printed a single "Aug 2026" tick for a
                        // one-month window, so the axis carried no readable
                        // information. Day unit + dd/MM matches the reference.
                        type: 'time',
                        time: { unit: 'day', tooltipFormat: 'dd/MM/yyyy',
                                displayFormats: { day: 'dd/MM' } },
                        ticks: { color: '#87867f', font: { size: 9 },
                                 maxRotation: 0, autoSkip: true, maxTicksLimit: 5 },
                        grid: { display: false }
                    },
                    y: {
                        ticks: { color: '#87867f', font: { size: 9 },
                                 maxTicksLimit: 3, callback: v => fmtNum(v) },
                        grid: { display: false }
                    }
                }
            }
        });
    }

    /* ── Lazy init ─────────────────────────────────────────────────────────── */

    let observer = null;

    function observeTiles() {
        if (observer) observer.disconnect();
        // Ten Chart.js instances is the main cost of this page. rootMargin gives
        // each tile a head start so the chart is there before it is looked at,
        // while a first paint only builds the ~6 tiles actually near the viewport.
        observer = new IntersectionObserver(entries => {
            entries.forEach(entry => {
                if (!entry.isIntersecting) return;
                const id = entry.target.dataset.chartId;
                observer.unobserve(entry.target);
                const chart = byId(id);
                if (chart) renderTile(chart);
            });
        }, { rootMargin: '200px' });

        document.querySelectorAll('.ov-tile').forEach(el => observer.observe(el));
    }

    function destroyMiniCharts() {
        Object.keys(miniCharts).forEach(id => {
            try { miniCharts[id].destroy(); } catch (e) { /* already gone */ }
            delete miniCharts[id];
        });
        if (observer) { observer.disconnect(); observer = null; }
    }

    /* ── Public API ────────────────────────────────────────────────────────── */

    window.VDOverview = {
        REGISTRY: CHART_REGISTRY,
        SECTIONS,
        byId,
        mount(root) {
            if (!root) return;
            if (!root.dataset.built) {
                buildGrid(root);
                root.dataset.built = '1';
            }
            observeTiles();
        },
        unmount: destroyMiniCharts,
        // Exposed for the routing layer in app.js.
        firstChartOfSection(sectionKey) {
            const c = CHART_REGISTRY.find(x => x.section === sectionKey);
            return c ? c.id : null;
        }
    };
})();
