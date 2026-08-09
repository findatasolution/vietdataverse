# Frontend (fe/) — Build & Structure

## Overview

`fe/index.html` được **auto-generated** từ 8 partials. Never edit `index.html` trực tiếp — edit `fe/partials/` thay.

## Partials Structure

```
fe/partials/
  _layout_head.html         # DOCTYPE, <head>, GA, JSON-LD, nav, sidebar open
  _tab_data_portal.html     # Dữ liệu kinh tế mở (6 sub-tabs: gold, silver, sbv, td, fx, download)
  _tab_market_pulse.html    # Thời báo 1 giây
  _tab_knowledge_market.html # Knowledge market
  _page_about.html          # About & Terms
  _page_privacy.html        # Privacy policy
  _page_contact.html        # Contact form
  _layout_footer.html       # Modals, footer, </body>, </html>
```

Total: 8 files, ~225 lines each on average. Each partial is an HTML fragment (no DOCTYPE/html wrapper except head/footer).

## Build Process

### Manual build (local development)

```bash
cd fe
python build.py
```

Output:
```
Build complete: /path/to/fe/index.html
  Partials merged : 8
  Output lines    : 1697
```

Commits to git: `python build.py` produces deterministic output (idempotent).

### Automated build (GitHub Actions)

**Workflow:** `.github/workflows/build-html.yml`

Trigger: push or PR to `fe/partials/` or `fe/build.py`

Steps:
1. Checkout code
2. Run `python fe/build.py`
3. If `fe/index.html` changed → auto-commit + push

**Result:** Dev edits `fe/partials/X.html` → pushes → CI builds + commits `fe/index.html` → deploy to GitHub Pages.

## Dev Workflow

### Editing a section

Example: fix gold chart markup in data portal tab.

1. Edit `fe/partials/_tab_data_portal.html` directly (line 50-200)
2. Test locally: 
   - Run `python fe/build.py` to regenerate `fe/index.html`
   - Open `fe/index.html` in browser, click "Dữ liệu kinh tế mở" tab
   - Verify chart renders, no DOM errors
3. Commit only `fe/partials/_tab_data_portal.html`:
   ```bash
   git add fe/partials/_tab_data_portal.html
   git commit -m "fix: gold chart title alignment in data portal"
   git push
   ```
4. CI automatically:
   - Runs `python fe/build.py`
   - Commits `fe/index.html` with message `build: regenerate fe/index.html [skip ci]`
   - Pushes to branch
5. Deploy: GitHub Pages serves `fe/index.html` from repo

### Adding a new section

1. Create `fe/partials/_section_newname.html` with markup
2. Add to `PARTIALS` list in `fe/build.py` (order matters!)
3. Run locally: `python fe/build.py`
4. Test in browser
5. Commit both `build.py` + new partial + regenerated `index.html`

## Copy & Formatting Conventions (added 2026-08-09)

Four rules that a UI audit of the Open Data page found broken in ~40 places. They
are cheap to keep and expensive to notice later — the page reads as unfinished
long before anyone can name why.

1. **Bump `?v=` when you touch `app.js` or `style.css`.** Both are referenced as
   `app.js?v=YYYYMMDDNN` from `_layout_head.html` / `_layout_footer.html`. Ship a
   change without bumping and returning visitors keep the cached old bundle and
   see none of it — the change looks like it silently failed.
2. **Vietnamese headings use sentence case, not Title Case.** "Lịch sử giá vàng
   trong nước", never "Lịch Sử Giá Vàng Trong Nước". Proper nouns keep their caps
   (Việt Nam, Phú Quý, NHNN, NHTM, GDP, CPI, SBV). This does **not** apply to the
   SEO `<title>` / `og:` / `twitter:` / JSON-LD strings — changing those affects
   search results and is a separate, deliberate decision.
3. **Every user-visible label needs a `data-i18n` key.** Hardcoded text silently
   opts out of the En/Vi toggle: 22 period buttons read English in *both*
   languages because they had no key. Period keys already exist —
   `period7d/1m/3m/1y/3y/10y/20y/All`; add to both the `vi` and `en` blocks in
   `app.js`, never one alone.
4. **All chart numbers go through `formatNumVi` / `formatVndAxis`** (`app.js`,
   defined above `parseGoldSilverData`). Chart.js otherwise falls back to the
   browser locale and prints `150,000,000` next to KPI cards showing `25.463`.
   `formatVndAxis` is for axis ticks only (`150 triệu`, `2,35 triệu`); tooltips
   use `formatNumVi` so the exact figure stays readable. Keep the 2 fraction
   digits — silver ticks step by 50.000đ, so 1 digit prints `2,3 triệu` twice.

## Important Rules

- **NEVER edit `fe/index.html` directly** — changes will be overwritten next build
- Header comment marks auto-generated: `<!-- GENERATED FILE — edit fe/partials/ instead. Run: python fe/build.py -->`
- Each partial must have **balanced open/close tags** (no dangling `<div>` that spans files)
- Partials are ordered: head (1) → tabs (2-4) → pages (5-7) → footer (8)

## Dependencies

- Python 3.8+
- stdlib only: `pathlib`
- No npm, no node_modules, zero external deps

## Performance

- Build time: <50ms
- Output size: 1697 lines HTML (gzips to ~15KB)
- Runtime: zero build artifacts required (HTML is pure static)

## Related Files

- `fe/app.js` (2938 lines) — Chart.js, fetch logic, translations — **NO BUILD STEP**
- `fe/style.css` (2640 lines) — styling — **NO BUILD STEP**
- `fe/auth.js` (150 lines) — Auth0 flow — **NO BUILD STEP**

These 3 files are copied as-is to `dist/` (if deployed) or referenced directly from `fe/` root. `build.py` only regenerates HTML, never touches JS/CSS.
