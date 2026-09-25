# Viet Dataverse Google Sheets connector

This directory contains the source for the Apps Script intended to be bound to
the Viet Dataverse Google Sheets template.

## Delivery status — 2026-09-25

The [template workbook](https://docs.google.com/spreadsheets/d/1UGILO_Mk02qWYx1BLk5DRE8yoNEXT9cTGIS57EOiwds/edit)
exists with a cover and nine dataset tabs, and is shared `anyone with link ->
reader`, which is what a copyable template needs.

Verified: the bound script is installed and the **Viet Dataverse** menu renders
in the spreadsheet. Local connector tests pass.

Not yet verified: an authenticated refresh end to end, and refresh after a Drive
copy. Both were blocked until 2026-09-25 by a backend defect unrelated to this
connector — `/auth/me` returned 500 for every new account, so no API key could
be issued (see root `CLAUDE.md`, "`/auth/me` inserted a blank email"). That is
fixed; the refresh check still has to be run.

Release checks, in order: refresh all nine tabs with a valid user key, confirm
the cover's `Trạng thái` cell turns from `Chưa kết nối` into
`Đã cập nhật 9 bộ dữ liệu`, then make a Drive copy **from a different Google
account** and confirm it (a) keeps the menu and (b) starts with no inherited
API key. Record the live result here before handing the link to anyone.

Two known cosmetic gaps: the cover's `C7` still reads "Thiết lập kết nối" while
the menu item is "Thiết lập API key", and the Apps Script project name is shown
to every customer on the OAuth consent screen, so it must not be left as
"Untitled project".

`Viet-Dataverse-Google-Sheets-Template.xlsx` is a layout artifact only — an
`.xlsx` cannot carry a bound Apps Script, so it is not the template.
**`build-template.mjs` does not run in this repo**: it imports
`@oai/artifact-tool`, which exists only in the authoring sandbox it was written
in, and this repo has no npm toolchain at all. It is kept as the record of how
the layout was produced, not as a build step.

## User flow

1. Make a copy of the published template.
2. Open **Viet Dataverse → Thiết lập API key**.
3. Authorize the script once, paste a valid API key, and choose a period in the native prompts.
4. Use **Viet Dataverse → Refresh toàn bộ dữ liệu** whenever fresh data is needed.

The API key is stored in Apps Script `UserProperties`. It is scoped to the
current Google user and is never written into spreadsheet cells or request
URLs. A refresh sends the key in `X-API-Key` and updates the nine managed data
tabs without deleting or recreating them.

## Bound-script files

- `Code.gs`: menu, native setup prompts, settings, API calls, and data writes.
- `appsscript.json`: V8 runtime and the minimum spreadsheet/external-request scopes.

Keep the single script file bound to the template spreadsheet. A normal Drive
copy keeps the bound script, so each customer receives the refresh menu in
their copy without adding any other Apps Script files.
