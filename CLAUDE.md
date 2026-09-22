# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Communication

Trao đổi với người dùng (chat, giải thích, tóm tắt) bằng tiếng Việt. Code, comment, commit message vẫn giữ tiếng Anh như chuẩn hiện tại của repo.

## Agent Boundaries — Codex (HARD RULES)

Hai luật tuyệt đối, không có ngoại lệ và không được tự diễn giải lỏng ra:

1. **NGHIÊM CẤM Codex sửa `CLAUDE.md`** — dù chỉ một ký tự, dù là sửa chính tả,
   đổi đường dẫn, hay "dọn dẹp" cho nhất quán. File này do user và Claude
   Code duy trì. Nếu Codex thấy nội dung trong `CLAUDE.md` sai hoặc lỗi thời:
   **báo cho user, không tự sửa**. Ghi chú riêng của Codex thuộc về `AGENTS.md`.

2. **NGHIÊM CẤM Codex edit hoặc xoá bất kỳ file nào khi không có yêu cầu trực
   tiếp từ user.** "Trực tiếp" nghĩa là user nói rõ file/phạm vi đó trong
   phiên hiện tại. Không suy ra từ ngữ cảnh, không "tiện tay sửa luôn",
   không refactor kèm, không xoá file thừa, không đổi tên, không format lại file
   ngoài phạm vi được giao. Task diagnose/review là chỉ-đọc: báo finding, không
   sửa.

Lý do luật này tồn tại (2026-09-16): trong một phiên Claude Code đang làm việc
khác, working tree đột ngột xuất hiện `CODEX.md` bị xoá + `CLAUDE.md` và
`AGENTS.md` bị sửa mà user không yêu cầu — hai agent ghi đè lên cùng cây làm việc,
rất dễ commit nhầm thay đổi của nhau lên prod. `CODEX.md` sau đó được user xác
nhận là xoá có chủ đích, nhưng phần sửa `CLAUDE.md` đã bị revert.

**Áp dụng cho Claude Code luôn ở luật 2**: agent nào cũng chỉ được động vào file
nằm trong phạm vi user giao. Thấy thay đổi lạ trong working tree mà mình không
tạo ra thì **tách ra, hỏi user, không commit kèm**.

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

1. Identify every document affected by the change, including `BACKLOG.md`, `CLAUDE.md`, scoped `fe/CLAUDE.md` / `AGENTS.md`, README/API docs, runbooks, architecture notes, migration notes, and `.env.example` when applicable.
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
| `KNOWLEDGE_MARKET_DB` | Knowledge Marketplace + wallet (separate Neon DB from `USER_DB`, despite the row above — `get_engine_knowledge()` in `be/core/engines.py`) | `knowledge_products`, `seller_earnings`, `credit_balance`, `credit_ledger`, `platform_products`, `platform_subscriptions`, `platform_subscription_events` |
| `HELPER_DB` | Internal ops/DQ tables | — |
| `FUEL_FORECAST_DB` | Fuel-forecast product (isolated; wallet-billed consumer subscription, not the originally-envisioned B2B corporate API — see "Platform subscriptions + Fuel Forecast gated API" below; gated endpoint and product page are live, but not yet open to real paying customers pending NĐ169 legal review) | `fuel_price_cycle` (Silver — giá điều hành MOIT theo kỳ + giá MOPS, **nguồn duy nhất của model**), `fuel_world_daily` (Silver — Brent/RBOB theo ngày từ Yahoo), `fuel_forecast` (Gold — kịch bản bán cho khách), `fuel_backtest` (Gold — điểm số validation). Mô tả từng cột, đơn vị và dải giá trị: xem "`FUEL_FORECAST_DB` — data dictionary" |

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
| Gold (SJC) | **Two independent crawlers**: 24h.com.vn + giavang.org, cross-checked | `vn_macro_gold_daily` | Hourly 08:00–16:00 VN, **from the box** not Actions |
| Silver | Phú Quý | `vn_macro_silver_daily` | Daily |
| FX Rate | VCB, SBV | `vn_macro_sbv_rate_daily` | Daily |
| CPI | NSO | `vn_gso_cpi_monthly` | Monthly |
| GDP / IIP / Xuất nhập khẩu | NSO monthly & quarterly bulletin | `vn_gso_gdp_quarterly`, `vn_gso_iip_monthly`, `vn_gso_trade_monthly` | Monthly / Quarterly |
| Global | Yahoo Finance (GC=F, SI=F, ^IXIC) | `global_macro` | Daily |
| Fuel (domestic) | Bộ Công Thương price-management announcements | `fuel_price_cycle` | ~Biweekly (cadence changed 2026-08, was weekly Thu) |
| Fuel (world) | Yahoo Finance (BZ=F Brent, RB=F RBOB) | `fuel_world_daily` | Daily (crawled daily, full history re-pulled each run) |
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

### Fuel crawl — MOIT dropped the year from the slug (found + fixed 2026-09-18)

Same silent-freeze shape as 2026-09-08, new cause. From 2026-09-03 MOIT filed the
bulletins under `/tin-tuc/thong-bao/` with **no year in the slug**
(`...-dieu-hanh-gia-xang-dau-ngay-10-9.html`). `_bulletin_url()` only probed
`/tin-tuc/...-ngay-D-M-YYYY.html`, so 2026-09-03, 09-10 and 09-17 were all missed
while `fuel-pipeline.yml` stayed green — `STALE_AFTER_DAYS` was 25 days against a
7-day cadence, so 21 days of silence never paged anyone; it is now **17**. Worse, had the category scan found such a link,
`_period_from_url()` would have `sys.exit`ed on it (no 4-digit year to parse).

**The scheduled fuel crawl runs on the VN box, not in CI (2026-09-19).**
`moit.gov.vn` refuses GitHub runners — three consecutive `fuel-pipeline.yml` runs
logged RemoteDisconnected on the search endpoint, SSLEOFError on one category page
and `[Errno 101] Network is unreachable` on the other, all from a US runner IP. A
run that cannot reach the source can only conclude "no newer cycle", which is
precisely how 09-03, 09-10 and 09-17 were missed while CI stayed green.
`deploy/crawl-fuel.{sh,service,timer}` now does it daily at 16:30 VN (MOIT
announces ~15:00 on the cycle day), mirroring the gold/silver box pattern, and
refits backtest+forecast only when the newest period actually moved.
`fuel-pipeline.yml` stays scheduled as a backstop for when the box is down.

**One writer, one watchdog (restructured 2026-09-19).** The model used to be
recomputed in two places for the same data: `deploy/crawl-fuel.sh` on the box
(only when a new cycle actually landed) and a `model` job in `fuel-pipeline.yml`
(every Thursday regardless). On 2026-09-19 that produced two identical refits
hours apart, and over its life left 23 forecast runs and 22 backtest runs for
roughly a dozen real cycles. Same conclusion this repo already reached for gold
on 2026-09-14 — *"Two writers on the same rows bought nothing."*

- **The box is the only writer.** It crawls MOIT and recomputes `fuel_backtest`
  + `fuel_forecast`, and only when `max(period)` actually moved.
- **`fuel-pipeline.yml` crawls Yahoo, triggers the box, then checks the result.**
  Its `model` job is gone. The new `freshness-check` job runs
  `crawl_tools/check_fuel_freshness.py` with `if: always()`, so it reports even
  when a crawl job failed — "the crawl failed *and* the data is 3 weeks old" is
  the report worth having.
- Schedule moved from `'0 2 * * 4'` (weekly, on a round minute — breaking this
  repo's own GitHub-cron rule) to `'23 2 * * *'` (daily, 09:23 VN).

`check_fuel_freshness.py` asks three things and exits non-zero on any: has a new
cycle failed to appear past `CYCLE_STALE_DAYS` (17); has either world series
stopped advancing past `WORLD_STALE_DAYS` (6); and **was the model actually
rebuilt after the newest cycle** — it compares `fuel_forecast`'s newest
`breakdown->>'last_known_cycle'` against `max(period)` in `fuel_price_cycle`.
That third check is the one nothing else can make: a fresh price cycle with a
stale forecast means the box crawled but the refit failed, and the API would
keep serving forecasts built without the newest cycle. Judgement lives in a pure
`evaluate()` covered by `tests/fuel/test_fuel_freshness.py`.

**Discovery is now search-first, not pattern-first** (the standing decision from
2026-09-16: options 2+3 — a free data source plus search — are how this data gets
found, and that applies to the scheduled crawl, not just one-off backfills).
`discover_new()` queries **MOIT's own site search** (`MOIT_SEARCH_URL`,
server-rendered, no API key) before anything else, so a renamed slug or a new
category no longer hides a cycle; results under `/van-ban-phap-luat/` are skipped
because that mirror is a different document type `moit_parser.py` cannot read.
Category scan and the URL probe stay as fallbacks: the probe still covers every
combination of three category prefixes x three slug templates, **including the
year-less one**. It returns **every** new cycle oldest-first — the old code crawled only the
newest, so any cycle skipped in between was lost for good. A year-less URL keeps
resolving to last year's article, so a hit only counts when the page's own
`article:published_time` meta is the cycle day (or the day after); that meta is
also where a year-less slug gets its year. `_period_from_url()` is kept for
`crawl_tools/backfill_moit_archive.py`, which still parses year-bearing URLs.

Covered by `tests/fuel/test_crawl_moit_discovery.py` (no network).

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

### Fuel price forecasting is a solved market — VPI (found 2026-09-20)

**Viện Dầu khí Việt Nam (VPI)**, a research institute under Petrovietnam,
publishes a fuel-price forecast **before every price-management cycle**, for all
five fuel types, using an artificial neural network with supervised learning. It
is free, and it is carried by VietnamPlus, BNews (TTXVN), PetroTimes, Thời báo
Tài chính, HTV, PVOIL and provincial papers. A transport company needs only to
search for it.

**Measured against our own `fuel_price_cycle` rows** (VPI forecasts collected
from state media, paired with the cycle they targeted):

| Model | E5RON92 MAE | DO005S MAE |
|---|---|---|
| **VPI** | **70** (n=4) | **62** (n=2) |
| `delta-world-v1` — ex-post, *knows* the cycle's MOPS | 199 | 236 |
| `brent-nowcast-v1` — genuine pre-announcement forecast | 513 | 600 |
| Random walk (price unchanged) | 692 | 959 |

VPI is **7–10× more accurate than our pre-announcement model**, and ~3× more
accurate than the ex-post one that gets to see the answer. Individual errors ran
0.03%–1.10%; one was 5 VND/L. Small n, and media may only publish the cycles VPI
got right — but a 7–10× gap is not sampling noise.

**Why they win:** VPI models the stabilisation-fund decision itself ("dự báo …
mức trích lập và chi sử dụng Quỹ bình ổn"), which is precisely the largest
remaining error source for us and the one we cannot address.

**Consequence:** do not position this product as a fuel-price forecast. That
applies to `delta-world-v1` (currently on sale) as well as to any successor.
Two directions survive, because VPI does **not** offer them: a clean queryable
history (117 cycles + the MOPS figure MOIT publishes), and **scoring forecasts
against outcomes** — storing VPI's published forecast each cycle and publishing
how accurate it turned out to be. Nobody does that, VPI included.

**Acquiring VPI's data — checked 2026-09-20, no clean route yet.**
`vpi.pvn.vn` redirects to a Gamma site-builder page: no data portal, no API, no
RSS, no downloads, only `contact@vpi.pvn.vn`. VPI publishes *press releases*,
not data. News articles are reachable and parseable (bnews.vn returns 200 and a
simple regex extracts the figures), and lead time is comfortable — measured
25–45 hours before the cycle across four articles. But: bnews' `/rss/kinh-te.rss`
500s and article URLs carry unguessable numeric ids, so discovery would rely on
search or category scraping — the exact fragility that broke the MOIT crawler
twice in 2026, now with a third party's CMS instead of our source's.

Legally there are three tiers, and only the middle one is clearly settled:
Điều 15 Luật SHTT excludes "tin tức thời sự thuần tuý" from copyright, so the
**figures** are likely usable with attribution; the **article text** is a
copyrighted journalistic work and is not; and **systematic aggregation inside a
paid product** plausibly triggers Nghị định 72/2013's licence for a "trang thông
tin điện tử tổng hợp", which VDV does not hold. Not legal advice — the third
tier needs a lawyer. The clean path is to ask VPI directly; it has not been
tried.

Full analysis: `docs/research/2026-09-19-fuel-model-report.md` and the local
`model.ipynb`.

### `FUEL_FORECAST_DB` — data dictionary (audited 2026-09-19)

Four tables. Two hold **crawled source data** (Silver), two hold **model output**
(Gold). Schema files: `be/fuel/schema.sql` (Silver), `be/fuel/schema_gold.sql`
(Gold). Every table carries the repo-standard `id / period-or-run_ts /
crawl_time / source / group_name` shape described under "Required columns".

---

#### `fuel_price_cycle` — giá điều hành xăng dầu trong nước, theo kỳ

**What it is.** One row per price-management cycle per fuel. This is the
regulated retail ceiling price MOIT sets, together with the world reference
price it used to set it. **It is the only input to the forecasting model.**

**Source.** Bộ Công Thương price-management bulletins, e.g.
`https://moit.gov.vn/tin-tuc/thong-bao/mot-so-thong-tin-ve-viec-dieu-hanh-gia-xang-dau-ngay-17-9.html`
— parsed from prose by `crawl_tools/moit_parser.py`. Raw HTML is archived to
Cloudflare R2 (Bronze) with a sha256 so a parser change can be replayed.
Crawled by `crawl_tools/crawl_moit_fuel.py`, **from the VN box** (moit.gov.vn
refuses GitHub runners).

**Grain.** `(fuel, period)` — UNIQUE. Cadence is set by the regulator and has
changed twice in 2026: weekly Thursday → ~14 days → weekly again.

| Column | Type | Unit / meaning | Observed range |
|---|---|---|---|
| `period` | DATE | Ngày công bố kỳ điều hành (MOIT announces ~15:00 VN) | 2022-01-21 → 2026-09-17 |
| `fuel` | VARCHAR(12) | `E5RON92` (xăng sinh học) or `DO005S` (dầu diesel 0,05S). RON95 dropped 2026-09-15 | 2 values |
| `retail_price` | NUMERIC | **VND/lít** — giá bán lẻ tối đa MOIT ấn định | E5RON92 18.233–31.302; DO005S 16.809–37.899 |
| `world_avg_price` | NUMERIC | **USD/thùng** — bình quân MOPS (Mean of Platts Singapore) của **xăng dầu thành phẩm**, cửa sổ ~7 ngày, do chính MOIT công bố trong bản tin | E5RON92 70,9–149,6; DO005S 76,8–218,9 |
| `source` | TEXT | URL bản tin cụ thể của kỳ đó | moit.gov.vn/… |

**Rows.** 234 = 117 cycles × 2 fuels.

**Do not confuse `world_avg_price` with Brent.** It is refined-product MOPS,
quoted per fuel — on 2026-09-17 it read 141,1 (E5RON92) and 182,6 (DO005S)
while Brent crude closed at 104,8. This is the number inside the regulator's
formula; Brent is not.

`base_price`, `bog_contrib`, `bog_use` and `taxes` were dropped 2026-09-15 for
never having been parsed (`be/migrations/fix_fuel_price_cycle_drop_unused_cols.py`).

---

#### `fuel_world_daily` — giá dầu thế giới theo ngày (hợp đồng tương lai)

**What it is.** Daily settlement prices of two exchange-traded futures, used as
free world-oil-price context. **Not the price in the regulator's formula.**

**Source.** Yahoo Finance via `yfinance` — `BZ=F` (Brent crude) and `RB=F`
(RBOB gasoline). Crawled by `crawl_tools/crawl_fuel_world.py`, daily on GitHub
Actions; each run re-downloads `period="max"` and upserts, so a missed run
self-heals. The crawler exits non-zero past `STALE_AFTER_DAYS` (6) so a frozen
series cannot report success — the shape that kept the MOIT table green for two
months.

**Grain.** `(instrument, period)` — UNIQUE, weekdays only.

| Column | Type | Unit / meaning | Observed range |
|---|---|---|---|
| `period` | DATE | Trading day | BRENT 2007-07-30, RBOB 2000-11-01 → 2026-09-18 |
| `instrument` | VARCHAR(12) | `BRENT` (dầu thô Brent) or `RBOB` (xăng kỳ hạn Mỹ). `SGGO` (Singapore Gasoil, the true diesel benchmark) is a stub — needs a licensed ICE/CME feed | 2 values |
| `close` | NUMERIC | **BRENT: USD/thùng. RBOB: USD/gallon** — units differ per instrument, validated against per-instrument bounds in `crawl_fuel_world.py` | BRENT 19,33–146,08; RBOB 0,41–4,28 |

**Rows.** 11.265 = 4.764 BRENT + 6.501 RBOB. One calendar gap > 5 days.

**The window was `"2y"` until 2026-09-19**, an arbitrary limit of ours that
started the table at 2024-07-12 while `fuel_price_cycle` goes back to
2022-01-21 — so only 74 of 117 cycles had world-price features. Widening it
also forced the validation bounds open: the old floors (Brent 20,0 / RBOB 0,5)
rejected the **real** April-2020 COVID crash (Brent settled 19,33 on 2020-04-21,
RBOB 0,41 on 2020-03-23), and because `validate()` is all-or-nothing those five
genuine rows discarded the entire backfill. Do not narrow the bounds back to
whatever the recent window happens to span.

**History.** It fed `structural-v1` (Brent → MOPS → Nghị định 80 formula),
deleted 2026-09-10 for losing to random walk. A 2026-09-19/20 experiment found a
*different* framing does work: the cycle-over-cycle change in the Brent 7-day
window average, observed **before** the announcement, beats random walk on
Δretail — walk-forward n=91, skill +0.265 (E5RON92) and +0.379 (DO005S),
Diebold-Mariano p=0.003 and p<0.0001, directional accuracy 84% and 89%.
**Do not reinstate the old level-on-level framing.**

Three things bound how far that result can be taken, and all three are settled:

- **It is nowcasting, not forecasting.** Skill decays 0.26 → 0.10 → 0.02 → −0.01
  across 1 to 4 cycles ahead and is gone at one month; a monthly-horizon model
  loses to random walk outright. It works because the MOPS reference window is
  nearly complete by the time the forecast is made — exactly what
  `docs/research/2026-07-10-fuel-forecast-feasibility.md` §3.2 predicted.
- **XGBoost loses to one-feature OLS** on both fuels. At 115 observations,
  depth-3 trees score negative skill. Tested four configurations before
  concluding this.
- **VPI already does it far better, for free** — see "Fuel price forecasting is
  a solved market" below.

Nothing in production consumes this table.

---

#### `fuel_forecast` — kịch bản dự báo bán cho khách (Gold)

**What it is.** The product output. Not a point forecast: each row is a
**world-conditional scenario** — "if the world price moves by X, retail moves by
k·X". `base` always equals the last known retail price unchanged.

**Written by** `be/fuel/forecast.py`; **read by** `be/routers/fuel_forecast.py`.

**Grain.** `(run_ts, fuel, target_cycle, scenario)` — UNIQUE. One `run_ts` per
refit; 23 runs stored, kept as history rather than overwritten.

| Column | Type | Unit / meaning |
|---|---|---|
| `run_ts` | TIMESTAMP | When the forecast was generated. Latest run is the one served |
| `target_cycle` | DATE | Kỳ điều hành được dự báo |
| `horizon` | INT | 1–4 cycles ahead |
| `scenario` | VARCHAR(6) | `low` / `base` / `high` — the 80% world-shift band |
| `point`, `lo`, `hi` | NUMERIC | VND/lít |
| `breakdown` | JSONB | `k_vnd_per_usd_bbl`, `sigma_world_usd_bbl`, `resid_std_vnd_l`, `cycle_days_used`, `last_known_cycle/retail`, `assumed_world_delta_usd_bbl`, `bands` (50/80/95% nested fan), `disclaimer`. Free tier receives only `disclaimer` |
| `model_version` | VARCHAR(40) | `delta-world-v1` (216 rows) — plus **336 stale `structural-v1` rows from 2026-07-12→09-10**, kept as history of a deleted model. Always filter by `model_version` or by latest `run_ts` |

---

#### `fuel_backtest` — điểm số validation của model (Gold)

**What it is.** Walk-forward accuracy of the model, recomputed every time a new
cycle lands. Each row is a snapshot of how the model scored at that moment with
the data it had — **it cannot be reconstructed after the fact**, which is why
this table is kept even though it is small.

**Written by** `be/fuel/backtest.py`; **read by** `be/routers/fuel_forecast.py`
(the `validation` block in the API response, since 2026-09-19).

**Grain.** `(run_ts, fuel, horizon, model_version)` — UNIQUE. 22 runs stored.

| Column | Type | Unit / meaning |
|---|---|---|
| `mae`, `rmse` | NUMERIC | VND/lít |
| `coverage` | NUMERIC | Tỉ lệ kỳ thực tế rơi trong khoảng [lo, hi]. Nominal ~80%, measured 0.87–0.89 |
| `n` | INT | Số điểm kiểm định walk-forward (currently 111) |
| `skill_vs_rw` | NUMERIC | `1 − MAE/MAE_randomwalk`, algebraically `1 − MASE`. 0 = ties random walk |
| `model_version` | VARCHAR(40) | `delta-world-v1` (42 rows), `structural-v1` (28 stale rows) |

**These numbers are ex-post, and the API says so.** `walk_forward_delta` feeds
the model the `world_avg_price` MOIT publishes *in the same bulletin* as the
retail price, so `skill_vs_rw` measures how mechanical the regulator's formula
is — not how well anything is predicted before an announcement. The API returns
`conditioning: "ex_post"` alongside the figures and the page labels the tile
accordingly. Until 2026-09-19 the page carried these as hardcoded JavaScript
constants that had already drifted from the table; **never reintroduce a typed
copy of a number this table computes.**

---

#### Dropped

**`fuel_formula_params`** (dropped 2026-09-19) held Nghị định 80 tax/fee
parameters for `structural-v1`. Zero rows from the day it was created, no code
ever read or wrote it. `be/fuel/schema.sql` keeps a comment where it stood.

## GitHub Actions Workflows

`.github/workflows/` — one workflow per crawl source (`{asset}-crawl.yml`), plus `build-html.yml` (regenerates `fe/index.html` on `fe/partials/` change), `generate-static-data.yml`, `data-quality-check.yml`, `market-pulse.yml`, `deploy.yml` (auto-deploy to prod), and `uptime-check.yml`.

`uptime-check.yml` runs daily at 11:00 VN and is the **only** production alerting we have: it probes prod from outside the box (root page + body size, `www`, `api`, anonymous `/gold` still 401, the three SEO root files, and cert expiry with a 14-day warning). A failure turns the workflow red and GitHub emails the repo owner. It must stay off-box — an on-box cron dies with the box it watches. Added after a 31h TLS outage went unnoticed (`DEPLOY.md`).

Cron in VN time (UTC+7): `'7 1 * * *'` = 08:07 VN. Standard steps: checkout → setup-python → `pip install -r crawl_tools/requirements.txt` → `python crawl_tools/crawl_{source}.py` with DB env from secrets.

**Never schedule a crawl on `:00` or `:30`.** GitHub runs scheduled workflows at low priority on shared runners and delays or drops them under load, and the round minutes are the congested slots. Measured 2026-08-09 on the old `'30 1'` + `'30 2-9'` gold/silver schedule: the 01:30 UTC primary slot *never fired at all* (first run of the day landed 03:04–04:38 UTC), only 4–8 of the 9 declared runs materialised, and the runs that did fire started **32 min late on average, 58 max**. Result: the day's gold data reached the DB at 10:00–12:40 VN instead of 08:30 VN, every day, with GitHub healthy. Daily crawlers now sit on distinct odd minutes so they neither hit a congested slot nor collide with each other: gold/silver `7`, termdepo `13`, exchange-rate `17`, SBV `23`, VN30 ratios `27`. **Gold/silver is no longer scheduled here at all** (2026-09-14): GitHub runners time out reaching `24h.com.vn` and GitHub dropped every declared slot that day, so the crawl moved to a systemd timer on the prod box — see "Box-side gold/silver crawl" below. `gold-silver-crawl.yml` keeps `workflow_dispatch` only.

### Box-side gold/silver crawl (`deploy/crawl-fallback.*`) — PRIMARY path since 2026-09-14

**This section said "INACTIVE, never re-provisioned on the new box" until 2026-09-14. That was wrong, and it cost a day of debugging.** The DB showed gold and silver rows written at `01:45:32`/`01:45:25` UTC on 2026-09-14 — a day GitHub ran the crawl workflow zero times — matching the timer's `OnCalendar=01:45 UTC` exactly. The timer had been running on the BKHOST box the whole time. `systemctl list-timers 'crawl-fallback*'` on the box beats anything written here; check it before trusting this paragraph.

**It is now the primary and only scheduled crawler for gold/silver.** `gold-silver-crawl.yml` keeps `workflow_dispatch` alone, for manual use when the box is down. Two writers on the same rows bought nothing.

Why the box won:

- **Network.** GitHub's runners sit outside Vietnam. The 2026-09-13 run failed with a connect timeout to `www.24h.com.vn`, and `nso.gov.vn` refuses foreign datacenter IPs outright — the reason prod itself moved to a VN box on 2026-09-04. This box reaches both sources without trouble.
- **Scheduling.** GitHub's cron is best-effort: it dropped every declared slot on 2026-09-14, and measured 2026-08-09 it fired only 4–8 of 9 daily runs, 32 min late on average (58 max). systemd fires on time, so the odd-minute trick (`:07`) is unnecessary here — the timer uses round hours.

**Cadence: hourly across VN office hours** (nine passes, 01:00–09:00 UTC = 08:00–16:00 VN), and **every run upserts**. There is deliberately no "skip if today's row exists" guard: that guard existed in three places at once (crawler, workflow, this script) and together they pinned the published price to the ~08:45 VN quote for 75 days while SJC moved several times a day. See "Gold is SJC-only" below.

**Each successful run also regenerates `fe/data/*.json`** into the directory FastAPI serves. The charts read those files, not the DB, so without this a fresh row would stay invisible until `generate-static-data.yml`'s 6-hourly backstop. The crawl mounts the repo read-only; the regeneration step adds a narrow writable mount for `fe/data` only.

**Two things had to change before that regeneration was actually visible** (both found 2026-09-14, after the DB was already correct and the site still showed the old price):

- `Dockerfile` does `COPY fe/ /app/fe/`, so the container served a build-time snapshot and ignored host-side writes entirely. `docker-compose.yml` now mounts `./fe/data:/app/fe/data:ro` over it.
- `deploy.yml`'s `git reset --hard` reverts `fe/data/` to the committed copy — as fresh as the last "Update static chart data" bot commit and no fresher — so a deploy rolled published prices *backwards*. The deploy now ends by running `crawl-fallback.service` synchronously, leaving current data in place when it finishes.

**`gh workflow run "Box — run gold/silver crawl now"`** (`.github/workflows/box-crawl-now.yml`) runs the unit on demand and prints its journal, using the deploy key GitHub already holds. It exists because moving the crawl to the box otherwise left no way to trigger a run or read its log without SSH.

Two things to preserve when touching it:

- **Success is "did every writer's `crawl_time` move", not "does today have a row" and not the exit code.** Two independent reasons. (1) `crawl_gold_silver.py` exits 1 whenever its Yahoo Finance section fails, and Yahoo blocks index tickers from datacenter IPs — which the box has; that non-zero exit is routine and says nothing about the domestic crawl. (2) A crawler can exit 0 having written nothing. The script therefore probes `MAX(crawl_time)` per writer (`24h.com.vn`, `giavang.org`, silver) before and after the run and compares the two — no clock arithmetic, so container/box timezone drift cannot fake freshness. Row-presence was the old test and it reported green all afternoon on a source that had died at 08:00; with two SJC sources writing hourly that is precisely the failure the second source exists to expose. A writer that did not advance turns the unit red *after* the static JSON is regenerated, since a degraded run still has fresher data than no run.
- **The two SJC crawlers' exit code is tracked separately from `crawl_gold_silver.py`'s** (`sjc_rc` vs `crawl_rc`). The SJC crawlers exit non-zero only on an implausible quote or a cross-source disagreement; folding them into one number let Yahoo's daily failure explain away a real one.
- **`bash deploy/crawl-fallback.sh --self-test`** exercises the freshness judgement against canned probe output — no DB, docker or `.env` needed, so it runs on the box and in CI (`crawl-tests.yml`). It is the only way to prove the "a source died" branch without breaking a source on purpose.
- **It runs in `python:3.11-slim` (`deploy/crawler.Dockerfile`), not on the box Python.** The box ships Python 3.14 with no `python3-venv`, while `crawl_tools/requirements.txt` pins 3.11-era versions. The image installs only the subset `crawl_gold_silver.py` imports, version-pinned by passing `crawl_tools/requirements.txt` to pip as a *constraint* file, so it stays in lockstep with CI without a duplicate dependency list. The repo is bind-mounted at `/repo`, so deploys refresh crawler code without an image rebuild.

**Changing the `.timer`/`.service` needs a box-side step** — a deploy only lands the files. `systemctl daemon-reload && systemctl enable --now crawl-fallback.timer`; full steps in `DEPLOY.md`.

This does **not** change the rule that `uptime-check.yml` must stay off-box — a watchdog cannot live on the machine it watches, whereas a crawler legitimately can.

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
/api/v1/subscriptions/*      # platform (VDV-owned) subscriptions — wallet-billed
/api/v1/fuel-forecast/{fuel} # Fuel Forecast product, gated by subscription
```

Open-data routes under gold/silver/SBV/term-deposit/global/VN30/macro are gated in `be/main.py`: anonymous or invalid credentials return `401`, while free and paid API keys and valid FE Bearer sessions are metered. Public `gold-analysis` / `market-pulse` calls and rejected metered calls are tracked without storing IP, token, raw API key, or user-agent. Admin performance reporting at `/pages/admin.html` supports `24h`, `7d`, and `YTD` periods.

`/pages/admin.html` (Auth0 login + `is_admin`/`user_level='admin'`, backed by `/api/v1/admin/*` with `admin_audit_log`) is the **only** admin/reporting surface. The secret-link report `GET /api/v1/report?key=<REPORT_SECRET>` (`be/routers/report_dashboard.py`) was removed on 2026-08-06: it duplicated data the admin dashboard already showed, put a credential in the URL (Caddy access logs, browser history, `Referer`), had no per-person revocation or audit trail, and fell back to `WEBHOOK_INTERNAL_SECRET` — the same secret GitHub Actions sends on every crawl webhook. Do not reintroduce secret-in-URL admin surfaces; add new reporting as an `/api/v1/admin/*` endpoint plus a section in `admin.html`.

### Platform subscriptions + Fuel Forecast gated API (2026-09-10)

Generic wallet-billed subscription primitive for VDV-owned "platform" data
products — deliberately separate from the Knowledge Market's seller-listing
model (`knowledge_products`, 90/10 split via `seller_earnings`): a platform
product has no seller and no one-time-purchase shape, so it gets its own
tables instead of bending the marketplace schema. Design doc:
`docs/superpowers/specs/2026-09-10-fuel-forecast-subscription-design.md`.

**Tables — `KNOWLEDGE_MARKET_DB`, not `FUEL_FORECAST_DB`.** This is the one
mix-up to watch: the *feature* being sold is fuel-price forecasting, but the
*billing* rows live with the wallet, on the same DB as `credit_balance`/
`credit_ledger` (`be/migrations/013_platform_subscriptions.sql`), so a
subscription write and a wallet debit share one transaction.

- `platform_products` — catalog, one row today: `fuel-forecast-advanced`,
  `price_credits=60`, `list_price_credits=120` (struck-through "50% launch
  discount" display), `billing_period_days=30`.
- `platform_subscriptions` — one row per `(user_id, product_code)`
  (`UNIQUE` constraint — re-subscribing after cancel reuses the row instead
  of inserting a second one), `status` in `active`/`past_due`/`cancelled`,
  `current_period_end`, `grace_until`, `cancel_at_period_end`
  (migration 015, `NOT NULL DEFAULT false` — see the cancellation semantics
  below).
- `platform_subscription_events` — append-only log (`created`/`charged`/
  `charge_failed`/`past_due`/`cancel_scheduled`/`cancel_undone`/`cancelled`/
  `reactivated`), the source for the
  FE's billing-history card. Deliberately not derived from `credit_ledger`:
  a failed/insufficient-balance renewal attempt is a real, user-relevant
  event that never touches the ledger (no money moved), so it would be
  invisible there.
- Migration 014 (`014_credit_ledger_subscription_kind.sql`) widened
  `credit_ledger`'s `CHECK` constraint to allow `kind='subscription_charge'`
  — a pre-existing gap found while wiring the debit path, not part of the
  original 013 migration.
- Migration 015 (`015_cancel_at_period_end.sql`, `run_015.py`) added
  `platform_subscriptions.cancel_at_period_end`. Applied to the dev
  `KNOWLEDGE_MARKET_DB` 2026-09-12.

**Cancellation takes effect at the end of the paid period, not immediately**
(product decision, 2026-09-12). `cancel_subscription()` sets
`cancel_at_period_end = true` and writes a `cancel_scheduled` event; `status`
and `current_period_end` are untouched, so access continues normally and
`has_active_subscription()` keeps returning `True` until the period really
ends. `run_billing_cycle` then takes the new `expire` action at that point
(`status='cancelled'`, event `cancelled`) instead of attempting a charge —
and does so regardless of balance, so an empty wallet can't turn a requested
cancellation into `past_due`. Still no proration and no refund, in either
direction. The one case that cancels **immediately** is a subscription with
no paid time left to honour (`past_due`, or `active` with a
`current_period_end` already in the past): neither grants access today, and
scheduling a `past_due` row would leave it eligible for the cron's
reactivation charge — i.e. billing someone who just asked to stop.
`POST /subscribe` doubles as the undo: on an active row that is scheduled to
cancel it clears the flag, writes `cancel_undone` and **charges nothing**
(that period is already paid for), returning `charged: false`.

**`be/services/subscription.py`** — `subscribe()`, `cancel_subscription()`,
`has_active_subscription()`
(pure lookup, `user_id=None` short-circuits to `False`, used for gating),
`list_subscription_history()`, `run_billing_cycle()`. The billing cycle fetches
every `active`/`past_due` subscription id in one query, then processes each in
its own short transaction (`_decide_renewal` branches per-row on its current
`status`) rather than one big transaction — a stuck or failing row is caught,
logged, and skipped, so it can't block every other renewal: renewals due get
charged and extended by `billing_period_days` from the existing `current_period_end`
(on-time renewal doesn't lose time); a failed renewal goes `past_due` with a
**2-day grace period** (`GRACE_PERIOD_DAYS`, was 3 until 2026-09-12), retried
daily — if the balance
recovers within the grace window the subscription reactivates from *now*
(a late payment buys a fresh 30 days, it does not backdate), and if grace
expires still unpaid it's auto-cancelled. A shortfall that's still within
grace is a silent no-op on retry (no repeated `charge_failed` spam — the
first failure already recorded the start of it).

**`be/routers/subscription.py`**, mounted at `/api/v1/subscriptions`:

```
GET  /api/v1/subscriptions/plans              — list platform_products (public)
GET  /api/v1/subscriptions/me                 — current user's subscription rows (auth)
POST /api/v1/subscriptions/subscribe {product_code} — subscribe / reactivate / undo a scheduled cancel (auth)
POST /api/v1/subscriptions/cancel   {product_code} — schedule cancellation at period end (auth)
GET  /api/v1/subscriptions/history?limit&offset — event history, this user only (auth)
```

**`be/routers/fuel_forecast.py`**, mounted at `/api/v1/fuel-forecast`:

```
GET /api/v1/fuel-forecast/{fuel}   fuel in {RON95, E5RON92, DO005S}
```

Auth is **optional** here (`middleware.authenticate_user_optional`, the
`reports.py` pattern) — unlike `wallet.py`/`subscription.py`'s required-auth
endpoints, the free tier must work for an anonymous visitor.
`has_active_subscription(user_id, 'fuel-forecast-advanced')` decides the
response shape: without an active subscription, history + `base` scenario
only, with `breakdown` stripped down to just the `disclaimer` field (no
`k`/`resid_std`/`sigma_world` — that model detail is the paid value); with
one, all three scenarios and the full breakdown. The response body itself
carries a `tier: "free"|"advanced"` field, so the FE never needs a separate
"am I subscribed" check to decide what to render.

This endpoint reads only `fuel_price_cycle` and `fuel_forecast` (via
`get_engine_fuel()`) — **`fuel_world_daily`/Brent-RBOB stay unused here too**,
consistent with the "zero consumers" note in "Fuel forecast model" above;
nothing in this feature reopens the Brent/RBOB proxy that `structural-v1`
already showed doesn't work.

**Daily billing cron**: `.github/workflows/subscription-billing.yml`,
`'11 3 * * *'` (10:11 VN, an odd non-`:00`/`:30` minute per this repo's own
GitHub Actions scheduling rule), runs
`python be/services/subscription.py --run-billing-cycle`. **Not yet merged
as of 2026-09-11** — blocked on the `KNOWLEDGE_MARKET_DB` GitHub repo secret
not existing yet (`gh secret list` confirmed); until it's added and the
workflow file committed, subscriptions do not auto-renew or auto-expire on
their own — `subscribe`/`cancel` work, but nothing calls `run_billing_cycle`
except a manual `workflow_dispatch` or local invocation.

**Fan chart (2026-09-18)** — `make_forecast_rows` also writes
`breakdown.bands`: the 50/80/95% world-shift quantiles per horizon, from the same
`z * sigma_world * sqrt(h)` formula as the low/high scenarios (`z` now defaults to
the exact 80% quantile so the 80% band *is* low/high, not a near-copy). The page
draws them as nested bands; it never recomputes model maths in JS. Levels are
nominal under the random-walk-on-world assumption — walk-forward coverage of the
80% band measured 88-90%, i.e. wider than advertised. The chart uses a **real time
axis** (cycles run 7-14 days apart) and defaults to a 3-month window, since the fan
is only ~4 weeks wide and a longer window squeezes it into a sliver; 6 tháng /
1 năm / Tất cả are one click away. The free tier's lock overlay now covers **only
the forecast zone** — published history stays sharp, and the backend still sends no
band numbers to free callers, so the lock hides nothing it does not also withhold.

**`fe/pages/fuel-forecast.html`** — the product page: real
`fetchWithAuth('/api/v1/fuel-forecast/{fuel}')` calls, a lock overlay for
the free tier whose CTA posts to `/subscriptions/subscribe`, and a
"Lịch sử thanh toán" card (shown once `GET /subscriptions/me` returns a row
for this product) rendering `GET /subscriptions/history` with Vietnamese
event labels: `created`→"Đăng ký mới", `charged`→"Gia hạn thành công",
`charge_failed`→"Không đủ số dư — vào grace period",
`cancel_scheduled`→"Đã lên lịch huỷ (hết kỳ hiện tại)",
`cancel_undone`→"Tiếp tục dùng — đã huỷ lịch huỷ", `cancelled`→"Huỷ",
`reactivated`→"Kích hoạt lại".

`GET /subscriptions/me` is fetched once into `state.sub` and drives two
things, so exactly one call-to-action is on screen at a time:

- **`#sub-bar`**, shown only while `status='active'` and the period is still
  running — "tự động gia hạn ngày X" + a "Huỷ đăng ký" button, or, once
  `cancel_at_period_end` is true, "Đã lên lịch huỷ — … tới hết ngày X" +
  "Tiếp tục dùng" (which POSTs `/subscribe`, the no-charge undo).
- **the lock overlay's copy**, which has three variants: never subscribed
  (sell the plan), `past_due` (failed renewal — top up, auto-retry within 2
  days, or retry now via `/subscribe`), and expired `active` (renew).

Dates from `/me` arrive as `json.dumps(default=str)` output
(`"2026-10-12 03:11:00.123456"` — naive, space-separated, no zone marker,
unlike `/history`'s explicit ISO-8601 `…Z`), so the page reads the
`YYYY-MM-DD` prefix as text rather than through `new Date()`, which would
read it as local time and can shift the displayed day.

### Auth identity resolution — one account, several Auth0 logins (2026-09-17)

`users.email` and `users.auth0_id` are both UNIQUE, and every router finds the
caller with `WHERE auth0_id = :aid` on `request.state.user["auth0_id"]`. A person
who signed up with email/password (`auth0|…`) and later logs in with Google
(`google-oauth2|…`) therefore had no row for the second identity: `/auth/me`
crashed trying to insert a duplicate email, `/subscriptions/me` returned 404, the
fuel forecast served the free tier. Found when `findatasolution@gmail.com` (admin,
active subscription) saw the lock overlay.

**`be/services/identity.py` `resolve_identity()` is now the only way the three
auth entry points in `be/middleware.py` (`_auth_via_bearer`, `authenticate_user`,
`authenticate_user_optional`) map a token to a user**, and they put the row's own
`users.auth0_id` into `request.state.user` — so no router needed changing. Order:
`users.auth0_id` → `user_identities` (migration 017, USER_DB) → claim an account
that has **no** identity yet (e.g. guest checkout) only when Auth0 `/userinfo`
says this identity's email is verified. Unknown subjects are negative-cached 5 min
to stay under Auth0's `/userinfo` rate limit.

**Never auto-merge into an account that already has an identity.** Whoever
registered that email first may never have proven they own it (account
pre-hijacking), and `users.email_verified` is unreliable (always `false` for rows
created by `/auth/me`). `/auth/me` and `/auth/callback` now return **409** for that
case instead of crashing. Link manually after confirming the person owns both:

```sql
INSERT INTO user_identities (auth0_sub, user_id) VALUES ('google-oauth2|…', <user_id>);
```

This also closed a privilege-escalation hole: `authenticate_user` used to fall back
to `SELECT user_level, is_admin FROM users WHERE email = <token email claim>`
without any verification, so a self-registered unverified login claiming an admin's
email got `is_admin=true` on the request. It also stored `user_level` in `user_id`.

### GA4 Reporting API (2026-09)

`admin_dashboard` (`be/routers/admin.py`) now returns a `website_traffic` field (active users, pageviews, sessions, new users for the selected `24h`/`7d`/`ytd` period) sourced from GA4 property `522974314` via `be/core/ga4.py`. Site-side `gtag.js` tracking (`fe/partials/_layout_head.html`, two Measurement IDs `G-YB3PKHN2E5`/`G-B9BHYSYDES` — both data streams under this one property) already existed; this adds server-side *read* access so the number shows up in `admin.html` instead of requiring a manual login to analytics.google.com.

**Auth is a personal OAuth refresh token, not a service-account key.** The GCP project (`vietdataverse`, under Cloud org `findatasolution-org`) has the org policy `iam.disableServiceAccountKeyCreation` enforced at the organization level; overriding it at the project level still failed (a second, "managed" version of the same constraint applies in parallel), and chasing an org-admin override was more friction than it was worth for a single read-only integration. The working path instead: an OAuth 2.0 **Desktop app** client (`Google Auth Platform → Clients`, consent screen in **Testing** mode with the operating Google account added as a test user) + a one-time local `InstalledAppFlow.run_local_server()` browser consent, scope `analytics.readonly`. The resulting refresh token does not expire on its own (only if access is revoked in the Google Account or the OAuth client is deleted) and is stored as 4 env vars, never as a file: `GA4_PROPERTY_ID`, `GA4_OAUTH_CLIENT_ID`, `GA4_OAUTH_CLIENT_SECRET`, `GA4_OAUTH_REFRESH_TOKEN` (see `.env.example`). If the refresh token is ever revoked, redo the one-time consent flow (`InstalledAppFlow.from_client_secrets_file(...).run_local_server(port=0)`, scope `https://www.googleapis.com/auth/analytics.readonly`) logged in as an account with at least Viewer access on the GA4 property, then update the 4 env vars — do not re-attempt the service-account route without first confirming the org policy has changed.

`ga4.get_traffic_summary(period)` maps `24h`→`yesterday..today`, `7d`→`7daysAgo..today`, `ytd`→ Jan 1 of the current year..today (GA4's relative-date strings, not the SQL `_REPORT_PERIODS` intervals used elsewhere in the same endpoint — GA4 doesn't support an arbitrary trailing-24-hours window without an hour-level dimension, so `24h` is approximated as "yesterday plus today so far"). The call sits outside the endpoint's `with get_engine_user().connect()` block (a network call has no reason to hold a DB connection open) and is wrapped in try/except so a GA4 hiccup degrades to `{"error": ...}` rather than 500ing the whole dashboard.

### 1s Pulse API status

`GET /api/v1/market-pulse` currently reads `ARGUS_FINTEL_DB.mri_analysis`. It supports only `lang` and `limit` (maximum 50); it does not yet provide pagination, total count, time/source/label/MRI filters, or an official stable response contract.

**Access is now two-tiered by caller, fixed 2026-09-16** — this endpoint has two audiences reading it, and only one is gated:
- **The site's own "1s Pulse" page** (`fe/app.js` `_doPulseFetch`) calls it with a Bearer token or no header at all — this path (`request.headers.get("X-API-Key")` absent → `authenticate_user_optional`) stays **fully public**, unchanged, for every visitor. This is a core Open Data product surface, not the Developer API — do not gate it without a separate, deliberate product decision.
- **A third-party caller presenting `X-API-Key`** (the Developer API) now genuinely requires `premium_developer`/admin — `be/routers/analysis.py` checks tier explicitly and returns `403` for a free-tier key, matching what `developer.py`'s `/endpoints` catalog has always documented (`access: "premium_developer"`, `403` error code). Before this fix the catalog entry was aspirational only — any key, free or paid, got `200`. Treat `BACKLOG.md` item `API-06` as the source of truth for the endpoint's remaining product-shape gaps (pagination, filters, response contract) — the tier-access half of that item is now done.

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
- **Three blocks are overview-only and must be toggled by hand** (2026-09-16):
  `#market-overview-panel`, `.ticker-strip` (the six at-a-glance cards — SJC gold,
  Phú Quý silver, ACB 12M, SBV overnight/3M, USD/VND) and `#global-ticker-band`
  (NASDAQ / S&P 500 / Dow / world gold / world silver). All three sit **outside**
  `.ov-root` and `.chart-section-group`, so the routing's class toggling never
  reaches them — `ovShowChartDetail()` sets `hidden` on them and `ovShowOverview()`
  clears it, via `ovTickers()` in `app.js`. They stay on the overview and disappear
  on any chart detail: a detail view is the one chart the visitor opened
  deliberately, and six unrelated tickers above it push it below the fold.
  `[hidden] { display: none !important; }` at the top of `style.css` is what makes
  the attribute win against these blocks' own `display` rules — don't remove it.
  **The hero (`.data-hero`) deliberately stays visible on detail views** (product
  decision, 2026-09-16) — only the ticker blocks and the panel are hidden.

### Brand assets (`fe/images/`) — self-hosted since 2026-09-16

Every favicon / app icon / social card is generated from **one source file,
`logo.png` at the repo root**, by `python fe/tools/make_icons.py`. Re-run it after
replacing that file and commit the regenerated PNGs — nothing regenerates them
automatically.

| File | Size | Consumers |
|---|---|---|
| `favicon-16x16.png` | 16 | `<link rel=icon>` in `_layout_head.html` + every `fe/pages/*.html`; Excel add-in `Icon.16x16` |
| `favicon-32x32.png` | 32 | same, 32px slot; Excel add-in `IconUrl` / `Icon.32x32` |
| `icon-80.png` | 80 | Excel add-in `HighResolutionIconUrl` / `Icon.80x80` |
| `apple-touch-icon.png` | 180 | iOS home screen; `manifest.json` |
| `icon-192.png` | 192 | `manifest.json`; the header brand mark (`.app-brand-icon` img) |
| `icon-512.png` | 512 | `manifest.json`, `msapplication-TileImage`, JSON-LD `logo`, `sitemap.xml` `image:loc` |
| `og-card.png` | 1200×630 | `og:image` / `twitter:image` in `_layout_head.html` and `pages/pricing.html` |

Three things to know before touching these:

- **They were on ImageKit until 2026-09-16** (`ik.imagekit.io/o2u9hny2s/vietdataverse/…`).
  Nothing references that CDN any more. Swapping the logo no longer needs a CDN
  upload, but it does need a deploy, since `deploy.yml` git-resets the box.
- **`og-card.png` is NOT a square copy of the logo, and is not named `logo.png`.**
  `_layout_head.html` declares `og:image:width=1200` / `height=630`, so a square
  image gets letterboxed or centre-cropped by scrapers; the generator composes the
  mark on the site surface colour at exactly that size. And `.gitignore` carries a
  bare `logo.png` rule ("stray assets — keep OUT of this PUBLIC repo") that matches
  at **any** depth — an `fe/images/logo.png` would silently never be committed and
  would 404 in production. The root `logo.png` predates that rule and is tracked.
- **Reference them as `/fe/images/…`, never `../images/…`.** Standalone pages are
  reachable at both `/fe/pages/x.html` and `/pages/x.html`, and a parent-relative
  path resolves differently on each — the same trap that killed `../auth.js` (see
  "Where production actually serves from"). Absolute-URL contexts (og/twitter,
  JSON-LD, manifest, sitemap, Excel add-in manifest) use
  `https://vietdataverse.online/fe/images/…`.

`fe/tools/make_icons.py` needs Pillow. It is an authoring-time tool — not loaded by
the browser, not run by CI — so the "FE is zero-dep" rule is unaffected.

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

**One exception to "no dual axes," added 2026-09-22: the domestic gold/silver
detail charts (`fe/app.js` `parseGoldSilverData`) overlay the matching world
price (`fe/data/global_{period}.json`'s `gold_prices`/`silver_prices`) on a
second, right-hand axis in its own real unit (USD/oz), left axis unchanged
(VND/lượng).** This is not the banned case: the "no dual axes" rule stops two
*different* commodities sharing one rebased axis, because it implies a
correlation the data never showed. Here it is the *same* metal in two markets,
and the domestic/world gap is exactly the number VN readers look for ("giá
vàng trong nước cao hơn thế giới bao nhiêu") — a real-unit second axis states
that gap directly; rebasing both to an index here would hide it, the opposite
of what rebasing did for the legitimately-different gold-vs-silver case above.
Fetched by `fetchWorldOverlay()`, best-effort and separate from the domestic
fetch — a failure (e.g. anonymous + `period=all`, which 401s the same as the
domestic gold/silver `all` period already does) degrades to no overlay line,
never blocks the primary chart. Plotted as `{x,y}` points rather than an array
aligned to the domestic `dates`, since the world series (Yahoo, weekdays only)
and the domestic series don't share a calendar; tooltip interaction is
`mode:'nearest', axis:'x'` rather than `'index'` for the same reason — `'index'`
assumes datasets share array positions, which two differently-sampled
time series don't.

### LBMA gold forecast survey — aggregate only (2026-09-22, redesigned twice same day)

The domestic gold chart draws **3 dashed rays** — high/average/low — from the
world price's latest actual point out to a year-end target, using LBMA's
latest professional-analyst gold price forecast. **Aggregate statistics only
(avg/high/low/n_analysts), never the per-analyst listing.**

**Two redesigns, same day, both from direct user feedback:**

1. The first version was a standalone mixed bar+scatter mini-chart below the
   main chart (`.lbma-survey-panel`, `renderLbmaSurvey()`) — it rendered
   empty in practice (Chart.js's `indexAxis:'y'` bar controller and a
   `type:'scatter'` dataset don't share a compatible category/linear y-scale
   without extra configuration neither dataset declared), and was confusing
   even when it did render: a user looking at it couldn't tell whether the
   two dates were publish dates or which period each forecast covered.
   Replaced with a single flat dashed reference line on the gold chart's
   `yWorld` axis, at the latest report's average — same pattern as the SBV
   policy rate overlaid on the interbank chart.
2. The user then asked for something more specific: connect *today's* price
   to the *forecast's* high/average/low, rather than one flat level. That is
   the current design — 3 rays fanning from `(latest world date, latest world
   price)` to `(year-end of the survey's target year, high|avg|low)`.

**Only the latest report is drawn, never all of them stacked.** Every render
picks the row with the max `published_date` from
`fe/data/lbma_gold_survey.json` — so when `crawl_lbma_gold_survey.py` finds a
newer report, the rays update on the next page load automatically. There is
no separate "refresh" step. Each ray's label/tooltip names which one it is
(cao nhất/trung bình/thấp nhất) and the period it forecasts (`annual` → "TB
cả năm {year}", an annual average, not a point estimate; `midyear` → "cuối
năm {year}", an explicit year-end target — both anchored at Dec 31 of
`survey_year` as the chart's one necessary endpoint either way, with the
label preserving which framing the source actually used). The high/low rays
are hidden from the legend (`_lbmaLegend: false`, filtered in
`plugins.legend.labels.filter`) to avoid 3 near-identical coral entries
crowding it; all 3 still tooltip normally. **Tooltip text is deliberately
short** — `Dự đoán LBMA (cao nhất) cho cuối năm 2026: 5.100 USD/oz`, no
analyst-count/publish-date parenthetical; a user found the first version
("khảo sát 16 chuyên gia, công bố 11/08/2026") too busy for a hover box.

**Only rendered on `1y`/`all`, not `7d`/`1m`.** This chart is otherwise
purely historical — dates never extend past "today" — so showing a ray
pointing months into the future needs the x-axis widened well past the
domestic series' own last date (`chartXMax`, widened only when an LBMA
target exists and is later). On a short period that compresses the real
recent price history into a narrow strip on the left with most of the width
given to a mostly-empty future span — confirmed by a user screenshot to be
worse than just not showing it there. `fetchLbmaSurvey()` is skipped
entirely (not just the render) for `7d`/`1m`, so those periods are back to
exactly their pre-LBMA behaviour, including no extra network request.

**No median — LBMA doesn't publish one.** Checked directly against the raw
page text (`grep -i median`): zero occurrences in either report. LBMA's
survey gives exactly 3 numbers (average/high/low from ~16-28 opinions), and
a real median would need each individual analyst's forecast — precisely the
per-analyst data this project deliberately does not scrape (see
"aggregate-only" below). Do not compute a median from the per-analyst
listing without first getting LBMA's written permission for that data at
all; that permission question is unresolved, not merely unasked.

**Not a fan chart.** A user asked why this isn't a percentile fan chart
(median + Pct10-Pct90 bands, like the one already live on
`fuel-forecast.html`). LBMA's survey gives exactly 3 numbers per report
(avg/low/high from ~16-28 opinions) — there is no underlying distribution to
draw percentiles from, and interpolating one would be exactly the kind of
fake precision this project's chart-honesty rules exist to prevent. A real
fan chart for gold would need the same kind of proper statistical model
`delta-world-v1` is for fuel (computed variance, backtested, Wilcoxon-tested)
built from VDV's own dense gold crawl data — a new modeling project, not a
chart change, and not started.

**Why aggregate-only.** LBMA also publishes each analyst's individual
forecast as a named "card" (analyst, firm, their own range and average), but
LBMA's own material states content "may not be altered in any way,
transmitted to, copied or distributed to any other party" without written
permission. That per-analyst listing is LBMA's own proprietary compiled data
— materially different from the raw public administrative bulletins (MOIT,
GSO) this project already crawls. Citing an aggregate statistic with
attribution ("theo khảo sát LBMA, trung bình X") is standard journalistic
practice and a much smaller reuse. **Do not extend this to store or display
per-analyst rows without LBMA's written permission first.**

**Two report types, two publish behaviours:**

| Type | URL | Cadence | Detection |
|---|---|---|---|
| `annual` | `lbma.org.uk/forecast-survey-{year}/at-a-glance` | ~mid-January, forecasts THAT year | Probe the current + next year's URL; 404 = not published yet |
| `midyear` | one fixed, evergreen article URL, reused/updated in place each year | ~late July/August | Article's own publish-date stamp (parsed from the page) advancing past what's stored |

The annual URL drifted once before (2022 used `/publications/annual-precious-
metals-forecast-survey-2022` instead of the current `/forecast-survey-2022`
pattern) — treat a probe failure as "check by hand," not proof nothing was
published.

**`crawl_tools/crawl_lbma_gold_survey.py`** — prose-regex extraction (the
figures sit in narrative sentences, not a table), same shape as the GSO
crawlers. `parse_annual()`/`parse_midyear()` are pure functions (no network),
tested against real fixture text in `test_crawl_lbma_gold_survey.py` without
hitting LBMA on every CI run. Every extraction requires the page to state its
own target year/date explicitly — the same guard `reconcile_sjc.py` uses, for
the same reason: a page that doesn't confirm what it's describing isn't safe
to trust. Stores to `global_lbma_gold_forecast` (`GLOBAL_INDICATOR_DB`,
migration 018), `UNIQUE (survey_type, survey_year)`, `ON CONFLICT DO UPDATE`.

**`.github/workflows/lbma-gold-survey-crawl.yml`** — **monthly** (1st of the
month), not weekly or daily: LBMA publishes twice a year, so even weekly was
more responsiveness than needed; monthly is enough to catch a new report
within the same month it's published. Runs on plain GitHub Actions, no VN box
needed — unlike MOIT/GSO, `lbma.org.uk` is a UK site with no anti-foreign-IP
behaviour (confirmed by direct `curl` from this session). `discover_and_crawl()`
probes both report types every run; most months find nothing new and exit 0.
A `SourceMismatch` (LBMA redesigned the page, regex no longer matches) is the
only thing that turns the workflow red — matches this project's established
"silent no-op on nothing-new, loud failure on a real break" philosophy. Also
added to `generate-static-data.yml`'s `workflow_run` trigger list, so a new
row automatically regenerates `fe/data/lbma_gold_survey.json` — the FE forecast
line updates the next time anyone loads the page, with no manual step.

**`generate_lbma_survey_data()`** (`be/generate_static_data.py`) writes
`fe/data/lbma_gold_survey.json` — every row, no period slicing (irregular,
low-volume data has no periods to slice). No dedicated API endpoint, same
precedent as `fe/data/sbv_policy_all.json`: FE reads the static file directly.

**FE**: `fe/app.js` `fetchLbmaSurvey()` (fetched once, cached, called from
`loadChartData('gold', …)` only — this is gold-specific, unlike
`fetchWorldOverlay()` which also serves silver) feeds the 3-ray datasets built
inside `parseGoldSilverData()`, on the `yWorld` axis, only when the world
overlay itself is present (no `yWorld` scale, no ray to attach to) — a real
`ReferenceError` bug caught and fixed in the same pass: the first cut of this
code referenced the `lbmaData` parameter inside `parseGoldSilverData()`
without declaring it in the function signature, which would have thrown on
every gold *and* silver chart render (the crash sits above the
`chartType === 'gold'` check). The `_tab_data_portal.html` gold chart-card
carries only a one-line disclaimer caption underneath
(`.lbma-survey-disclaimer`) — no separate canvas — citing LBMA's own 2025
forecast-vs-actual miss ($2,735 forecast average vs $3,432 actual close),
consistent with Hướng B (2026-07, "no dự đoán/dự báo, fact/comparison only"):
a stated error history next to the numbers, not a bare confident line.

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

### Retrospective reconciliation (`crawl_tools/reconcile_sjc.py`, 2026-09-14)

The gap this closes: **every other check in this project runs before a write, on
freshly parsed values**, and that cannot see either of the two failures that
actually happened — a write that never happens (the 75-day freeze discarded
correct data at the persistence step) or a write that bypasses the crawler (196
placeholder rows backfilled straight into the table). Both passed every guard by
never meeting one.

**Source: `webgia.com/gia-vang/sjc/DD-MM-YYYY.html`**, which archives SJC's own
published adjustments per day with the time of each. It is unrelated to
24h.com.vn and giavang.org, and — unlike either — it serves *historical* dates.
That is the entire point: you cannot audit the past against a source that only
knows today. **It is deliberately not promoted to a crawl source.** An auditor
that also writes the books is not an auditor.

**The page must state its own date** (checked against the `<h1>`) before anything
on it is believed. This is the direct lesson of the fake rows: 24h.com.vn's
`?ngaythang=` lookup served placeholder numbers under a URL naming a past date
and nothing checked that the page agreed.

Five verdicts, and **only one is an ERROR**:

| Verdict | Meaning | Severity |
|---|---|---|
| `ok` | matches the day's closing quote (or the previous close on a no-change day) | — |
| `stale` | a real quote from that day, but not the last one — the freeze shape | WARNING |
| `carry_forward` | the previous close, because SJC's first change came after the last crawl (18:35 happens) — correct behaviour | WARNING |
| `unconfirmed` | archive lists no change and ours differs — could be our row or a gap in the archive | WARNING |
| `fabricated` | the archive positively lists the day's quotes and ours is none of them — the fake-row shape | ERROR |

`carry_forward` and `unconfirmed` both began life as false ERRORs against real
data. Do not collapse them back into `fabricated`: an empty archive day is
absence of evidence, not evidence of absence, and a tool that overstates its
confidence gets ignored — which is exactly how the last DQ report ended up
unread.

**It never auto-corrects.** A third source disagreeing is evidence to look at,
not truth to overwrite with; silently rewriting stored history from whichever
source spoke last is how this table got into trouble in the first place.

It also runs a network-free `structural_audit()` over the whole series: rows with
a synthesised `crawl_time` (`00:00:00`, the backfill fingerprint), prices frozen
for 20+ consecutive days, and **year-aware** outliers — each row against the
median of its own ±45-day window, since the fixed 20M–500M range has no notion of
time and 81M is unremarkable in general but impossible in 2015.

Run ad-hoc: `python crawl_tools/reconcile_sjc.py [days]` (default 30). It is
wired into the weekly DQ report; the window stays at 30 days so a weekly run has
4× overlap without re-reporting known-old damage forever.

**16 of the days it found were repaired 2026-09-15** (`be/migrations/fix_gold_freeze_stale_days.py`,
backup `be/migrations/gold_freeze_fix_backup_20260915-102845.csv`) — every `stale`
and the one `fabricated` day from the first run, all with strong evidence
(webgia.com's own per-day adjustment log, 2-4 timestamped changes per day). Each
value is the day's actual closing quote, not a guess. `reconcile_sjc.py` confirms
0 ERROR / 0 stale afterward.

**Deliberately left alone**: `2026-08-07` (`carry_forward` — already correct,
nothing to fix) and `2026-07-08/09/15/16/17` (`unconfirmed` — the archive lists
no change those days and the stored value differs from the previous close, which
is absence of evidence, not evidence the row is wrong; the archive may simply be
missing an entry). Do not "fix" these without independently confirming SJC's
actual price that day from a second source — reconcile_sjc.py designed this
verdict specifically so a weak signal does not get treated as certain.

**The DQ agent's findings were invisible until 2026-09-14, and two of its
ERRORs were false.** Three separate problems, all found together:

- **Its only output channel is an HTML email, and that mailbox is dead.** Gmail
  has rejected `SMTP_USER`/`SMTP_PASS` with `535 Username and Password not
  accepted` since at least 2026-09-09, so `data-quality-check.yml` goes red every
  day for a mail failure — not a data failure — and the red light says nothing
  about the data. **The `SMTP_PASS` app password needs reissuing in the Google
  account and updating as a repo secret; until then no report is delivered.**
- **The run log printed three counts and no detail.** It now prints every issue
  to stdout as well, so the Actions log is a usable report on its own. A count is
  not a report.
- **Two standing false ERRORs, both stale `dup_key` config** — the same failure
  mode the 2026-08-31 overhaul was supposed to end, missed on two tables.
  `vn_macro_gold_daily` still grouped on `(date, type)` after migration 016
  widened its unique index to `(date, type, source)`, so every day with both SJC
  sources counted as a duplicate; `vn_gso_gdp_quarterly` grouped on `(year,)`
  while the DB enforces `(year, quarter, sector)`, reporting 7 "duplicates" that
  were simply the other quarters and sectors of the same year. **When a unique
  index changes, change `dup_key` in the same commit.**

After those fixes the agent reports 0 CRITICAL / 0 ERROR / 3 WARNING, and all
three warnings are real: `vn_macro_sbv_rate_daily` has had no row since
2026-09-11, and `vn30_ratio_daily`'s `pe`/`pb` are 84% NULL (the known outage
noted under "VN30 data source" above).

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

### SJC gold is crawled twice, from two unrelated sites (2026-09-14)

One number — SJC's quoted buy/sell price — is read by **two independent crawlers**:

| Script | Source | Role |
|---|---|---|
| `crawl_tools/crawl_sjc_24h.py` | 24h.com.vn | primary on the read path |
| `crawl_tools/crawl_sjc_giavang.py` | giavang.org | covers dates the primary missed |

Both call `crawl_tools/sjc_store.py`, which holds the write path, the plausibility
rules and the cross-source comparison in one place.

**Why two.** Every check this project had looked at the data in isolation — range,
freshness, internal consistency — and a frozen or placeholder price passes all of
them. Two unrelated sites do not invent the same wrong figure, so disagreement is
the one signal that catches a wrong-but-plausible number. When they differ by more
than 2% the crawler still stores its row (a disputed day beats an empty one) and
exits non-zero, so the unit goes red.

**They are not primary/backup — both rows are stored.** Migration
`be/migrations/016_gold_unique_per_source.sql` changed the unique key from
`(date, type)` to `(date, type, source)`; under the old key their upserts
overwrote each other and any disagreement was invisible.

**The read path chooses, it does not take the newest.** `be/generate_static_data.py`
and `be/routers/market_data.py` both `ORDER BY` a `CASE` on `source` — 24h.com.vn,
then giavang.org — so the published figure cannot flip between sources depending on
which crawler ran last. **Change both together.**

`sjc.com.vn` itself would be the ideal source and was tried first: it returns 403
to server-side requests (checked 2026-09-14).

**Schedule: hourly, 01:00–09:00 UTC (08:00–16:00 VN)** — nine passes across the
eight working hours, in `deploy/crawl-fallback.timer`. Each pass runs both SJC
crawlers and `crawl_gold_silver.py` (silver + global macro) as **separate**
container runs, so a Yahoo Finance outage — routine, Yahoo blocks datacenter IPs —
cannot mask whether the gold crawl worked. That coupling is exactly why gold was
split out of `crawl_gold_silver.py`; despite its name that script no longer touches
gold.

### Gold table was reduced to SJC alone (2026-09-14)

`vn_macro_gold_daily` went from **33,885 rows / 31 types to 887 rows of SJC**. Full CSV of everything deleted: `be/migrations/gold_full_backup_20260914-114327.csv` (2.8 MB, committed).

Two separate deletions:

- **32,920 rows of non-SJC brands.** They could not be corrected for the 75-day freeze bug — no per-day archive exists for any of them (24h.com.vn's own `?ngaythang=` lookup returns placeholders for past dates, webgia.com archives SJC alone), so their 2026-06-29→09-11 values were unverifiable and unfixable.
- **78 SJC rows that were never real prices.** All 2015/2016/2020/2021, each brand pinned to one constant (SJC `81.0/83.3`, Phú Quý `81.2/83.3`, BTMC `81.3/83.0`, DOJI SG `80.0/82.5`, PNJ `73.0/74.7`) — physically impossible when actual gold was 34M and 56M respectively. Every one carried `crawl_time = 00:00:00`, i.e. a synthesised timestamp: they came from a **backfill that bypassed the crawler**, so `gold_validation.py` never saw them. 196 such rows existed across all brands.

**The `?ngaythang=` parameter that produced them is gone from `crawl_gold_silver.py`.** It looked harmless because the crawler only ever passed today's date, but any backfill through that URL would have re-created the same garbage.

**Consequence to know before reading the chart:** SJC's own history is sparse — 5 rows in 2015, 11 in 2016, then **nothing until 2024**. The long history that used to fill the "Tất cả" view came from DOJI HN (5,982 rows back to 2009), which is gone. The chart is honest now but short.

**Why `gold_validation.py` did not catch any of this**, worth understanding before trusting it as a safety net:
- It runs **pre-insert, on freshly parsed values**. The freeze bug discarded correct values at the persistence step — validation passed on data that was then thrown away. No pre-insert check can see a write that never happens.
- The backfill rows never went through the crawler at all.
- Its cross-brand median rule **inverts when bad data is the majority**: on 2015 dates the garbage outnumbered the real quotes, so re-running the rule flags the *correct* BTMC/DOJI rows instead.
- Its range rule (20M–500M) has no notion of time: 81M is plausible in general and impossible in 2015, and the rule cannot tell the difference.

Nothing reconciles a stored value against the source after the fact, and no check is year-aware. That gap is still open.

### Gold is SJC-only, and the daily row now tracks intraday moves (2026-09-12)

Two linked changes, both triggered by a user report that the chart had shown a
*fall* from 11/09 to 12/09 while 24h.com.vn showed a *rise*.

**1. The daily row used to freeze at the morning quote.** `crawl_gold_silver.py`
skipped its upsert whenever a row for `(date, type)` already existed, and
`gold-silver-crawl.yml` had a second, independent guard step that skipped the
whole job once `gold_rows > 0 AND silver_rows > 0`. Between them, every rerun
after the day's first successful crawl was a no-op, so each day stored whichever
price happened to be live at ~08:07–08:45 VN and never updated — even though SJC
adjusts several times a day. Introduced 2026-06-29 by `d31423068`, which
collapsed a working 2x/day (08:30 + 14:30 VN) crawl into 1x/day to stop duplicate
rows; it stopped the duplicates but also discarded the afternoon value. Live for
**75 days**. Both guards are gone; every run upserts, `ON CONFLICT DO UPDATE`
does the work, and the unique indexes still hold 1 row per (date, type/source).
Cadence is now hourly across office hours, from a systemd timer on the box
(nine passes, 08:00–16:00 VN) rather than GitHub cron — see
`deploy/crawl-fallback.timer`.

**2. Only SJC is stored and charted now.** Measured impact of the freeze bug on
SJC: **14 of 30 days in 13/08–11/09 held the wrong price**, off by up to 2.1M
VND/lượng (19/08: stored 139.7M, actual 141.8M). Those 14 rows were corrected
from `webgia.com/gia-vang/sjc/DD-MM-YYYY.html`, which archives SJC's own
published adjustments per day (it shows each intraday change — 11/09 went
142.0 → 141.4 → 142.4). **No equivalent archive exists for the other 8 brands**:
24h.com.vn's own `?ngaythang=` lookup returns garbage for past dates (81M/lượng
for Aug 2026, and a "Hôm qua" column dated 2021), and webgia.com archives SJC
alone. Their 2026-06-29→09-11 rows therefore can never be verified or corrected,
so they are no longer crawled, generated as static JSON, or offered in the FE
chart dropdown. Existing rows stay in `vn_macro_gold_daily` and remain reachable
via `/api/v1/gold?type=…`; they simply stop advancing. `gold_types.json` used to
publish 31 types straight from `SELECT DISTINCT type`, most of them long-dead
series (DONGA BANK, SACOMBANK, SJC Đà Nẵng, SJC1c…) with no static file behind
them — it is now `["SJC"]`.

**That is no longer how the gold path validates — `validate_gold_records` has no
production caller any more.** It used to be kept alive by parsing every brand on
the page before filtering to SJC, because its cross-brand median check needs ≥3
brands to run at all. `crawl_sjc_24h.py` reads the SJC row alone and validates
through `sjc_store.py` instead. The exchange is deliberate and is net coverage
*gained*, not lost:

- The digit-error case that motivated the median rule (24h.com.vn publishing
  `14,450` for `144,500`) is caught by `check_plausible`'s 20M floor outright.
- The median rule **inverts when bad rows are the majority** — on the 2015 dates
  it flags the correct BTMC/DOJI quotes, not the fakes. The cross-source
  comparison has no such failure mode: two unrelated sites do not invent the same
  wrong figure.

`validate_gold_records` still guards nothing but its own tests. Leave it in place
(`gold_validation.silver_is_plausible` in the same module is live, used by
`crawl_gold_silver.py`), but do not cite it as the gold safety net.

### Gold & silver validation (`crawl_tools/gold_validation.py`)

Rules live in their own module so they are unit-testable (`crawl_tools/test_gold_validation.py`, run with `python -m pytest crawl_tools/` from the repo root — CI does not run it yet):

- **Range**: gold 20M–500M VND/lượng, silver 300k–20M VND/lượng. Rejects a dropped or extra digit.
- **Cross-brand median**: a brand more than 15% off the same-day median across all brands is rejected (needs ≥3 brands, otherwise skipped). Catches a digit error that still lands inside the range.
- Rejected rows are never inserted; if the whole page fails, `crawl_gold_silver.py` exits non-zero (`gold_failed`, mirroring `global_failed`) so the workflow turns red instead of silently serving stale data.

Added 2026-08-07 after 24h.com.vn itself published DOJI at `14,450` instead of `144,500` on 2026-07-18–19. The crawler had no pre-insert validation, so a price one tenth of the real value reached the public chart and the API and stayed there 20 days. The DQ email agent did flag it as a WARNING — it just never blocked anything and nobody read the mail.

### Uniqueness

`vn_macro_gold_daily` has `uq_vn_gold_date_type_source (date, type, source)` — widened from `(date, type)` by migration 016 so two crawlers can quote the same day side by side; `vn_macro_silver_daily` has `uq_vn_silver_date_source (date, source)`. **`crawl_tools/data_quality_check.py`'s `dup_key` for gold must match** — it still said `(date, type)` until 2026-09-14 and would have reported every two-source day as a duplicate. Both crawler INSERTs use `ON CONFLICT … DO UPDATE`, so overlapping hourly retries refresh the row instead of appending a second one. Before these existed (2026-01→06), retries left 1,217 duplicate gold rows and 298 silver rows, 347 of them disagreeing on price.

### Missing values are `null`, never `0`

`be/generate_static_data.py` (`num()`) and `be/routers/market_data.py` (`_num()`) emit `null` for a NULL column on the gold and global-macro endpoints. Emitting `0` made charts plunge to the axis and API consumers read a gap as a real price of zero. Chart.js skips nulls, leaving an honest gap. Other tables still coerce to `0` — they have no NULLs today; convert them the same way if that changes.
