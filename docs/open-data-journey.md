# Open Data customer journey

Base journey implemented on 2026-09-17. API/Excel purchase improvements and PayOS settlement fixes implemented locally on 2026-09-23; deployment of these changes and a real payment smoke test remain pending.

## Entry points and routes

- `/fe/index.html#data/portal`: explore the catalog by reporting, historical analysis or API integration. Existing overview charts remain available.
- `/fe/index.html#data/portal/chart/<id>`: the single dataset detail route shared by catalog cards and overview charts.
- Detail route query (inside the hash): `period`, `bank`, `method`. Values are allowlisted. Invalid datasets fall back to the overview.
- `/pages/pricing.html?id=<id>&period=<period>&bank=<bank>&method=<method>`: compare subscription limits in dataset context. Both `/pages` and `/fe/pages` aliases remain supported.
- Excel, Sheets and API-key guides are linked from dataset detail. Only gold advertises the Sheets CSV connector. Policy rates currently have no dedicated API endpoint.

## What visitors can do

1. Inspect source, units, observation cadence and the existing full-size chart without signing in.
2. Inspect snapshot date coverage, record count and recent rows; download the public snapshot as CSV without authentication.
3. Use the existing authenticated history download, or inspect the dataset-specific API request and integration guides.
4. Compare paid access if API usage outgrows the free quota. Pricing does not claim exclusive history, unlimited API, realtime delivery or priority download speed.
5. After server-verified payment, open API-key management, the Excel starter, or return to the same dataset, chart period, bank and method. Pending confirmation is polled four times (1.5-second intervals); a manual retry remains available. Context contains no credentials and expires after 24 hours in session storage. No automatic download or API-key rotation occurs.
6. `/pages/excel.html#starter` offers free, ready-to-paste Power Query examples and public snapshot previews for central USD/VND, monthly CPI and quarterly GDP. API keys are entered in Excel only, via the `X-API-Key` header. FX requests one year (up to 500 rows), CPI up to 60 observations, and GDP the existing API coverage (up to 200 rows); GDP has no `years` parameter. Numeric columns are explicitly typed. A multi-page response fails visibly instead of silently dropping rows. No workbook or exclusive dataset is sold.
7. The existing API Supper Lite product remains 45,000 VND / 30 days (450,000 VND / 365 days; verified students pay half). Open Data links directly to pricing and the Excel examples. Guest checkout opens the email field immediately and explains that the same email must be used for subsequent login. No new price, plan, schema or paid product was introduced.

## Source of truth

- `fe/pages/data-journey.js`: dataset catalog, snapshot parsing, discovery, detail controls and bounded purchase context. Snapshot coverage is explicitly not full API history. Missing snapshots display an error rather than fabricated coverage.
- `GET /api/v1/payment/plans`: public prices, duration, monthly and burst quotas from `SUBSCRIPTION_PLANS` and `get_quota`. Does not access a database or expose credentials. Frontend checkout remains disabled if these facts cannot be loaded; retry is provided.
- `fe/pages/pricing-journey.js`: consumption of server plan facts and contextual comparison. Existing plan IDs, billing amounts, student discount and access enforcement are unchanged. The pricing catalog grid also appends one extra tile, **Giá xăng dầu & dự báo**, linking to the standalone `fuel-forecast.html` product page — its coverage line is read live from `/api/v1/fuel-forecast/E5RON92` (no static snapshot exists). It is deliberately *not* in `data-journey.js`'s `catalog`: that array is pinned to the SPA overview charts (`catalog.test.cjs`), and fuel has no `#data/portal/chart/<id>` route. This tile is currently the only on-site link to the fuel forecast page.
- Free API currently exposes available history within its quota; there is no ten-download lifetime gate. Public snapshot windows differ by dataset.
- PayOS return/cancel URLs point to pricing, where server verification determines success. Verification failure does not imply successful payment and retains the order query for retry. The UI requires `success`, `status=paid`, `order_type=subscription` and an activation/already-paid flag before showing API activation or emitting a purchase event.
- Auth0 callback compares the full same-origin return URL, including the dataset hash; returning to the same `index.html` pathname no longer drops the selected dataset.
- The new Open Data offer uses one-time PayOS payments, not automatic renewal. This does not describe the separate wallet-funded marketplace subscription system.

## Measurement

Dataset events use the existing `gtag` when available: `dataset_detail_view`, `dataset_download_success` (preview CSV triggered), `dataset_upgrade_view`. They do not prove the downloaded file was opened or an integration succeeded.

Pricing and Excel now load `fe/pages/site-analytics.js`, targeting the existing primary tag `G-YB3PKHN2E5` only on `vietdataverse.online`/`www.vietdataverse.online`. These pages send a sanitized page view (no URL query/hash) and `excel_query_copy`, `begin_checkout`, `checkout_redirect`, `checkout_error`, and `purchase`. Purchase value/plan come from server verification; transaction ID is the order code, with session-storage reload deduplication. This browser event is not an accounting ledger: ad blockers, disabled JS, abandoned return pages or cleared storage affect it. Reconcile revenue with paid backend orders.

This scoped addition does not reconfigure GA4 or change the SPA's legacy tags. The property still contains other hostnames, and old SPA tracking still needs its separate privacy/attribution cleanup. Use a production-host filter for analysis. `dataset` has not been registered as a GA4 custom dimension; the historical Data API cannot break down that parameter. The primary tag mapping to a stream could not be independently read through the Admin API (403); its ID is reused from the existing SPA loader.

## PayOS settlement

The official signed callback reports nested `data.code="00"` and has no `status` field. The previous handler waited for `status="PAID"` and skipped these callbacks. Both the callback and return-page verification now call `_settle_paid_order`, lock the payment row with `FOR UPDATE`, check the stored amount and payment link ID, and settle once. Subscription extension also locks the user row. Missing signature configuration fails closed; unrecognized product types cannot activate a subscription. Wallet topups use their existing `payos:<order>` idempotency key and never activate API plans. Unknown signed order callbacks are acknowledged to support the PayOS setup probe; return-page verification returns 404 for unknown orders. No production DB backfill was performed.

Reference: https://payos.vn/docs/du-lieu-tra-ve/webhook/

The callback currently requires an exact amount match. Partial/mismatched transfers require reconciliation; return-page verification also checks PayOS's `amountPaid` before settlement.

## Verification

```sh
python3 fe/build.py
python3 fe/check_overview.py
node --check fe/app.js
node --check fe/pages/data-journey.js
node --check fe/pages/pricing-journey.js
node tests/journey/catalog.test.cjs
node tests/journey/auth_return.test.cjs
python3 tests/journey/test_public_plans.py
python3 tests/journey/test_payment_settlement.py
node tests/journey/checkout.test.cjs
node tests/journey/analytics.test.cjs
node tests/journey/excel_starter.test.cjs
node tests/journey/browser_smoke.cjs
```

Browser tests use an isolated temporary Chrome profile and mocked API responses, never real payments. Set `CHROME_BIN` on non-macOS environments. Screenshots are written to the printed temporary directory. Test deployment of `/payment/plans` before publishing the new pricing UI. Verify a real free-account download, Auth0 return and PayOS sandbox/approved payment separately before declaring production checkout verified.


2026-09-23 verification: local unit/regression tests and JS/Python syntax checks pass; HTML rebuilt and overview checks pass. Payment tests use signed fixtures and a lock-aware fake session, not a live PostgreSQL integration. Browser UI checks at 390/768/1366 and executing the examples in Excel remain pending: computer-use permissions were unavailable and the in-app browser was unavailable. No real PayOS order/payment, production deployment, API-key usage or marketing publication was performed.

The root `CLAUDE.md` GA4 section still incorrectly says an External/Testing OAuth refresh token never expires. Google limits these tokens to seven days for Analytics scopes. Root `CLAUDE.md` is user/Claude-maintained and was not edited by Codex; this known documentation correction remains with its owner.
