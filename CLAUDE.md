# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Communication

Trao đổi với người dùng (chat, giải thích, tóm tắt) bằng tiếng Việt. Code, comment, commit message vẫn giữ tiếng Anh như chuẩn hiện tại của repo.

## Project Overview

Viet Dataverse — financial data platform for Vietnam macro & corporate data, with a knowledge/skill marketplace for AI agents.

Stack: Python crawlers → PostgreSQL (Neon) → FastAPI (`be/`) → static HTML/Chart.js FE (`fe/`).

Two products in one SPA:
1. **Open Data** — macro/finance/commodity/stock charts, API-key-metered data API + free static downloads. `gold-analysis` and `market-pulse` remain intentionally public.
2. **AI Agent Knowledge & Skill Market** (short: "Agent Market") — paid/free `.md/.json/.yaml` knowledge packs for agent builders, with seller flow, wallet/credits, library.

## Skills

`.claude/skills/` has project-specific skills. **Check for a matching skill before starting non-trivial work — if a skill's `description` plausibly covers the task, invoke it before proceeding with an ad-hoc approach.** Two families exist:

- **`be_1_crawler` → `be_2_data_modeling` → `be_3_data_crawl_execute` → `be_4_data_clean_verify` → `be_5_data_updatedocs`** — generic pipeline for simple single-value time-series crawlers (gold, CPI, interest rates). Chain them in order for a new source of this shape.
- **`financial_statement_extraction`** — for anything involving BCTC line items (balance sheet/B01-DN, income statement/B02-DN, cash flow/B03-DN) from OCR/PDF, or `crawl_tools/crawl_vn30_financials.py`/its replacement. Points to `.claude/knowledge/financial_statements/` (mã kế toán Thông tư 200 KB — mã tài khoản, mã chỉ tiêu B01/B02/B03, 15 quy tắc nghiệp vụ R01-R15, 12 kiểm tra số học V01-V12). **Explicitly excludes consolidated ("hợp nhất") statements and a handful of specialized regimes (banks, insurance, TT133, IFRS)** — see the skill and KB index for the full out-of-scope list; do not apply this KB's line-code mapping to a hợp nhất document.

`.claude/knowledge/` holds reference KBs a skill points into (not duplicated into the skill body). Add new topics as `.claude/knowledge/<topic>/index.md` + leaf files, following the `financial_statements/` example.

## Git Workflow Rules

**KHÔNG tự ý tạo branch.** Mặc định commit thẳng lên `main`. Chỉ tạo branch khi user yêu cầu rõ ràng (hoặc user chọn mở PR) — và hỏi trước nếu không chắc. Trước khi xoá branch/PR: verify trạng thái merge thật (`gh pr view`) rồi mới xoá, không xoá dựa trên giả định.

## Security Rules

**NEVER display secrets in chat or terminal output.** This includes DB connection strings, API keys, passwords, tokens, or any value read from `.env`. Use values programmatically; mask or skip prints that would expose them.

## Documentation Close-out (Required)

Documentation is part of the definition of done. Before marking any task complete:

1. Identify every document affected by the change, including `BACKLOG.md`, `CLAUDE.md`, `CODEX.md`, scoped `fe/CLAUDE.md` / `AGENTS.md`, README/API docs, runbooks, architecture notes, migration notes, and `.env.example` when applicable.
2. Update status, behavior, paths, commands, schemas, access rules, deployment state, and limitations in the same task. Do not leave documentation describing the pre-change behavior.
3. When completing a backlog item, mark it complete only after implementation and required verification succeed. If production deployment is still pending or blocked, document that state explicitly instead of marking it fully complete.
4. Replace stale statements rather than appending contradictory notes. Update source documents, not generated artifacts, then rebuild generated documentation when required.
5. In the final handoff, list the documents updated. If no document needed a content change, explicitly state that the relevant documentation was reviewed and remains accurate.

Do not close a task while related documentation is known to be stale.

## Repository Layout

```
be/                 FastAPI backend
  main.py           App entry, router registration, static mount at /fe
  routers/          One router per domain (market_data, vn30_data, knowledge, wallet, seller, …)
  core/             config, engines, startup, r2 (Cloudflare R2 for KM files)
  services/         credit, auth helpers
  migrations/       SQL files + run_*.py one-shot scripts (Knowledge Market schema)
  knowledge_models.py, models.py   SQLAlchemy models
  payment.py        PayOS + credit_topup webhook
  generate_static_data.py          DB → fe/data/*.json
  1s_market_pulse.py               news pulse generator
fe/                 Static frontend (served by FastAPI at /fe — see note below)
  partials/         8 HTML fragments — source of truth (see fe/CLAUDE.md)
  build.py          Concatenates partials → index.html (stdlib only)
  index.html        AUTO-GENERATED — never edit directly
  app.js            Charts, fetch, workspace/view routing
  app.knowledge.js  Agent Market logic (cards, library, wallet, seller)
  style.css         All FE styles
  auth.js           Auth0 flow
  data/             Static JSON (gold/silver/sbv/termdepo/global), regenerated by CI
  pages/            Standalone pages (api-docs, pricing, account, admin, …)
crawl_tools/        Standalone crawler scripts (one per source/asset)
.github/workflows/  Per-asset crawlers + build-html + generate-static-data + data-quality-check
.claude/rules/
  DESIGN.md         Design system (Claude/Anthropic-inspired warm palette + §11 Marketplace patterns)
```

## Common Commands

```bash
# Frontend: rebuild index.html from partials (after editing fe/partials/*)
python fe/build.py

# Backend: run FastAPI locally
cd be && uvicorn main:app --reload

# Crawler: run a single crawler ad-hoc (loads .env from repo root)
python crawl_tools/api_gold_btmc.py
python crawl_tools/crawl_bank_termdepo.py

# Regenerate static JSON in fe/data/ from DB
python be/generate_static_data.py

# One-shot KM migration
python be/migrations/run_004.py
```

Backend dependencies: `pip install -r be/requirements.txt`. Crawlers: `pip install -r crawl_tools/requirements.txt`. No npm/Node — FE is zero-dep static.

## Database Infrastructure

3 PostgreSQL databases on Neon, env vars loaded by `be/main.py` from `<repo-root>/.env` (not `be/.env`):

| Env Var | Purpose | Key Tables |
|---------|---------|------------|
| `CRAWLING_BOT_DB` | Macro crawl data | `vn_macro_*`, `vn_gso_*` |
| `CRAWLING_CORP_DB` | Corporate/equity data | `vn30_*` |
| `GLOBAL_INDICATOR_DB` | Global macro (Yahoo Finance) | `global_macro` |
| `USER_DB` | Users, payments, KM (sellers, products, wallet, library) | knowledge_* |
| `HELPER_DB` | Internal ops/DQ tables | — |
| `FUEL_FORECAST_DB` | Fuel-forecast product (isolated; B2B, unreleased) | `fuel_price_cycle`, `fuel_world_daily`, `fuel_forecast`, `fuel_backtest` |

### Table naming convention

```
vn_macro_{source}_{asset}_{freq}     vn_gso_{topic}_{freq}
vn30_{topic}_{freq}                  global_{topic}_{freq}
```
Examples: `vn_macro_gold_daily`, `vn_gso_cpi_monthly`, `vn30_ohlcv_daily`.

### Required columns (every crawl table, all NOT NULL)

```sql
id          SERIAL PRIMARY KEY           -- always SERIAL, never MAX(id)+1
period      DATE | VARCHAR(7) NOT NULL   -- YYYY-MM-DD daily / YYYY-MM monthly
crawl_time  TIMESTAMP NOT NULL           -- UTC at crawl time
source      TEXT NOT NULL                -- source URL or org (e.g. "acb.com.vn")
group_name  VARCHAR(20) NOT NULL         -- macro | finance | commodity | stock | sentiment
```

When adding `source`/`group_name` to existing tables: ALTER → UPDATE backfill → then add NOT NULL.

### Data group taxonomy → table prefix

- `vn_gso_*` → macro
- `vn_macro_termdepo_*, vn_macro_sbv_*, vn_macro_fxrate_*` → finance
- `vn_macro_gold_*, vn_macro_silver_*, global_*` → commodity
- `vn30_*` → stock

### Constraints (always add)

```sql
UNIQUE (entity_key, period)   -- dedup: (bank_code/type/ticker, date)
INDEX  (period)
```

## Crawl Pipeline

Each crawler is standalone in `crawl_tools/`:

```python
load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent.parent / '.env')
DB_URL = os.getenv('CRAWLING_BOT_DB')
if not DB_URL: sys.exit("CRAWLING_BOT_DB not set")

data = parse(html)
if not validate(data): sys.exit(1)  # ≥3 valid numeric values in expected range
save(data)
```

Note the **three** `.parent` calls — that resolves to the directory *above* the repo root, not the repo root. All 17 active crawlers (`crawl_gold_silver.py`, `crawl_sbv.py`, `crawl_vn30_*.py`, …) do this; only the one-off `backfill_*.py` scripts use two. In CI it is moot because env comes from workflow `env:` blocks, but it means running a crawler locally from a repo-root `.env` does **not** work — export the vars, or keep an `.env` one level above the checkout.

Store pattern: `INSERT ... ON CONFLICT DO NOTHING|UPDATE`. Never `MAX(id)+1` (use SERIAL). Always `conn.commit()` explicitly (SQLAlchemy 2.x). Validate range + completeness before insert — never write partial rows.

### Active sources

| Asset | Source | Table | Freq |
|-------|--------|-------|------|
| Term Deposit | ACB | `vn_macro_termdepo_daily` | Daily |
| Gold | BTMC, DOJI, SJC, PNJ | `vn_macro_gold_daily` | Daily |
| Silver | Phú Quý | `vn_macro_silver_daily` | Daily |
| FX Rate | VCB, SBV | `vn_macro_sbv_rate_daily` | Daily |
| CPI | NSO | `vn_gso_cpi_monthly` | Monthly |
| GDP / IIP / Xuất nhập khẩu | NSO monthly & quarterly bulletin | `vn_gso_gdp_quarterly`, `vn_gso_iip_monthly`, `vn_gso_trade_monthly` | Monthly / Quarterly |
| Global | Yahoo Finance (GC=F, SI=F, ^IXIC) | `global_macro` | Daily |
| Fuel (domestic) | Bộ Công Thương price-management announcements | `fuel_price_cycle` | ~Biweekly (cadence changed 2026-08, was weekly Thu) |
| Fuel (world) | Yahoo Finance (BZ=F Brent, RB=F RBOB) | `fuel_world_daily` | Daily |
| VN30 (profile/price/financials/ratios) — crawled but **not served anywhere**, internal cross-check only | `vnstock3` (wraps SSI/TCBS) — license restriction, see below | `vn30_*` | Daily/Quarterly |

### VN30 data source (`vnstock3`) — REV-01 gỡ khỏi API/FE hoàn tất (2026-09-10)

`crawl_vn30_price.py`, `crawl_vn30_financials.py`, `crawl_vn30_profile.py`, `crawl_vn30_ratios.py` all source from the `vnstock3` Python library, which wraps SSI/TCBS's internal (not publicly documented) endpoints. **`vnstock3`'s license explicitly prohibits any commercial use, including indirect use — "activities where Vnstock directly or indirectly contributes to generating revenue or cash flow for an organization" — without the author's written consent** ([license](https://github.com/thinh-vu/vnstock/blob/main/LICENSE.md)). Viet Dataverse is a commercial organization, so this applies **even to the free tier** — the restriction is on organizational use, not on whether a specific dataset is sold. The restriction travels with the data's chain of custody (exchange → licensed vendor → any redistributor), not with which field or endpoint serves it — so this covers `vn30_company_profile` (ticker/name/sector/ICB) and `vn_macro_vnindex_daily` (VN-Index) too, not just the price/ratio tables.

**Done 2026-09-10**: `be/routers/vn30_data.py` no longer defines any `/vn30/*` or `/market/vnindex` endpoint — the file now serves only `macro/cpi`, `macro/gdp`, `macro/trade` (GSO-sourced, unrelated to vnstock3). `be/routers/developer.py`'s endpoint catalog, `be/routers/webhooks.py`'s `VALID_EVENTS`, `be/generate_static_data.py` (dropped `generate_vnindex_data()`), and every FE surface that referenced VN30/VN-Index data or endpoints (`app.js`, `app.overview.js`, `fe/partials/_tab_data_portal.html` — including its "Chứng khoán" overview section, now removed since VN-Index was its only chart — `fe/pages/api-docs.html` + its EN i18n data, `fe/pages/account.html` webhook picker, `fe/excel-addin/`, `fe/llms.txt`, `_layout_head.html`'s JSON-LD FAQ) were all updated in the same pass. Open Data overview grid is now 9 tiles / 4 sections (was 10/5) until a clean VN-Index source lands — see `fe/check_overview.py`, whose invariants were updated to match.

**Crawl pipeline is untouched and keeps running** — `crawl_vn30_*.py` + their GitHub Actions workflows still populate `vn30_company_profile` / `vn30_ohlcv_daily` / `vn30_ratio_daily` / `vn30_income_stmt_quarterly` / `vn30_balance_sheet_quarterly` / `vn30_cashflow_quarterly` / `vn_macro_vnindex_daily` in `CRAWLING_CORP_DB` exactly as before — this is the "internal-only, for cross-checking BCTC-derived ROE/ROA/EPS" reference decided 2026-09-08, and removing the public router doesn't touch it. Only the read path (the API/FE) is gone; nothing reads those tables anymore.

**Remaining REV-01 item (not started)**: rebuild `crawl_vn30_financials.py`-equivalent to source BCTC directly from each company's own IR page or the official disclosure portal (HOSE/HNX/SSC) instead of `vnstock3`, and automate it — the `financial_statement_extraction` skill + `listed_company_financials` table already prove this works for 27 companies, but every one of them was extracted **manually**, not by a script. The "email the vnstock author for permission" item that used to sit alongside this was dropped 2026-09-10 — not pursuing that path anymore, going straight for the clean-source rebuild instead.

**VN-Index has no clean replacement source yet** — checked Yahoo Finance (no VN-Index ticker in its coverage) and SSI's iBoard (same kind of broker-platform-ToS problem as vnstock3, not actually safer) on 2026-09-10; neither panned out. See `BACKLOG.md` for the follow-up research item — HOSE's own daily trading-summary disclosure (if it publishes one as a routine public document, parallel to how the BCTC PDF mirror was found) is the most promising untried lead.

See `docs/research/2026-09-08-financial-statements-subscription-plan.md` for the full product plan (personal-tier BCTC subscription) and the complete risk write-up.

### Fuel (domestic) crawl — MOIT re-files bulletins without notice (found + fixed 2026-09-08)

`crawl_tools/crawl_moit_fuel.py`'s `discover_latest()` only ever scraped the
`moit.gov.vn/tin-tuc/thi-truong-trong-nuoc` category page for the newest "điều hành
giá xăng dầu" bulletin link. MOIT stopped listing these bulletins there after
2026-07-09 and started filing them under `phat-trien-nang-luong` instead (the
article URL pattern itself — `mot-so-thong-tin-ve-viec-dieu-hanh-gia-xang-dau-ngay-D-M-YYYY.html`
— never changed, only which category page links it). Because the crawler is
idempotent (`ON CONFLICT DO UPDATE`) and never checked whether the discovered cycle
was actually newer than what's already stored, it re-upserted the same 2026-07-09
row every week and exited 0 — **`fuel-pipeline.yml` stayed green for 2 months
(2026-07-09 → 2026-08-27) while `fuel_price_cycle` silently stopped advancing**,
freezing the walk-forward backtest at n=15–16 the whole time. World-side data
(`fuel_world_daily`, Brent/RBOB) was unaffected and stayed fresh throughout.

Also found: even the newer category page doesn't reliably list every bulletin —
the 2026-08-27 cycle exists at its predictable URL but isn't linked from either
known category page at all. Category scraping alone is not trustworthy going
forward.

**Fixed**: `discover_latest()` now takes two independent signals — (1) scans both
known category pages, (2) directly probes the predictable URL pattern for every
date up to `PROBE_WINDOW_DAYS` (21) after the latest stored cycle, since the URL
itself doesn't depend on any listing page. `main()` no longer treats "nothing newer
found" as success-with-no-op silently: it's a normal, logged no-op below
`STALE_AFTER_DAYS` (25, comfortably above the ~14-day cadence observed since
2026-08-13), and a hard `sys.exit` (workflow goes red) past that — the exact
scenario that let this go unnoticed for 2 months can no longer report green.
Backfilled 2026-08-13 and 2026-08-27 (both verified real, found by direct URL
probing) using the production parser; two prior weekly bulletins that would fall
weekly-cadence-wise in the 2026-07-16→2026-08-06 gap were checked directly by URL
and do not exist — a genuine source-side gap (likely tied to MOIT's 2026-07-27
public consultation on a new fuel-trading Decree), not a crawler miss.

If this freezes again: check `https://moit.gov.vn` manually for where the bulletin
moved, and add the new category to `MOIT_NEWS_INDEXES` in `crawl_moit_fuel.py` —
the date-probe fallback alone will still catch a new cycle within
`PROBE_WINDOW_DAYS`, but finding the right category faster reduces reliance on that
fallback.

### Fuel forecast model — structural-v1 removed, delta-world-v1 only (2026-09-10)

**`structural-v1` (two-stage OLS: `world ~ Brent/RBOB`, then `retail ~ Nghị định 80
formula(world)`) is fully deleted from the codebase** — `be/fuel/formula.py` and
`be/fuel/world_model.py` are gone, `fit_calibration`/`predict_world`/`predict_retail`/
`FuelCalibration`/`STANDARD_PARAMS` are gone from `calibration.py`, `walk_forward`
is gone from `backtest.py`. It never beat random-walk in any backtest (skill
-0.19..0.00 across all three fuels, refreshed 2026-09-08) — Brent/RBOB are only
loosely correlated with the Singapore MOPS price the regulator's formula actually
uses, and the module existed only to feed it. **`delta-world-v1`
(`retail_t ≈ retail_{t-1} + k·Δworld`, fit on the MOPS-based `world_avg_price` MOIT
itself publishes each cycle) is now the only model**, in both `backtest.py` and
`forecast.py`.

**Statistical hardening (2026-09-10)**, computed directly from `fuel_price_cycle`
(full-sample OLS-through-origin on Δworld/Δretail, complementing the walk-forward
numbers already in `fuel_backtest`) — methodology follows Hyndman & Athanasopoulos,
*Forecasting: Principles and Practice* (free, OTexts.com/fpp3): the project's
`skill_vs_rw = 1 - MAE/MAE_RW` is algebraically `1 - MASE` (mean absolute scaled
error), the standard scale-free accuracy metric from that text.

| Fuel | k (VND/L per USD/bbl) | SE(k) | t | p | R² | Wilcoxon p (beats RW) |
|---|---|---|---|---|---|---|
| DO005S | 153.1 | 6.6 | 23.4 | <0.0001 | 0.96 | <0.0001 |
| E5RON92 | 131.7 | 20.1 | 6.6 | <0.0001 | 0.65 | 0.001 |
| RON95 | 149.7 | 22.1 | 6.8 | <0.0001 | 0.68 | 0.003 |

k is significant well beyond p<0.05 for all three fuels — the pass-through
relationship is real, not a small-sample artifact, and beats random-walk with a
non-parametric paired test (Wilcoxon signed-rank on `|RW error| - |model error|`),
not just a point skill estimate.

**Known weakness, not yet fixed**: residuals from this regression show notable
**negative lag-1 autocorrelation** (-0.45 to -0.57) and **reject normality**
(Shapiro-Wilk p<0.001 for all three fuels). This means the `z·resid_std` confidence
interval used in both `walk_forward_delta` and the live forecaster's world-shift
band is not theoretically well-calibrated. In practice, walk-forward coverage
still came out at 88-94% (more conservative than the nominal ~80% for z=1.28), so
this is not currently producing overconfident bands — but it is a legitimate
next-step: either fit an AR(1) correction on the residual, or replace the Gaussian
CI with a bootstrap interval over historical residuals.

**R² is much lower for gasoline than diesel (E5RON92 0.65, RON95 0.68, DO005S
0.96) — traced to 2 specific cycles, not diffuse noise (2026-09-10 follow-up).**
A 20,000-draw permutation test (shuffle Δworld against Δretail, refit k, recompute
R²) puts the null (random-pairing) R² at ~0.04 ± 0.07 for all three fuels — the
observed R² beats 100% of 20,000 shuffles for every fuel (p<0.0001), so "low"
here is not "no better than random." The gasoline/diesel gap traces almost
entirely to **2026-03-07 and 2026-03-26**: world price rose sharply (+19 to +42
USD/bbl) both cycles, retail followed roughly on schedule on 03-07 but then
**fell** for E5RON92/RON95 on 03-26 despite world still rising (diesel kept
rising, just by less than predicted) — almost certainly a discretionary BOG-fund
draw or tax adjustment specific to gasoline (more politically visible / motorbike
fuel) around that period, not present for diesel. Dropping just these 2 of 24
cycles brings E5RON92 and RON95 to R²=0.91, matching diesel's 0.98. This is
also a likely partial driver of the negative residual autocorrelation above (two
adjacent cycles with large opposite-sign residuals mechanically induces negative
lag-1 correlation). **Next step, not done**: add a discrete intervention/dummy
term for BOG-drawdown cycles instead of treating them as regression noise —
identifying which cycles those are (beyond eyeballing these 2) needs a proper
event flag, which the source bulletins may or may not make extractable.

**Live forecaster (`forecast.py`) no longer generates a point prediction.** The
delta model needs Δworld for the *next* cycle, and the real value (MOIT's next
MOPS figure) isn't known before the announcement without a licensed real-time
feed — reusing the just-deleted Brent proxy to guess it would silently reintroduce
the same proxy-error problem that made structural-v1 fail. Instead, `fuel_forecast`
rows are **world-conditional scenarios**: "if world price moves by X, retail moves
by k·X" for three illustrative Δworld draws (low/base/high) sized from the
historical cycle-to-cycle volatility of `world_avg_price` itself (population
std-dev, random-walk-on-world assumption, spread scaling with `sqrt(horizon)`).
`base` always equals the last known retail price unchanged. This is a deliberately
less "impressive" output than a single point forecast, but it's the honest thing
the data supports without paying for MOPS — matches the fallback BACKLOG.md already
called for ("không có feed thì bán scenario world-conditional").

**`CYCLE_DAYS` bug found + fixed 2026-09-10**: `forecast.py` had spaced forecast
horizons using a hardcoded `CYCLE_DAYS = 7`, silently wrong once the real cadence
shifted toward ~14 days (see "Fuel (domestic) crawl" above) — horizon labels were
under-dated by close to 2x. Replaced with `_estimate_cycle_days()`, the median gap
over the last 6 known cycles per fuel, recomputed on every forecast run so it
self-corrects if cadence shifts again. Current value comes out to 10 days (not a
clean 7 or 14) because the 6-cycle window still spans the mid-2026 transition
(includes one 35-day gap from the regulatory pause) — only 2 cycles exist so far
in the new ~14-day regime, too few to confidently call it the new steady state.
This is an honest limitation of the heuristic, not a bug: don't hand-tune the
window to force a "cleaner" number without more post-transition data.

**MOPS/Platts direct crawl — investigated 2026-09-10, not viable without an
enterprise contract.** S&P Global Commodity Insights (formerly Platts) requires
account accreditation for any API access and has no free/public tier; MOPS itself
has no public webpage to scrape — it's delivered only through their authenticated
Platts Connect / API products. Subscription pricing is not published ("contact
our team"), consistent with other enterprise data-vendor products. Do not build a
crawler against Platts without a signed commercial agreement — there is nothing
publicly reachable to point it at, unlike the MOIT-bulletin workaround this
project already uses for historical MOPS values.

**`fuel_world_daily` (Brent/RBOB, crawled by `crawl_fuel_world.py`) has zero
consumers now** — nothing in `be/fuel/` reads it anymore. Left running (free,
harmless, no license issue) as raw world-oil-price context data in case it's
useful for a future dashboard/UI panel; it is not wiring into the forecasting
model again without a specific, deliberate reason given it's exactly the proxy
that failed. `fuel_formula_params` (schema table) has never had a code writer or
reader — dead since it was created; not dropped from the DB, but do not build
against it without first re-checking this note.

## GitHub Actions Workflows

`.github/workflows/` — one workflow per crawl source (`{asset}-crawl.yml`), plus `build-html.yml` (regenerates `fe/index.html` on `fe/partials/` change), `generate-static-data.yml`, `data-quality-check.yml`, `market-pulse.yml`, `deploy.yml` (auto-deploy to prod), and `uptime-check.yml`.

`uptime-check.yml` runs daily at 11:00 VN and is the **only** production alerting we have: it probes prod from outside the box (root page + body size, `www`, `api`, anonymous `/gold` still 401, the three SEO root files, and cert expiry with a 14-day warning). A failure turns the workflow red and GitHub emails the repo owner. It must stay off-box — an on-box cron dies with the box it watches. Added after a 31h TLS outage went unnoticed (`DEPLOY.md`).

Cron in VN time (UTC+7): `'7 1 * * *'` = 08:07 VN. Standard steps: checkout → setup-python → `pip install -r crawl_tools/requirements.txt` → `python crawl_tools/crawl_{source}.py` with DB env from secrets.

**Never schedule a crawl on `:00` or `:30`.** GitHub runs scheduled workflows at low priority on shared runners and delays or drops them under load, and the round minutes are the congested slots. Measured 2026-08-09 on the old `'30 1'` + `'30 2-9'` gold/silver schedule: the 01:30 UTC primary slot *never fired at all* (first run of the day landed 03:04–04:38 UTC), only 4–8 of the 9 declared runs materialised, and the runs that did fire started **32 min late on average, 58 max**. Result: the day's gold data reached the DB at 10:00–12:40 VN instead of 08:30 VN, every day, with GitHub healthy. Daily crawlers now sit on distinct odd minutes so they neither hit a congested slot nor collide with each other: gold/silver `7`, termdepo `13`, exchange-rate `17`, SBV `23`, VN30 ratios `27`.

### Box-side crawl fallback (`deploy/crawl-fallback.*`) — INACTIVE since 2026-09-04

**Not currently running.** Prod moved off the Hetzner box (deleted 2026-09-04, see "Where production actually serves from" below) to a BKHOST VPS, and this systemd timer was never re-provisioned on the new box. Actions remains the crawl path and is unaffected — this was only ever a secondary safety net for gold/silver lateness, not a required dependency — but re-read this section and re-run the install steps in `DEPLOY.md` before assuming it's protecting anything.

Design, kept for reference / re-provisioning: odd minutes reduce GitHub's scheduling delay but cannot eliminate it — scheduled runs stay best-effort. A systemd timer on the box fired at **01:45 and 03:00 UTC** (08:45 / 10:00 VN) and crawled gold/silver **only if that day's rows are still missing**, bounding lateness independently of GitHub. It was a net, not a replacement: Actions stayed the primary path and the timer was a no-op on a healthy day.

Two things to preserve when touching it:

- **Success is judged by re-probing the DB, never by the crawler's exit code.** `crawl_gold_silver.py` exits 1 whenever its Yahoo Finance section fails, and Yahoo blocks index tickers from datacenter IPs — which the box has. A non-zero exit there is expected and does not mean the domestic crawl failed.
- **It runs in `python:3.11-slim` (`deploy/crawler.Dockerfile`), not on the box Python.** The box ships Python 3.14 with no `python3-venv`, while `crawl_tools/requirements.txt` pins 3.11-era versions. The image installs only the subset `crawl_gold_silver.py` imports, version-pinned by passing `crawl_tools/requirements.txt` to pip as a *constraint* file, so it stays in lockstep with CI without a duplicate dependency list. The repo is bind-mounted at `/repo`, so deploys refresh crawler code without an image rebuild.

Install/verify steps are in `DEPLOY.md`. This does **not** change the rule that `uptime-check.yml` must stay off-box — a watchdog cannot live on the machine it watches, whereas a crawler net legitimately can.

## Backend (FastAPI)

`be/main.py` registers routers and mounts `fe/` as static at `/fe`. Static `.env` is read from repo root, not `be/.env`. Root `/` 307-redirects to `/fe/`. For SEO/AEO, `main.py` also serves `robots.txt`, `sitemap.xml` and `llms.txt` from `fe/` at the **domain root** (`/robots.txt`, `/sitemap.xml`, `/llms.txt`) — crawlers (Googlebot, GPTBot, ClaudeBot, PerplexityBot) only read these at root, not under `/fe/`. Edit the source files in `fe/`; the root routes just re-serve them. `robots.txt` explicitly welcomes AI/LLM crawlers; `llms.txt` is the machine-readable site/dataset overview (llmstxt.org format).

### API URL pattern

```
/api/v1/{asset}              # primary data endpoint (Open Data)
/api/v1/{asset}/types        # subtype list (banks, gold types)
/api/v1/macro/{indicator}    # macro indicators
/api/v1/knowledge/*          # Agent Market (knowledge.py)
/api/v1/wallet/*             # credits, top-up, balance
/api/v1/seller/*             # seller dashboard, listings
/api/v1/reports/*, /takedown/*  # moderation/DMCA
```

Open-data routes under gold/silver/SBV/term-deposit/global/VN30/macro are gated in `be/main.py`: anonymous or invalid credentials return `401`, while free and paid API keys and valid FE Bearer sessions are metered. Public `gold-analysis` / `market-pulse` calls and rejected metered calls are tracked without storing IP, token, raw API key, or user-agent. Admin performance reporting at `/pages/admin.html` supports `24h`, `7d`, and `YTD` periods.

`/pages/admin.html` (Auth0 login + `is_admin`/`user_level='admin'`, backed by `/api/v1/admin/*` with `admin_audit_log`) is the **only** admin/reporting surface. The secret-link report `GET /api/v1/report?key=<REPORT_SECRET>` (`be/routers/report_dashboard.py`) was removed on 2026-08-06: it duplicated data the admin dashboard already showed, put a credential in the URL (Caddy access logs, browser history, `Referer`), had no per-person revocation or audit trail, and fell back to `WEBHOOK_INTERNAL_SECRET` — the same secret GitHub Actions sends on every crawl webhook. Do not reintroduce secret-in-URL admin surfaces; add new reporting as an `/api/v1/admin/*` endpoint plus a section in `admin.html`.

### GA4 Reporting API (2026-09)

`admin_dashboard` (`be/routers/admin.py`) now returns a `website_traffic` field (active users, pageviews, sessions, new users for the selected `24h`/`7d`/`ytd` period) sourced from GA4 property `522974314` via `be/core/ga4.py`. Site-side `gtag.js` tracking (`fe/partials/_layout_head.html`, two Measurement IDs `G-YB3PKHN2E5`/`G-B9BHYSYDES` — both data streams under this one property) already existed; this adds server-side *read* access so the number shows up in `admin.html` instead of requiring a manual login to analytics.google.com.

**Auth is a personal OAuth refresh token, not a service-account key.** The GCP project (`vietdataverse`, under Cloud org `findatasolution-org`) has the org policy `iam.disableServiceAccountKeyCreation` enforced at the organization level; overriding it at the project level still failed (a second, "managed" version of the same constraint applies in parallel), and chasing an org-admin override was more friction than it was worth for a single read-only integration. The working path instead: an OAuth 2.0 **Desktop app** client (`Google Auth Platform → Clients`, consent screen in **Testing** mode with the operating Google account added as a test user) + a one-time local `InstalledAppFlow.run_local_server()` browser consent, scope `analytics.readonly`. The resulting refresh token does not expire on its own (only if access is revoked in the Google Account or the OAuth client is deleted) and is stored as 4 env vars, never as a file: `GA4_PROPERTY_ID`, `GA4_OAUTH_CLIENT_ID`, `GA4_OAUTH_CLIENT_SECRET`, `GA4_OAUTH_REFRESH_TOKEN` (see `.env.example`). If the refresh token is ever revoked, redo the one-time consent flow (`InstalledAppFlow.from_client_secrets_file(...).run_local_server(port=0)`, scope `https://www.googleapis.com/auth/analytics.readonly`) logged in as an account with at least Viewer access on the GA4 property, then update the 4 env vars — do not re-attempt the service-account route without first confirming the org policy has changed.

`ga4.get_traffic_summary(period)` maps `24h`→`yesterday..today`, `7d`→`7daysAgo..today`, `ytd`→ Jan 1 of the current year..today (GA4's relative-date strings, not the SQL `_REPORT_PERIODS` intervals used elsewhere in the same endpoint — GA4 doesn't support an arbitrary trailing-24-hours window without an hour-level dimension, so `24h` is approximated as "yesterday plus today so far"). The call sits outside the endpoint's `with get_engine_user().connect()` block (a network call has no reason to hold a DB connection open) and is wrapped in try/except so a GA4 hiccup degrades to `{"error": ...}` rather than 500ing the whole dashboard.

### 1s Pulse API status

`GET /api/v1/market-pulse` currently reads `ARGUS_FINTEL_DB.mri_analysis` and is intentionally public for the FE. It supports only `lang` and `limit` (maximum 50); it does not yet provide pagination, total count, time/source/label/MRI filters, or an official stable response contract. The Developer catalog currently labels it `premium_developer`, so access policy is inconsistent. Treat `BACKLOG.md` item `API-06` as the source of truth before marketing or monetizing this endpoint as an official API.

### 1s Pulse source research (not approved)

No 1s Pulse source expansion has been approved. `be/1s_market_pulse.py` already uses `feedparser==6.0.11`. Vietnamese RSS sources (CafeF, VnExpress, Vietstock, ĐTCK, VietnamNet, Tuổi Trẻ) were removed in commit `d408d5887` on 2026-06-30 to make the product international-sentiment-only, not because feedparser failed. A 2026-07-05 audit confirmed CafeF and VnExpress feeds still return parseable entries. Free options under consideration are RSS/official press rooms, SEC EDGAR, YouTube free quota/channel feeds, Bluesky public API, and Mastodon public endpoints. X is pay-per-use; LinkedIn crawling is prohibited and read access is restricted. Unofficial alternatives were also tested: `ntscraper==0.4.0` found no working Nitter instance, unauthenticated `twikit==2.3.3` failed on current X client-transaction data, and `Mastodon.py==2.2.1` received 403 from Truth account/status endpoints. Do not add these unofficial scrapers or hidden endpoints to production: they are unstable and current X/Truth terms prohibit unauthorized scraping/automated access. Treat the corresponding `BACKLOG.md` section as research only and do not implement it without explicit user approval.

Response shape:
```json
{"success": true, "source": "GSO/NSO vn_gso_cpi_monthly", "count": 21, "data": [...]}
```

### GSO GDP/IIP/Trade crawlers — window-targeted backfill (2026-09)

`crawl_gso_gdp.py`, `crawl_gso_industry.py` (IIP), and `crawl_gso_trade.py` — like `crawl_gso_cpi.py` before them — now each expose `crawl_period(year, month_or_quarter)`, so they can target any historical period instead of only "whatever bulletin is newest". Before this, every one of these three tables held exactly **one** row (created on first run, never backfilled), because `fetch_gso_html()` structurally could only ever return the latest article no matter when it ran.

**Source**: `nso.gov.vn`'s WordPress REST API (`wp-json/wp/v2/posts`), not scraped HTML — `find_article_by_window(year, period)` lists posts published in a window after the period closes (start = 25th of the closing month; end = day 10–20 of the month after, wider for a quarter-closing month — see below) and filters by URL slug. GDP and IIP additionally have a **dedicated per-period article** search (`find_iip_dedicated_articles` for IIP; GDP and Trade only use the general bulletin). Extraction is prose-regex against `content.rendered` (BeautifulSoup → whitespace-collapsed text), with Gemini (`gemini-2.5-flash`) as a last-resort layer 3 — used only when the regex layer finds nothing, since the free tier's rate limit makes it unusable as a primary path at backfill volume (a bulk run hits `429` every few calls).

**Article discovery is unreliable before 2020** (a 2019 site migration bulk-republished old bulletins under shared timestamps that don't reflect their real reporting period) — none of these three crawlers' backfills go earlier than 2020-01.

**A republish artifact can also land inside a *post*-2020 window**: `find_article_by_window(2020, 11)` once matched a slug from 2004, because the slug filter alone doesn't check which year the article is actually about. All four GSO crawlers (CPI included) now additionally require the target year to appear in the post's own **URL slug** (not the full URL — the `/YYYY/MM/` path prefix is the *publish* date and matched even the 2004 article, since NSO happened to publish it in 2020) before accepting a match.

**Quarter-closing months (Mar/Jun/Sep/Dec) publish later than plain months**: the Sept-2020 bulletin wasn't posted until Nov 2 — 13 days past the window that works for every other month — so IIP's and Trade's `find_article_by_window` widen the window (end day 10 instead of 20, extending into month+2) and prefer a slug containing `quy-{roman}` for those four months.

**Known, source-side gaps left as NULL, not guessed** (verified against source, not a bug):
- IIP is missing for 16 quarter-closing months (`2020-03/06/12`, `2021-03/06/09/12`, `2022-03/06/12`, `2023-03/09/12`, `2024-03`, `2025-06/09`) — NSO's general socio-economic bulletin states **"Giá trị tăng thêm toàn ngành công nghiệp"** (industrial *value-added* growth) for the closing month of a quarter, not **"Chỉ số sản xuất công nghiệp (IIP)"** (the production index) — two different statistics that read as near-synonyms in Vietnamese. The dedicated per-month IIP article (which does carry the real IIP figure even for quarter-closing months, e.g. `.../chi-so-san-xuat-cong-nghiep-thang-6-nam-2023/`) doesn't exist for older years and is sometimes only an infographic caption with no full sentence to parse. Treating "Giá trị tăng thêm" as IIP was an actual bug caught mid-session (a wrongly-labeled `2023-06` row was written, then deleted) — the keyword list explicitly excludes that phrase, so these periods return no row rather than a mislabeled one.
- GDP is missing `2024Q1`, Trade is missing `2020-12`, `2024-03`, `2026-05` — no bulletin was found under the expected slug family within a widened window (through ~2 weeks into month+2) for these specific periods. `2026-05`'s bulletin does exist (published 2026-06-03) but its own slug has a typo (`...-nam-2025-2`, wrong year, presumably cloned from the prior year's May article) — the year-guard above correctly rejects it since NSO's own slug says the wrong year, and loosening the guard to admit it would reopen the 2004-in-2020 class of bug for one single period. Not investigated further past this point; do not backfill these four periods with an LLM guess.

**A 2023Q2 GDP `industry` row was previously wrong** (`1.56%`; source says `1.13%`) — it came from an early LLM extraction that was never checked against source (only the headline `total` figure had been verified). The table-based `layer1_structured` this replaced returned 0 records for every GDP quarter tested (2020Q1/2022Q3/2023Q2/2026Q1) because NSO's quarterly bulletin states GDP in prose, never a `<table>` — so every quarter was silently falling through to Gemini. The table was truncated and fully re-backfilled with the new prose parser once this was found.

**A `records` layer-fallthrough bug independently caused the entire first IIP backfill attempt to return 0/80**: `crawl_period` fell through to layer 2/3 whenever `len(records) < 2`, but the prose-based IIP `layer1_structured` can only ever return 1 record (the aggregate; it has no per-sector breakdown), so a perfectly correct layer-1 match was discarded and replaced with a rate-limited Gemini call on *every single period*, including ones later confirmed to parse correctly in isolation. Fixed to `if not records:` in all three crawlers' `crawl_period`/`main()`.

### Static JSON pattern (for FE perf)

`fe/data/{asset}_{subtype}_{period}.json` (e.g. `termdepo_ACB_1y.json`), `{asset}_types.json`, `manifest.json`. Generated by `be/generate_static_data.py` via `generate-static-data.yml`.

## Frontend

`fe/index.html` is **auto-generated** from 8 partials in `fe/partials/` by `python fe/build.py`. Never edit `index.html` directly — CI rebuilds and overwrites it. See `fe/CLAUDE.md` for full build workflow.

### Where production actually serves from

**FastAPI + Caddy on a BKHOST VPS (`103.130.215.180`, Vietnam), and nowhere else.** `https://vietdataverse.online/` answers with `server: uvicorn`, `via: Caddy`, and 307-redirects to `/fe/`.

**Migrated 2026-09-04 from the Hetzner box (`62.238.25.95`, Germany) — that server has been deleted.** Root cause: `nso.gov.vn` (the GSO crawlers' source) resets connections from foreign/EU datacenter IPs, and this affected Hetzner itself, not just GitHub Actions runners — no box hosted in an EU/US datacenter can reach it. A VN-datacenter VPS was the only fix that didn't also require standing up separate proxy infrastructure. `mythreel.studio`, which previously shared the Hetzner box (own containers, own Postgres job-queue, its own real data on Neon/R2 — nothing box-local was lost), was discontinued in the same move; the new box runs VDV standalone with its own Caddy (`docker-compose.override.yml` on the box, not committed to git — see `deploy/vietdataverse.caddy` for the routing rules it replicates). Deploy secrets are `DEPLOY_HOST/USER/PORT/APP_DIR/SSH_KEY` (renamed from `HETZNER_*`; a fresh `vdv-github-deploy-bkhost` ed25519 key was issued, the old Hetzner key is no longer valid since the box is gone). The box-side crawl fallback for gold/silver was **not** re-provisioned on the new box — see the GitHub Actions Workflows section above.

GitHub Pages is **also enabled** on this repo (source: `main` branch, root path) and builds on every push, but it is a stale orphan, not a deploy target:

- `findatasolution.github.io/vietdataverse/` → 404, because the repo root has no `index.html` (it lives at `fe/index.html`).
- `findatasolution.github.io/vietdataverse/fe/` → **200, a full public duplicate of the site.**

That duplicate is kept out of trouble solely by the hardcoded `<link rel="canonical" href="https://vietdataverse.online/">` in `index.html`, which points search engines back at the real domain. A repo `robots.txt` cannot block it: on `github.io` the effective robots file is at the domain root, which GitHub controls. If you ever drop or template that canonical, verify the github.io copy first.

**Disabling Pages needs the repo owner.** Attempted 2026-08-26 via `gh api -X DELETE repos/findatasolution/vietdataverse/pages` → `404`. The repo is owned by the user account `findatasolution`; the usual working account (`Hiienng`) has `push`/`triage` but `admin: false`, and deleting a Pages site requires admin. No token scope fixes this — it is a repo-level permission. Do it in the UI as `findatasolution`: **Settings → Pages → Build and deployment → Source → None**. Until then Pages keeps building on every push and the `/fe/` duplicate stays up.

### Workspace IA (top-level navigation)

3 workspaces with top tab bar + per-workspace sidebar context:

- **`data-workspace="data"`** — Open Data (charts, downloads, API Key, API Docs)
- **`data-workspace="km"`** — Agent Market (Discover / My Stuff / Sell / Help sub-nav)
- **`data-workspace="pulse"`** — Thời báo 1 giây

Routing: hash `#<workspace>/<view>` handled by `setWorkspace()`/`setView()` in `app.js`. `LEGACY_HASH_MAP` redirects old hashes (`#knowledge-market`, `#tab-library`, …).

### Open Data — Overview grid (`#data/portal`)

Landing on Open Data shows a grid of 10 mini-charts grouped under the same 5
section headings the charts have always used (Vàng & Bạc, Tiền tệ VN, Thị
trường quốc tế, Vĩ mô, Chứng khoán), not the five full-size sections stacked
vertically. Clicking a tile routes to `#data/portal/chart/<id>` — that one
chart, full size, unchanged from before. Spec:
`docs/superpowers/specs/2026-08-17-open-data-overview-design.md`.

- **`fe/app.overview.js`** (new, `window.VDOverview`) owns `CHART_REGISTRY` —
  the single declaration of the 10 charts, their static JSON source, and which
  of app.js's four unrelated chart-loading paths (`dispatch` / `policy` /
  `macro` / `stock`) each one uses. It does not touch the full-size charts;
  those stay in `app.js`.
- The five `.chart-section-group` blocks are hidden **in the static HTML**
  (`ov-section-hidden` class baked into `_tab_data_portal.html`), not by JS at
  runtime — the safe default is "show overview" regardless of which code path
  activates the `data-portal` tab. The routing functions
  (`ovShowOverview`/`ovShowChartDetail`/`applyDataPortalRoute`, in `app.js`
  next to the hash-parsing block) toggle that class to reveal one section and
  one `.chart-card[data-chart-id]` at a time.
- **`interbank` and `policy` share one `.chart-card`** in the DOM — the
  interbank chart and the SBV policy-rate panel are two blocks inside the same
  card, not two cards (see `_tab_data_portal.html`'s currency section). Both
  registry ids resolve to `domCardId: 'interbank'`; routing to `policy`
  additionally scrolls to `#sbv-policy-anchor` inside that shared card. The ‹ ›
  detail-nav steps over *distinct DOM cards*, so interbank and policy count as
  one stop, not two.
- `#data/portal/<section>` (the pre-existing 3-segment legacy form) now
  redirects to that section's first chart rather than the dead
  `.chart-tab-btn` click it used to fire — kept one release per §12.6.
- Entering any chart detail re-runs that chart's own load function
  (`loadChartData` / `loadPolicyRates` / `loadMacroCharts` / `loadVnindexChart`).
  Every one of those already destroys its previous Chart.js instance before
  creating a new one, so calling it again is safe *and* — deliberately — sizes
  the new instance against the now-visible container, sidestepping the classic
  Chart.js "canvas was `display:none` on first draw" bug for free.
- `fe/check_overview.py` checks structural invariants (registry ↔ static-file
  field names, DOM `data-chart-id` set, sections hidden by default) — run it
  after touching the registry or the portal partial. It cannot check Chart.js
  rendering itself; that still needs a real browser.
- **A sticky "Tổng quan thị trường" panel (`#market-overview-panel`) sits beside
  the tile grid**, inside `.portal-body` but outside `.ov-root`, so the routing's
  show/hide of `.ov-root`/`.chart-section-group` never touches it. It is shown on
  the overview and `hidden` on any chart detail — a detail view is one chart the
  visitor opened deliberately and gets the full width; VN-INDEX/Brent/WTI beside
  a term-deposit chart is unrelated noise. Its VN-INDEX and USD/VND rows are fed
  by `loadMarketMovement()` in `app.js`; **HNX-INDEX, UPCOM-INDEX, Dầu Brent and
  WTI render "—" because no crawler or table exists for them yet** — they are
  placeholders, not a bug.
- Sections whose charts all have `{7d,1m,1y}` static files (gold-silver, global,
  stock) show a period picker beside the section heading. Macro and currency do
  not: CPI is annual records, GDP is fetched live, and the SBV policy history is
  a single all-time file, so a picker there would leave some tiles unchanged.
- **Tile height is a derived constant** (`.ov-tile-canvas`, currently 212px):
  panel height − section head row − tile chrome, so the first row of tiles ends
  level with the panel. Re-measure it in a browser if the panel gains a row or
  the head row changes height — adding the period picker already moved it once.

### Agent Market (KM) auth states

`_updateSidebarStateAsync()` in `app.knowledge.js` drives sidebar group visibility based on 5 states: **logged-out / banned / unverified seller / active seller / not-registered seller**, plus an independent `_isAdmin` flag. Preserve this logic when refactoring — silent breakage of seller onboarding is the main risk.

### Design system

`.claude/rules/DESIGN.md` is the source of truth for *structure* — Anthropic Serif for headlines, ring shadows (`0px 0px 0px 1px`), generous radius (8–32px). §11 covers marketplace patterns (card anatomy, filter bar, badges, empty states, mobile bottom-sheet) — follow it when touching Agent Market UI.

**The palette was replaced on 2026-08-29**: pastel milky-white + soft blue, not the warm parchment/terracotta scheme DESIGN.md describes. The CSS custom properties in `fe/style.css` kept their names (`--terracotta`, `--parchment`, `--ivory`, …) and now hold blue/near-white values, so component rules did not change — only the values. Brand blue is `#2f5fde`. DESIGN.md carries an override note at the top; its §7 "no cool blue-grays / terracotta only" rules are superseded.

Critical card rule: badges like "VD Official" go in the seller footer row, **never adjacent to the title** (breaks wrap).

### Chart color conventions

```
CPI/inflation : #EF5350 (≥10%), #FFA726 (≥5%), #66BB6A (≥0%), #42A5F5 (<0%)
Gold          : #2f5fde   (brand blue)
Silver        : #4d4c48   (charcoal — NOT #87867f, see below)
Term deposit  : #a3c0f2 (1m) → #6c93e4 (3m) → #2f5fde (6m) → #1e3fae (12m) → #16307f (24m)
Interbank/SBV : #2f5fde (qua đêm), #a3c0f2 (1M), #6c93e4 (3M/9M),
                #1e3fae (chiết khấu), #16307f (tái cấp vốn)
GDP           : #26A69A   (teal)
```

**Rate charts use a single-hue ramp, not categorical hues.** They once used
`#42A5F5 / #66BB6A / #FFA726 / #EF5350 / #AB47BC`, which read as five unrelated
categories for what is an *ordered* variable; light→dark reads short→long on its
own. If five same-hue lines ever prove hard to separate, add dash patterns rather
than reintroducing hues. The ramp was terracotta until the 2026-08-29 palette
change and is now blue — same structure, new hue.

**Chart colours live in TWO files and both must be changed together.** The
full-size charts are coloured in `fe/app.js`; the overview mini-charts have their
own colour per entry in `CHART_REGISTRY` (`fe/app.overview.js`). Editing only
`app.js` leaves the overview tiles on the old palette — that shipped once and is
easy to repeat.

**CPI keeps its categorical colours** — there red/amber/green/blue encode
inflation severity, which is data meaning, not decoration. Same for the ▲/▼
sparkline pair and error text. Only re-colour a chart when the colour is
decorative.

**Never use `#87867f` (Stone Gray) for a data line.** It is the tertiary *text*
colour; as a 2px line on white it reads as disabled. Both silver series were
drawn in it.

### Chart honesty rules (added 2026-08-10)

Four defects where the chart said something the data did not. Do not reintroduce:

- **Rate series use `type: 'time'`, not a category axis.** The 1-year term-deposit
  and interbank series are sampled monthly up to 2026-01 and daily after, so a
  category axis drew a 30-day step the same width as a 1-day step and invented a
  vertical cliff in January. Requires `chartjs-adapter-date-fns` (loaded in
  `_layout_head.html` next to Chart.js).
- **`fill: true` requires a zero baseline.** An area fill states "magnitude
  measured from zero". Gold (starting at 134 triệu), USD/VND and VN-Index cannot
  sensibly start at zero, so they use `fill: false`. CPI and GDP keep their fill
  and force `beginAtZero`.
- **No dual axes.** The global gold/silver chart had gold on the left ($3–6k) and
  silver on the right ($30–120); two arbitrary scales made the lines cross at
  meaningless points and implied a correlation. Both are rebased to 100 at the
  first point on one axis; the tooltip still shows real $/oz.
- **Give a series the horizon its data actually moves on.** SBV's refinancing and
  rediscount rates are *administered*: SBV moves them a handful of times a year
  and then holds. On the interbank window (7 ngày–1 năm) they are flat by
  construction, so plotting them there produced two straight lines — and
  replacing that with a bare pair of numbers removed the trend entirely, which is
  worse: the direction and timing of policy moves is one of the most-cited facts
  in VN macro. The panel now has its **own** horizon (5 năm / 10 năm / Tất cả)
  fed by `fe/data/sbv_policy_all.json`, and renders `stepped: 'before'` with
  `tension: 0` — a policy rate holds and then jumps on a decision date; smoothing
  drew a curve through dates on which nothing happened.
- **The policy rates also overlay the interbank chart as dashed reference lines.**
  The refinancing rate is the ceiling of SBV's corridor, so the reading that
  matters is the *gap*: overnight drifting up toward or through the ceiling is the
  liquidity-stress signal. Keeping the two in separate charts hid it.

### `fe/data/sbv_policy_all.json`

Generated by `generate_sbv_policy_history()` in `be/generate_static_data.py`.
`vn_macro_sbv_rate_daily` mixes sparse policy-decision rows going back to **2002**
(interbank columns NULL) with recent daily interbank observations that carry the
prevailing policy rate along; the generator collapses both to the dates a rate
actually **changed** — 45 points, ~1 KB — and appends today so the final step runs
to the present instead of stopping at the last decision.

`last_change` in that file is the last **decision** date (currently `2023-06-19`,
after the four 2023 cuts took refinancing 6.0 → 4.5). The FE prints "không đổi kể
từ …" from it. Never substitute the first date of the visible window: an earlier
version did, and showed "từ 10/07/2026" for a rate that had held for three years.

Related: the VN-Index period buttons offer up to "3 năm" but
`vn_macro_vnindex_daily` only starts **2026-04-16**, so the chart prints the range
it actually plotted underneath. The real fix is backfilling that table — until
then, do not remove the coverage caption.

## Data Quality

Validate before insert:
```python
def validate_rates(data):
    term_keys = [k for k in data if k.startswith('term_') and data[k] is not None]
    if len(term_keys) < 3: return False
    for key in term_keys:
        if not (0.1 <= data[key] <= 20.0): return False
    return True
```

Workflow `data-quality-check.yml` runs scheduled DQ checks. There is also a `data-quality-check` skill — note it is scoped to `manual_listing_report` / `manual_keyword_report` only, **not** the macro tables.

`crawl_tools/data_quality_check.py` was overhauled on 2026-08-31 after an audit
found it reporting 15 issues of which 11 were false, which is why a real outage
(VN30 `pe`/`pb` 100% NULL since 2026-05-15) went unnoticed for months. Rules that
keep it honest:

- **Duplicates group by each table's real business key** (`dup_key` in `TABLES`),
  not `(period, source)`. `source` is constant per crawler, so the old grouping
  reported one "duplicate" per extra brand/ticker/bank on the same day.
- **Ranges must match the stored unit.** VN30 prices are in *thousand* VND
  (close 1.29–236); checking them against `[1000, 500000]` flagged all 73,307
  rows. A 100% hit rate is a broken threshold, not a data problem.
- **Freshness for Mon–Fri-only tables compares against the last business day**
  (`market_days=True`), or every Monday run fails because T-1 is Sunday.
- **NULL checks look at recent rows and fire at a ≥10% rate**, so long-closed
  historical gaps and market holidays stop re-reporting forever.
- **`row_filter` scopes both the null and range checks** where a column applies
  to only some rows — `usd_vnd_rate` exists only on the USD row, and
  `Vàng TG ($)` is USD-denominated inside a VND table.

### Gold history was unit-repaired (2026-08-31)

`be/migrations/fix_gold_units.py` corrected 1,431 rows of `vn_macro_gold_daily`
whose 2015–2021 backfill mixed units (×1000 = thousand VND, ×10 = per chỉ rather
than per lượng). It only touches a row when one power of ten lands it within 15%
of the median of nearby correctly-quoted brands, and dumps every change to CSV
first. Domestic gold now spans 21.19M (2009) to 191.3M (Feb 2026 peak) with no
out-of-range row.

`Vàng TG ($)` (771 rows) is world gold in USD sitting in this VND table, stale
since 2019 — a different instrument, not a unit error. Left in place; the DQ
range check excludes it.

**PNJ quotes ring gold while DOJI/SJC quote SJC bars.** During the 2022–2023 bar
premium they differed by ~17% (2023-06-15: DOJI 67.1M vs PNJ 55.5M). Both are
correct. `crawl_tools/gold_validation.py`'s 15% cross-brand rule would reject the
ring-gold quotes if that premium returns.

### Gold & silver validation (`crawl_tools/gold_validation.py`)

Rules live in their own module so they are unit-testable (`crawl_tools/test_gold_validation.py`, run with `python -m pytest crawl_tools/` from the repo root — CI does not run it yet):

- **Range**: gold 20M–500M VND/lượng, silver 300k–20M VND/lượng. Rejects a dropped or extra digit.
- **Cross-brand median**: a brand more than 15% off the same-day median across all brands is rejected (needs ≥3 brands, otherwise skipped). Catches a digit error that still lands inside the range.
- Rejected rows are never inserted; if the whole page fails, `crawl_gold_silver.py` exits non-zero (`gold_failed`, mirroring `global_failed`) so the workflow turns red instead of silently serving stale data.

Added 2026-08-07 after 24h.com.vn itself published DOJI at `14,450` instead of `144,500` on 2026-07-18–19. The crawler had no pre-insert validation, so a price one tenth of the real value reached the public chart and the API and stayed there 20 days. The DQ email agent did flag it as a WARNING — it just never blocked anything and nobody read the mail.

### Uniqueness

`vn_macro_gold_daily` has `uq_vn_gold_date_type (date, type)`; `vn_macro_silver_daily` has `uq_vn_silver_date_source (date, source)`. Both crawler INSERTs use `ON CONFLICT … DO UPDATE`, so overlapping hourly retries refresh the row instead of appending a second one. Before these existed (2026-01→06), retries left 1,217 duplicate gold rows and 298 silver rows, 347 of them disagreeing on price.

### Missing values are `null`, never `0`

`be/generate_static_data.py` (`num()`) and `be/routers/market_data.py` (`_num()`) emit `null` for a NULL column on the gold and global-macro endpoints. Emitting `0` made charts plunge to the axis and API consumers read a gap as a real price of zero. Chart.js skips nulls, leaving an honest gap. Other tables still coerce to `0` — they have no NULLs today; convert them the same way if that changes.
