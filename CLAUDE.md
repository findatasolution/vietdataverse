# Viet Dataverse — Project Standards

## Project Overview
Financial data platform for Vietnam macro & corporate data.
Stack: Python crawlers → PostgreSQL (Neon) → FastAPI → Chart.js FE.

---

## Database Infrastructure

### 3 PostgreSQL databases (Neon, env vars in `vietdataverse/be/.env`)

| Env Var | Purpose | Key Tables |
|---------|---------|------------|
| `CRAWLING_BOT_DB` | Macro crawl data | `vn_macro_*`, `vn_gso_*` |
| `CRAWLING_CORP_DB` | Corporate/equity data | `vn30_*` |
| `GLOBAL_INDICATOR_DB` | Global macro (Yahoo Finance) | `global_macro` |

### Table Naming Convention
```
vn_macro_{source}_{asset}_{freq}     # domestic macro
vn_gso_{topic}_{freq}                # GSO/NSO statistical data
vn30_{topic}_{freq}                  # VN30 corporate data
global_{topic}_{freq}                # global indicators
```
Examples: `vn_macro_gold_daily`, `vn_gso_cpi_monthly`, `vn30_ohlcv_daily`

### Required Columns (all tables)
```sql
id          SERIAL PRIMARY KEY          -- always SERIAL, never manual MAX(id)+1
crawl_time  TIMESTAMP NOT NULL          -- UTC, set at crawl time
date/period DATE or VARCHAR(7)          -- YYYY-MM-DD or YYYY-MM
```

### Constraints (always add)
```sql
UNIQUE (bank_code, date)               -- dedup key per entity
INDEX  (date) or INDEX (period)        -- query perf
```

---

## Crawl Pipeline Standards

### File location: `crawl_tools/`
Each crawler is a standalone Python script. Pattern:
```
crawl_tools/
  crawl_{source}_{asset}.py     # daily/periodic crawler
  enrich_{asset}_history.py     # historical backfill
  db_schema.py                  # SQLAlchemy schema reference (all tables)
```

### Crawler Structure
```python
# 1. Load .env from vietdataverse/be/.env
load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / 'vietdataverse' / 'be' / '.env')

# 2. Validate env
DB_URL = os.getenv('CRAWLING_BOT_DB')
if not DB_URL: sys.exit("CRAWLING_BOT_DB not set")

# 3. Parse → validate → store
data = parse(html)
if not validate(data): sys.exit(1)
save(data)
```

### Validation Rule
At least 3 valid numeric values in expected range before writing to DB.

### Store Pattern
- Use `INSERT ... ON CONFLICT DO NOTHING` or `ON CONFLICT DO UPDATE`
- Never write `SELECT MAX(id)+1` — always use SERIAL
- Always call `conn.commit()` explicitly (SQLAlchemy 2.x)

---

## GitHub Actions Workflows

Location: `.github/workflows/`
Naming: `{asset}-crawl.yml`

Standard schedule pattern (Vietnam timezone = UTC+7):
```yaml
schedule:
  - cron: '30 1 * * *'   # 08:30 VN daily
```

Standard steps:
```yaml
- uses: actions/checkout@v4
- uses: actions/setup-python@v5
- run: pip install -r crawl_tools/requirements.txt
- run: python crawl_tools/crawl_{source}.py
  env:
    CRAWLING_BOT_DB: ${{ secrets.CRAWLING_BOT_DB }}
```

---

## API Layer (FastAPI)

### Location: `vietdataverse/be/`
- Routers: `be/routers/market_data.py`, `be/routers/vn30_data.py`
- Static data generator: `be/generate_static_data.py` → outputs to `vietdataverse/data/`

### API URL Pattern
```
/api/v1/{asset}               # primary data endpoint
/api/v1/{asset}/types         # list available subtypes (e.g. gold types, banks)
/api/v1/macro/{indicator}     # macro indicators (cpi, gdp, trade)
```

### Static JSON Pattern (for FE performance)
```
data/
  {asset}_{subtype}_{period}.json    # e.g. termdepo_ACB_1y.json
  {asset}_types.json                  # available subtypes
  manifest.json                       # metadata + timestamps
```

### Response Format
```json
{
  "success": true,
  "source": "GSO/NSO vn_gso_cpi_monthly",
  "count": 21,
  "data": [...]
}
```

---

## Visualization (FE)

### File: `vietdataverse/app.js`
- Charts: Chart.js
- Data: fetched from `/api/v1/...` (relative URLs — same origin)
- Period buttons: `data-macro-period` attribute on `.filter-btn`
- Cache pattern: `_raw{Asset} = null` — fetch once, re-render on period change

### Color Conventions
```js
CPI/inflation  : #EF5350 (≥10%), #FFA726 (≥5%), #66BB6A (≥0%), #42A5F5 (<0%)
Gold           : #C9A55B
Term deposit   : #42A5F5 (1m), #66BB6A (3m), #FFA726 (6m), #EF5350 (12m)
```

---

## db_schema.py — Schema Reference Rules
- Every table must have a class here
- `id = Column(Integer, primary_key=True, autoincrement=True)`
- Always include `UniqueConstraint` and `Index` in `__table_args__`
- Comment per column: source, unit, notes
- Remove columns from schema when dropped from DB

---

## Data Quality Checks (before any DB write)

```python
def validate_rates(data):
    term_keys = [k for k in data if k.startswith('term_') and data[k] is not None]
    if len(term_keys) < 3: return False
    for key in term_keys:
        if not (0.1 <= data[key] <= 20.0): return False
    return True
```

General rule: validate range + completeness before insert. Never insert partial/corrupted rows.

---

## Active Banks / Sources

| Asset | Bank/Source | Table | Freq |
|-------|------------|-------|------|
| Term Deposit | ACB only | `vn_macro_termdepo_daily` | Daily |
| Gold | BTMC, DOJI, SJC, PNJ... | `vn_macro_gold_daily` | Daily |
| Silver | Phú Quý | `vn_macro_silver_daily` | Daily |
| FX Rate | VCB, SBV | `vn_macro_sbv_rate_daily` | Daily |
| CPI | NSO/GSO (nso.gov.vn) | `vn_gso_cpi_monthly` | Monthly |
| Global | Yahoo Finance (GC=F, SI=F, ^IXIC) | `global_macro` | Daily |
