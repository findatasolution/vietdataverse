# Viet Dataverse — Google Sheets template

A customer copies one file, pastes an API key into one cell, and has nine
datasets that keep themselves up to date. There is no third step.

## How it works

`build_template.py` generates a workbook whose nine data tabs each hold a single
formula in `A1`:

```
=IF('Bắt đầu'!$C$4="", "← Dán API key…", IMPORTDATA("…&format=csv&api_key="&'Bắt đầu'!$C$4))
```

`IMPORTDATA` is built into Google Sheets. Nothing is installed, nothing is
authorized, and every tab reads its key from the same cell, so one paste fills
the whole file.

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
