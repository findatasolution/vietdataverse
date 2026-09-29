# Viet Dataverse — Google Sheets template

A customer copies one file, pastes an API key into one cell, and has nine
datasets that keep themselves up to date. There is no third step.

## How it works

**One API call feeds the whole workbook.** A `_dữ liệu thô` tab holds a single
`IMPORTDATA` against `/api/v1/excel/refresh-data?format=csv`, which returns all
nine datasets stacked into one rectangle (`dataset` + 8 padded value columns).
Each visible tab pulls its own rows with `QUERY`, a pure spreadsheet function
that costs no network.

Each dataset tab carries a **line chart** and, in `B1`, the **newest period in
that dataset** — so a reader can see how fresh the data is without scrolling.

### Why one call and not nine

Measured on a real customer, 2026-09-29: the previous design — nine live
`IMPORTDATA` formulas — made **315 calls in 2.7 days**. That is 116/day,
including 03:00 and 05:00 local, with nobody touching the file: Sheets
refreshes each formula about hourly while a tab stays open.

| Design | Ceiling if the file is left open | Against the 1.000/month paid quota |
|---|---|---|
| Nine formulas | ~216 calls/day | dead in **8.6 days** |
| One formula | 24 calls/day | ~720/month — **fits, with room** |

That is what makes the product promise keepable: a paying customer can pull the
full dataset every day for thirty days and still be inside quota.

### Locale — the one thing that silently corrupts the data

`IMPORTDATA` is called with an explicit `"en_US"` locale. **Do not remove it.**

A Drive copy inherits its owner's spreadsheet locale. Under `vi_VN`, Sheets
reads `4.5` as *the date 4 May* and stores `46146`. Every rate shaped `X.Y`
with `X<=12` and `Y<=31` was destroyed that way — refinancing `4.5` → `46146`,
overnight `5.1` → `46027`, `3.7` → `46088` — while three-digit values like
`4.45` survived, so the damage looked like random noise instead of a parsing
rule. In `en_US` the decimal separator is `.` and the date separator is `/`, so
a rate cannot be mistaken for a date at all.

The first column of each tab also carries an explicit number format, applied
cell by cell over the spill range because a column-level format does not
survive the `.xlsx` → Sheets conversion. Without it a parsed date renders as
its serial (`45929` instead of `2025-09-29`). Dates use `yyyy-mm-dd`; CPI and
trade use `yyyy-mm` (their period is `2026-08`, which `en_US` turns into
1 Aug 2026 — the format displays it back as the source states it); GDP's year
is a plain number.

### When the API refuses

`IMPORTDATA` renders `#N/A` and nothing else — a Sheets user never sees an HTTP
body, which is precisely why an exhausted quota looked like a broken file. The
raw formula is wrapped in `IFERROR` and prints the real reason plus the upgrade
link instead.

## Why there is no Apps Script

An earlier version of this connector was a bound Apps Script with a
**Viet Dataverse** menu (`Code.gs`, removed 2026-09-25 — see git history).

It worked, and it could not ship. A bound script travels with a Drive copy and
becomes *the copier's own* script project, so Google showed every customer
"Google hasn't verified this app", naming **the customer** as the developer, on
a script they had just unknowingly acquired. No project setting removes that.
The only fix is publishing a verified Google Workspace Marketplace add-on —
weeks of review, a privacy policy, a demo video and a maintained GCP project.

Do not reintroduce a bound script as a copyable template. If the Sheets channel
ever justifies it, do the Marketplace route properly: customers then *install*
an add-on instead of copying a file, which is a better product anyway.

## Quota

Each tab is one metered API call, so opening the file with all nine tabs costs
nine. Free tier is 2 requests/month — not enough to fill the file once, which is
deliberate: the template is a reason to buy API Supper Lite (1.000/month ≈ 110
opens). A customer who needs fewer datasets deletes the `A1` formula on the tabs
they do not want.

## Live template — verified 2026-09-26

`1UGILO_Mk02qWYx1BLk5DRE8yoNEXT9cTGIS57EOiwds`, "Viet Dataverse — Dữ liệu kinh
tế Việt Nam", shared `anyone with link → reader`, old bound Apps Script deleted.

Verified after the import: all nine tabs carry a live formula — `A1` renders the
"← Dán API key…" prompt, not `#NAME?`. That is the check that matters, because
`IMPORTDATA` is a Google-only function and nothing guarantees an `.xlsx` import
preserves it. **It does.**

Still unverified: pasting a real key and watching data arrive.

## Rebuilding

```bash
python3 integrations/google-sheets/build_template.py
```

Then publish the generated `.xlsx` into the live template spreadsheet:

1. Open the [template](https://docs.google.com/spreadsheets/d/1UGILO_Mk02qWYx1BLk5DRE8yoNEXT9cTGIS57EOiwds/edit)
2. **File → Import → Upload** the `.xlsx` → **Replace spreadsheet**
3. Check the cover reads `Bắt đầu` and a data tab's `A1` shows the prompt text,
   not `#ERROR!` — Google parses the formulas on import, so a bad formula is
   visible immediately.

Keeping the same file id matters: its `/copy` link is published in
`fe/pages/google-sheets.html`, `api-docs.html` and `account.html`, and it is
already shared `anyone with link → reader`.

The Google Drive connector available to this repo's agents cannot convert
`.xlsx` to a Google Sheet ("Invalid conversion requested"), so the import step
is manual.

## Endpoints

Queries mirror `_datasets()` in `be/routers/sheets_export.py`. Both must change
together if a dataset's parameters change. Every query was verified to return
CSV against the live databases on 2026-09-25.
