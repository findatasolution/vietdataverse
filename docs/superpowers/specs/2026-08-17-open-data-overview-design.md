# Open Data Overview — design

Status: approved 2026-08-17. Supersedes nothing; extends the existing Open Data workspace.

**Implemented 2026-08-27** (desktop + mobile CSS together, per the phasing
decision below). Code: `fe/app.overview.js`, routing in `fe/app.js` next to
the hash-parsing block, grid/tile/detail CSS in `fe/style.css`, structural
checks in `fe/check_overview.py`. Verified: JS syntax, every registry entry
against its real static-file shape, DOM tag consistency, HTTP 200 on all new
assets. **Not yet verified: actual Chart.js rendering, click-through routing,
and mobile at a real viewport width — this environment has no browser.** See
the handoff message for the exact manual QA checklist.

## Problem

`#data/portal` renders five sections stacked vertically with ten full-width charts.
A visitor lands on a hero plus one chart and has no idea the other nine exist —
the page gives no overview of what the platform actually covers. The request: a
first screen that covers every indicator, where clicking a chart expands it.

## Decisions

| Question | Decision | Why |
|---|---|---|
| Density | Grid of real mini-charts (~130px, with axes), 3 columns, ~2 screens tall | A 40px sparkline answers "which way" but not "from what level to what level". Level is the reason the policy-rate panel felt empty as bare numbers. |
| Grouping | Grouped under the existing 5 section headings | Keeps the taxonomy users already navigate by. Costs ~34px per heading. |
| Expand | Navigate to a per-chart detail route | `DESIGN.md` §11.9: "không dùng modal cho detail — push navigate full page". Also gives every chart a shareable URL. |
| Detail granularity | One chart, full size, with ‹ › to move within its section | Matches the "phóng to" metaphor. Section-level detail would drop the clicked chart among three others. |
| Page header | Hero compacted: keep `<h1>` + both CTAs, shorten the lead to one line, reduce vertical padding. KPI strip kept as one row | Preserves the `<h1>` and lead text for SEO and the API entry point while letting the grid reach above the fold. |
| Implementation | Chart registry + two render variants, in a new `fe/app.overview.js` | Avoids moving canvas DOM nodes (Chart.js binds to the element). Follows the `app.knowledge.js` precedent; `app.js` is already ~3,600 lines. |

## Routes

| Route | State | Renders |
|---|---|---|
| `#data/portal` | Overview (default landing) | Compact hero, KPI strip, grouped grid of 10 mini-charts |
| `#data/portal/chart/<id>` | Detail | One chart at full size: title, period controls, CSV button, source, ‹ › within section |
| `#data/portal/<section>` | Legacy | Redirects to the first chart of that section |

The legacy form stays because `LEGACY_HASH_MAP` maps `tab-gold-silver` →
`data/portal/gold-silver`; removing it breaks existing bookmarks. `DESIGN.md`
§12.6 already prescribes keeping a legacy hash shim for one release.

Sidebar clicks use `replaceState`, workspace tab clicks use `pushState` — the
existing convention in §12.6. Tile clicks are navigation, so they `pushState`;
browser Back returns to the overview with scroll position restored.

## Chart registry

One declaration per chart, in `fe/app.overview.js`. This is the single source of
truth for the grid, the detail view and ‹ › ordering.

```js
{ id, section, title, canvas, family, defaultPeriod, source }
```

Ten entries, in display order:

| id | section | family | default period |
|---|---|---|---|
| `gold` | gold-silver | dispatch | 1m |
| `silver` | gold-silver | dispatch | 1m |
| `termdepo` | currency | dispatch | 1y |
| `interbank` | currency | dispatch | 1m |
| `policy` | currency | policy | all |
| `fxrate` | currency | dispatch | 1m |
| `global` | global | dispatch | 1y |
| `cpi` | macro | macro | 20 |
| `gdp` | macro | macro | 20 |
| `vnindex` | stock | stock | 1y |

`family` exists because the current code has four unrelated loading paths. The
value is used to pick which existing loader to call:

- `dispatch` (gold, silver, termdepo, interbank, fxrate, global) — `loadChartData(type, period)` → `renderChart()`
- `policy` (policy) — `loadPolicyRates()` → `renderPolicyRates()`
- `macro` (cpi, gdp) — `renderCpi()` / `renderGdp()`, driven by a shared year selector
- `stock` (vnindex) — `loadVnindexChart(period)` → `renderVnindex()`

**These three families are not unified.** Unifying them is a separate refactor
with its own risk, and it does not serve this feature. The registry adapts to
them instead.

## Overview layout

Grid: 3 columns ≥1200px, 2 columns 768–1199px, 1 column <768px. Gap 20px.
Section headings reuse the existing `.chart-section-heading` (serif 1.5rem).

Tile anatomy, top to bottom:

```
┌─────────────────────────────────┐
│ Lãi suất tiết kiệm       ACB    │  title 13px / source 11px stone
│ 5,30 %/năm                      │  value 20px weight 600
│ +0,00%                          │  delta 12px, coral/crimson/stone
│ ┌─────────────────────────────┐ │
│ │ 5,5%│                       │ │  mini chart, 130px tall
│ │   4%│      ┌────────        │ │  y axis: 3 ticks
│ │ 2,5%│──────┘                │ │  x axis: 3 date marks
│ │     └───────────────────    │ │  no legend, no axis titles,
│ └─────────────────────────────┘ │  no period buttons, no CSV
└─────────────────────────────────┘
```

The whole tile is one click target. Hover: ring shadow `0 0 0 2px #d1cfc5` plus
`translateY(-2px)`, 180ms — never `scale()`, per `DESIGN.md` §11.12.

Mini variant drops legend, axis titles, period controls and the CSV button; keeps
the series colours, the stepped/tension settings and the number formatters
(`formatVndAxis`, `formatNumVi`, `formatPctVi`) so mini and full cannot disagree.

## Detail layout

```
← Tổng quan          Tiền tệ VN          ‹ 2/4 ›
─────────────────────────────────────────────────
Lịch sử lãi suất gửi tiết kiệm (NHTM)  ⓘ
                        [ACB] [1 năm] [Tất cả] [⤓]
   <full chart, unchanged from today>
Nguồn: acb.com.vn
```

The chart card itself is exactly what renders today — same markup, same controls,
same behaviour. Only its container and the surrounding nav are new.

## Data flow and performance

Ten Chart.js instances is the main cost. Mitigations:

1. **Lazy init by visibility.** An `IntersectionObserver` with `rootMargin: 200px`
   builds each mini chart just before it scrolls into view. On a 3-column grid
   only ~6 exist at first paint.
2. **Reuse the existing prefetch.** `window._prefetchPromises` already holds
   static JSON for gold, silver, fxrate, termdepo and interbank before
   `DOMContentLoaded`. The mini charts consume the same promises — no extra
   requests for five of ten tiles.
3. **Cache per chart id.** Data fetched for a mini chart is reused by the detail
   view at the same period, so clicking a tile does not refetch.
4. **One instance per chart at a time.** Leaving the overview destroys every mini
   instance; leaving the detail destroys the full one. Each chart has two canvas
   elements but never two live Chart objects.

## Error and empty states

- **A tile's data fails to load** — that tile alone shows "Không tải được dữ liệu"
  plus a retry link, in the tile's own body. One dead source must not blank the grid.
- **Loading** — skeleton matching the tile anatomy (title bar, value bar, chart
  block), per `DESIGN.md` §11.13. Skeleton for at most 800ms, then the inline error.
- **Unknown chart id in the URL** — fall back to the overview rather than a blank view.
- **Stale data** — the tile reuses the existing staleness wording ("Cập nhật hôm
  nay / hôm qua / Dữ liệu N ngày trước"), so the overview surfaces stale sources
  the same way the KPI strip already does.

## SEO

Today all five sections are in the DOM and visible. After this change the detail
sections are hidden until routed to. Hidden text is still indexed but carries less
weight, so:

- The `<h1>` and the compact hero lead stay in the overview.
- Each tile renders its chart title as real text (not canvas-only), so the ten
  indicator names remain crawlable on the landing view.
- Section headings stay as real `<h2>` elements in the overview grid.
- `<title>`, `og:`, `twitter:` and JSON-LD are untouched.

## Phasing

**Desktop and mobile ship together** (decided 2026-08-17, after the SEO audit).
Google indexes the mobile rendering, so shipping a desktop-only overview would
mean the version Google sees is the one nobody has checked. Build desktop first,
then mobile, then release both.

**Desktop** — everything in this spec at ≥768px.

**Mobile** — same feature at <768px, in the same release:

- Grid collapses to one column; tiles keep the same anatomy but the chart drops
  to ~110px and the y axis to 2 ticks.
- Detail view: ‹ › becomes a sticky bottom bar (`DESIGN.md` §11.9 mobile note).
- `DESIGN.md` §13.9 forbids horizontal scroll anywhere — verify at ≤640px.
- Phase 2 also covers the earlier layout work (section headings, KPI strip,
  policy filters, footer grid, index-100 axis title), none of which has been
  checked at that width yet.

Splitting this way keeps one variable moving at a time: if something breaks at
≤640px we know whether it came from the overview or from the earlier pass.

## Out of scope

- Unifying the three chart-loading families.
- The orphaned `renderTrade()` / `#macroTradeChart` (canvas no longer exists in
  the partial — dead code, flagged, not removed here).
- Backfilling VN-Index history before 2026-04-16.
- Changing any chart's own rendering, colours or periods.

## Acceptance

1. `#data/portal` shows 10 tiles under 5 headings; every tile has a value, a delta
   and a chart with visible axes.
2. Clicking any tile lands on `#data/portal/chart/<id>` showing that chart alone,
   full size, with its period controls working.
3. ‹ › moves within the section and stops at the ends; Back returns to the overview.
4. An old `#data/portal/currency` URL still resolves (to `termdepo`).
5. Killing one static JSON file degrades only that tile.
6. No chart is rendered twice; `chartInstances` holds at most one object per id.
