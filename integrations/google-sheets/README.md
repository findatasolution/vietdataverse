# Viet Dataverse — Google Sheets template

A customer copies one file, pastes an API key into one cell, and has nine
datasets that keep themselves up to date. There is no third step.

## How it works

**One API call feeds the whole workbook.** A hidden `_raw` tab holds a single
`IMPORTDATA` against `/api/v1/excel/refresh-data?format=csv`, which returns all
nine datasets stacked into one rectangle (`dataset` + 8 padded value columns).
Each dataset tab pulls its own rows with `FILTER`, a pure spreadsheet function
that costs no network.

Tab order: `Bắt đầu` (key in `C6`, refresh in `C7`, period dropdown in `C8`) →
`Tổng quan` (eight KPI cards with change vs previous period and a 90-point
sparkline, plus eight `SPARKLINE` chart blocks with first / lowest / highest /
newest values under each) → nine dataset tabs, each with `B2` showing the
newest period it holds. No native (inserted) charts — see rule 6.

### Six rules, each paid for by a broken file (2026-10-03)

1. **Dates leave the formula as text** — `TEXT(..., "yyyy-mm-dd")`. IMPORTDATA
   stores `2025-10-03` as the serial `45933` with no date format; the old fix
   pre-applied a number format to every cell, and in a customer's copy that
   format held for the first rows only — later rows showed `46155` where a date
   belonged (exact cause unknown; text sidesteps it) — for several sessions
   running, because nobody looked at a real Sheet with real data.
2. **`FILTER`, never `QUERY`, over the raw tab.** QUERY types each column by
   majority and nulls the minority. Nine datasets share the raw columns, so
   every GDP sector name came back blank.
3. **No Excel dynamic-array functions** (`SORT`, `LET`, `XLOOKUP`…). The old
   freshness cell (`SORT`) showed "—" on the live template even with data
   loaded. Suspected cause, unverified: openpyxl writes them without the
   `_xlfn.` prefix. Avoiding them costs nothing.
4. **The raw tab is hidden.** Its headers are `c1..c8` and its dates are
   serials; customers asked what it was for. Formulas reach it through
   workbook names `VDV_A`..`VDV_I` and `VDV_STATUS` (= its `A1`).
5. **No open-ended ranges** (`C2:C`). Valid in Sheets, invalid in `.xlsx`: the
   first real-Sheet check turned every formula holding one into `#ERROR!`.
   The names above are bounded (`$C$2:$C$8000`).
6. **No native charts.** Seven inserted charts tripled the `.xlsx`; the Drive
   connector could only upload files up to ~14k base64 characters, so the
   dashboard draws with `SPARKLINE` (and the dataset tabs carry no chart).
   A sparkline has no axis, so each block prints its scale underneath.

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

### Locale — the other thing that silently corrupts the data

`IMPORTDATA` is called with an explicit `"en_US"` locale. **Do not remove it.**

A Drive copy inherits its owner's spreadsheet locale. Under `vi_VN`, Sheets
reads `4.5` as *the date 4 May* and stores `46146`. Every rate shaped `X.Y`
with `X<=12` and `Y<=31` was destroyed that way — refinancing `4.5` → `46146`,
overnight `5.1` → `46027`, `3.7` → `46088` — while three-digit values like
`4.45` survived, so the damage looked like random noise instead of a parsing
rule. In `en_US` the decimal separator is `.` and the date separator is `/`, so
a rate cannot be mistaken for a date at all.

Dates are covered by rule 1 above.

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

The whole file costs **one** metered call per load (see "Why one call and not
nine"). Free is 20/month; API Supper Lite is 1.000/month, which covers the file
left open for a whole month (~24 loads/day, ~720/month).

When the call is refused — no key, bad key, quota spent — the raw tab's `A1`
holds the reason, and every data tab (and the dashboard subtitle) falls back to printing that same reason
instead of going blank. A blank tab reads as a broken file; that was the
customer report of 2026-09-29.

### Refresh cell `C7`

`IMPORTDATA` caches on the exact URL and refreshes about hourly. `C7` is appended
to the URL as `&_r=`, so bumping it forces a real fetch; the API ignores the
parameter (verified on prod: a fake key still gets 401, not 422). Commit
`724b86677` dropped it while collapsing nine formulas into one, and the cover's
"bump C7" instruction silently stopped working until 2026-09-29.
`tests/sheets/test_build_template.py` now guards it.

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

### Verifying a rebuild — do not skip this

`tests/sheets/` checks formula strings; it cannot prove they evaluate. Every
bug in rules 1–5 passed a string test. Two ways to check for real:

**Without a key (what was done 2026-10-03).**
`python3 integrations/google-sheets/make_verify_files.py stacked.csv OUT/`
builds two small `.xlsx` with the raw tab pre-filled exactly as IMPORTDATA
leaves it (`stacked.csv` = the body of `/api/v1/excel/refresh-data?format=csv`).
Upload each to Drive *converted to a Google Sheet* and read it back — Drive
evaluates the formulas on conversion. Verified that way on 2026-10-03: dates
render as text to the last row, CPI as `2026-08`, GDP sectors in Vietnamese,
`B2` filled, every KPI card and chart-block value matching its tab. Not
verifiable from text: the SPARKLINE images themselves.

**With a key.** Import the full `.xlsx` into a scratch spreadsheet (never the
live template), paste a key into `C6`, and look at the same things plus the
sparklines and that no `_raw` tab is visible.

Agent limits found 2026-10-03: Claude-in-Chrome could not use the Google file
picker (cross-origin iframe) or run JS on Drive; the Drive connector uploads
only ~14k base64 characters reliably and its `share_file` cannot set
"anyone with the link". So creating or re-sharing the live template is the
owner's step.

Then publish the generated `.xlsx` into the live template spreadsheet:

1. Open the [template](https://docs.google.com/spreadsheets/d/1UGILO_Mk02qWYx1BLk5DRE8yoNEXT9cTGIS57EOiwds/edit)
2. **File → Import → Upload** the `.xlsx` → **Replace spreadsheet**
3. Check the cover reads `Bắt đầu` and a data tab's `A1` shows the prompt text,
   not `#ERROR!` — Google parses the formulas on import, so a bad formula is
   visible immediately.

**Never paste a real API key into the live template itself.** It is shared
`anyone with link → reader`, so a key in its `C6` is published to everyone who
opens or copies it, and every copy spends that key's quota. Test on a copy
(`/copy` link), never on the master. Found 2026-09-29: the owner's key sat in the
master's `C6`. Clear the cell and rotate that key on `developer.html`.
**Found again 2026-10-03** — a customer reported their fresh copy "already had a
token". The build ships `C6` empty (`tests/sheets` pins it), so the only way a
key gets there is someone pasting it into the master. After every import, read
the live file's `C6` back and confirm it is empty.

Keeping the same file id matters: its `/copy` link is published in
`fe/pages/google-sheets.html`, `api-docs.html` and `account.html`, and it is
already shared `anyone with link → reader`.

The Google Drive connector *can* convert an `.xlsx` into a new Google Sheet
(checked 2026-09-29 — the earlier "Invalid conversion requested" note was
wrong), but it cannot replace the contents of an existing file id, and the live
template's id is what every published `/copy` link points at. So the import into
the live template stays manual: File → Import → Replace spreadsheet.

Two limits on testing it from an agent, both found 2026-09-29: a CSV upload
parses formulas in the owner's locale (`vi_VN` needs `;` as the argument
separator) and leaves `IMPORTDATA` as plain text; and `IMPORTDATA` is only
evaluated while a browser has the file open, so reading a sheet through the API
never shows fetched data.

## Endpoints

Queries mirror `_datasets()` in `be/routers/sheets_export.py`. Both must change
together if a dataset's parameters change. Every query was verified to return
CSV against the live databases on 2026-09-25.
