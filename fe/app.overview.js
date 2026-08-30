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
            title: 'Giá vàng trong nước', source: 'DOJI HN', unit: 'triệu/lượng',
            detailPeriod: '1m',
            mini: { file: 'data/gold_DOJI_HN_1m.json', series: 'buy_prices',
                    scale: 1e6, decimals: 1, color: '#2f5fde', periodic: true }
        },
        {
            id: 'silver', section: 'gold-silver', family: 'dispatch',
            chartType: 'silver', domCardId: 'silver',
            title: 'Giá bạc trong nước', source: 'Phú Quý', unit: 'triệu/lượng',
            detailPeriod: '1m',
            mini: { file: 'data/silver_1m.json', series: 'buy_prices',
                    scale: 1e6, decimals: 2, color: '#4d4c48', periodic: true }
        },
        {
            id: 'termdepo', section: 'currency', family: 'dispatch',
            // internal chartInstances key is 'td', not 'termdepo'
            chartType: 'td', domCardId: 'termdepo',
            title: 'Lãi suất gửi tiết kiệm', source: 'ACB', unit: '%/năm',
            detailPeriod: '1y',
            mini: { file: 'data/termdepo_ACB_1y.json', series: 'term_12m',
                    scale: 1, decimals: 2, color: '#1e3fae', stepped: false, periodic: true }
        },
        {
            id: 'interbank', section: 'currency', family: 'dispatch',
            // internal chartInstances key is 'sbv', not 'interbank'
            chartType: 'sbv', domCardId: 'interbank',
            title: 'Lãi suất liên ngân hàng', source: 'SBV', unit: '%/năm',
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
            title: 'Lãi suất điều hành', source: 'NHNN', unit: '%/năm',
            detailPeriod: 'all',
            mini: { file: 'data/sbv_policy_all.json', series: 'refinancing',
                    scale: 1, decimals: 2, color: '#16307f', stepped: true }
        },
        {
            id: 'fxrate', section: 'currency', family: 'dispatch',
            chartType: 'fxrate', domCardId: 'fxrate',
            title: 'Tỷ giá trung tâm USD/VND', source: 'NHNN', unit: 'VND',
            detailPeriod: '1m',
            // Field is `usd_vnd_rate` in fxrate_SBV_USD_1m.json, not `rates`.
            mini: { file: 'data/fxrate_SBV_USD_1m.json', series: 'usd_vnd_rate',
                    scale: 1, decimals: 0, color: '#2f5fde', periodic: true }
        },
        {
            id: 'global', section: 'global', family: 'dispatch',
            chartType: 'global', domCardId: 'global',
            title: 'Vàng thế giới', source: 'Yahoo Finance', unit: '$/oz',
            detailPeriod: '1y',
            mini: { file: 'data/global_1y.json', series: 'gold_prices',
                    scale: 1, decimals: 1, color: '#2f5fde', periodic: true }
        },
        {
            id: 'cpi', section: 'macro', family: 'macro', domCardId: 'cpi',
            title: 'CPI Việt Nam', source: 'GSO', unit: '%/năm',
            detailPeriod: '20',
            // cpi_annual.json is a bare array of {period, yoy_pct, months} records —
            // not the {dates:[…], <series>:[…]} shape every other file uses.
            // `period` here is a year string ("2002"), not a full ISO date.
            mini: { file: 'data/cpi_annual.json', recordsMode: true,
                    dateField: 'period', series: 'yoy_pct',
                    scale: 1, decimals: 2, color: '#FFA726' }
        },
        {
            id: 'gdp', section: 'macro', family: 'macro', domCardId: 'gdp',
            title: 'Tăng trưởng GDP', source: 'World Bank', unit: '%/năm',
            detailPeriod: '20',
            // No static file exists for GDP (unlike CPI/gold/silver/…) — the full
            // detail view fetches it live from the World Bank API. `live: 'gdp'`
            // routes through window.loadGdpSeries(), a thin export added in
            // app.js that shares the SAME cache the detail view uses.
            mini: { live: 'gdp', decimals: 2, color: '#26A69A' }
        },
        {
            id: 'vnindex', section: 'stock', family: 'stock', domCardId: 'vnindex',
            title: 'VN-Index', source: 'HSX', unit: 'điểm',
            detailPeriod: '1y',
            mini: { file: 'data/vnindex_1y.json', series: 'close',
                    scale: 1, decimals: 2, color: '#2f5fde', periodic: true }
        }
    ];

    const SECTIONS = [
        { key: 'gold-silver', label: 'Vàng & Bạc',          icon: 'fa-coins' },
        { key: 'currency',    label: 'Tiền tệ VN',          icon: 'fa-landmark' },
        { key: 'global',      label: 'Thị trường quốc tế',  icon: 'fa-globe' },
        { key: 'macro',       label: 'Vĩ mô',               icon: 'fa-chart-area' },
        { key: 'stock',       label: 'Chứng khoán',         icon: 'fa-chart-line' }
    ];

    const byId = id => CHART_REGISTRY.find(c => c.id === id) || null;

    /* Borrowed from app.js rather than reimplemented — see the header note. */
    const fmtNum = v => (window.formatNumVi ? window.formatNumVi(v) : String(v));
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
        { key: '7d', label: '7 ngày' },
        { key: '1m', label: '1 tháng' },
        { key: '1y', label: '1 năm' }
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
            const raw = await window.loadGdpSeries(); // [{date, value}, …]
            return raw.map(d => ({ date: normalizeDate(d.date), value: d.value }));
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
                    aria-label="Mở ${chart.title}">
              <span class="ov-tile-head">
                <span class="ov-tile-title">${chart.title}</span>
                <span class="ov-tile-src">${chart.source}</span>
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
                        }" data-period="${p.key}">${p.label}</button>`).join('') +
                    `</span>`;
            }
            return `
              <div class="ov-section-head">
                <h2 class="chart-section-heading ov-heading">
                  <i class="fas ${sec.icon}"></i><span>${sec.label}</span>
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

    function setTileState(tileEl, { value, delta, pct, unit, msg }) {
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
            msgEl.textContent = msg + ' — nhấn để xem chi tiết';
            msgEl.hidden = false;
            if (canvasWrap) canvasWrap.hidden = true;
            return;
        }
        msgEl.hidden = true;
        if (canvasWrap) canvasWrap.hidden = false;
        valEl.innerHTML = `${value}<small>${unit}</small>`;
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
            setTileState(tileEl, { msg: 'Không tải được dữ liệu' });
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
            delta, pct, unit: chart.unit
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
