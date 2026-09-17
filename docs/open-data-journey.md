# Open Data customer journey

Implemented locally on 2026-09-17; deployment and a real authenticated payment smoke test remain pending.

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
5. After verified payment, return to the same dataset, chart period, bank and method. Context contains no credentials and expires after 24 hours in session storage. No automatic download or API-key rotation occurs.

## Source of truth

- `fe/pages/data-journey.js`: dataset catalog, snapshot parsing, discovery, detail controls and bounded purchase context. Snapshot coverage is explicitly not full API history. Missing snapshots display an error rather than fabricated coverage.
- `GET /api/v1/payment/plans`: public prices, duration, monthly and burst quotas from `SUBSCRIPTION_PLANS` and `get_quota`. Does not access a database or expose credentials. Frontend checkout remains disabled if these facts cannot be loaded; retry is provided.
- `fe/pages/pricing-journey.js`: consumption of server plan facts and contextual comparison. Existing plan IDs, billing amounts, student discount and access enforcement are unchanged. The pricing catalog grid also appends one extra tile, **Giá xăng dầu & dự báo**, linking to the standalone `fuel-forecast.html` product page — its coverage line is read live from `/api/v1/fuel-forecast/E5RON92` (no static snapshot exists). It is deliberately *not* in `data-journey.js`'s `catalog`: that array is pinned to the SPA overview charts (`catalog.test.cjs`), and fuel has no `#data/portal/chart/<id>` route. This tile is currently the only on-site link to the fuel forecast page.
- Free API currently exposes available history within its quota; there is no ten-download lifetime gate. Public snapshot windows differ by dataset.
- PayOS return/cancel URLs point to pricing, where server verification determines success. Verification failure does not imply successful payment and retains the order query for retry.
- Auth0 callback compares the full same-origin return URL, including the dataset hash; returning to the same `index.html` pathname no longer drops the selected dataset.
- The new Open Data offer uses one-time PayOS payments, not automatic renewal. This does not describe the separate wallet-funded marketplace subscription system.

## Measurement

Uses the existing `gtag` when available: `dataset_detail_view`, `dataset_download_success` (preview CSV triggered), `dataset_upgrade_view`. No tokens, email or payment details are included. These events do not prove the downloaded file was opened or an integration succeeded. Existing purchase telemetry remains separate; end-to-end conversion attribution is not yet established.

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
node tests/journey/browser_smoke.cjs
```

Browser tests use an isolated temporary Chrome profile and mocked API responses, never real payments. Set `CHROME_BIN` on non-macOS environments. Screenshots are written to the printed temporary directory. Test deployment of `/payment/plans` before publishing the new pricing UI. Verify a real free-account download, Auth0 return and PayOS sandbox/approved payment separately before declaring production checkout verified.
