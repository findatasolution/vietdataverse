window.DOCS_I18N_EN = {
  "ex.toc.label": "Contents",
  "ex.toc.overview": "What you'll get",
  "ex.toc.token": "Step 1 — Get an API token",
  "ex.toc.connect": "Step 2 — Connect with Power Query",
  "ex.toc.refresh": "Step 3 — Refresh the data",
  "ex.toc.datasets": "Dataset list",
  "ex.toc.troubleshoot": "Common issues",

  "ex.h1": "Pull data into Excel (Power Query)",
  "ex.lead": "\n      Pull Vietnamese financial data — gold, silver, FX, interest rates, CPI, global data — straight into <strong>Microsoft Excel</strong>\n      with <strong>Power Query</strong>, no coding needed. Data loads as a Table and refreshes with one click.\n    ",

  "ex.overview.h2": "What you'll get",
  "ex.overview.p": "Excel has built-in <strong>Power Query</strong> (Get &amp; Transform Data) — Google Sheets' <code>IMPORTDATA</code> equivalent, but more powerful: it reads both CSV and JSON, loads into a Table, and refreshes automatically.",
  "ex.overview.info": "\n        <strong>No extra install needed.</strong> Power Query ships with Excel 2016 and later (Windows &amp; Mac) and Microsoft 365. Unlike Google Sheets, Excel <strong>doesn't show an \"unverified app\" warning</strong>.\n      ",

  "ex.token.h2": "Step 1 — Get an API token",
  "ex.token.step1": "\n        <div class=\"doc-step-num\">1</div>\n        <div class=\"doc-step-body\">Open the <a href=\"/pages/developer.html\" style=\"color:var(--terracotta);\"><strong>Developer page</strong></a> and log in (sign up free if you don't have an account).</div>\n      ",
  "ex.token.step2": "\n        <div class=\"doc-step-num\">2</div>\n        <div class=\"doc-step-body\">Free accounts get an API key instantly, with a limit of <strong>1,000 requests/month</strong>.</div>\n      ",
  "ex.token.step3": "\n        <div class=\"doc-step-num\">3</div>\n        <div class=\"doc-step-body\">Click <strong>\"Copy\"</strong> to get the full key (~43 characters). Keep it secret.</div>\n      ",

  "ex.connect.h2": "Step 2 — Connect with Power Query",
  "ex.connect.step1": "\n        <div class=\"doc-step-num\">1</div>\n        <div class=\"doc-step-body\">In Excel: <strong>Data → Get Data → From Other Sources → From Web</strong> (or <strong>Data → From Web</strong>).</div>\n      ",
  "ex.connect.step2": "\n        <div class=\"doc-step-num\">2</div>\n        <div class=\"doc-step-body\">\n          Paste the dataset's URL (replace <code>YOUR_API_KEY</code> with your token). Example — 1 year of SJC gold prices:\n        </div>\n      ",
  "ex.connect.step3": "\n        <div class=\"doc-step-num\">3</div>\n        <div class=\"doc-step-body\">If Excel asks how to authenticate → choose <strong>Anonymous</strong> → <strong>Connect</strong> (the token is already in the URL).</div>\n      ",
  "ex.connect.step4": "\n        <div class=\"doc-step-num\">4</div>\n        <div class=\"doc-step-body\">\n          The Power Query window opens:\n          <ul>\n            <li><strong>JSON data</strong> (silver, interest rates, CPI…): click the <code>data</code> field → <strong>To Table</strong> → click the expand icon (↔) on the column header to split it into columns (date, value…).</li>\n            <li><strong>Gold prices as CSV</strong>: if you drop <code>page</code> and add <code>&amp;format=csv</code>, Excel reads it as a table directly, no expand needed.</li>\n          </ul>\n        </div>\n      ",
  "ex.connect.step5": "\n        <div class=\"doc-step-num\">5</div>\n        <div class=\"doc-step-body\">Click <strong>Close &amp; Load</strong> — the data loads into the sheet as a Table.</div>\n      ",
  "ex.connect.info": "\n        <strong>Tip:</strong> The <code>&amp;page=1&amp;limit=500</code> parameters make the API return a <em>flat list of rows</em> — Power Query expands it straight into a clean table.\n      ",

  "ex.refresh.h2": "Step 3 — Refresh the data",
  "ex.refresh.p": "Update anytime: <strong>Data → Refresh All</strong>. To automate:",
  "ex.refresh.ol": "\n        <li>Right-click the Table → <strong>Table → External Data Properties</strong> (or Data → Queries &amp; Connections → Properties).</li>\n        <li>Check <strong>\"Refresh data when opening the file\"</strong> and/or <strong>\"Refresh every N minutes\"</strong>.</li>\n      ",
  "ex.refresh.warn": "\n        Each refresh = 1 request against your monthly quota. Don't set an aggressive refresh interval across many queries at once.\n      ",

  "ex.datasets.h2": "Dataset list",
  "ex.datasets.p": "Every dataset on the Viet Dataverse homepage works in Excel. Append parameters to the URL: <code>?period=...&amp;page=1&amp;limit=500&amp;api_key=YOUR_API_KEY</code>",
  "ex.datasets.table": "\n        <thead><tr><th>Dataset</th><th>Endpoint</th><th>Main parameters</th><th>Returned columns</th></tr></thead>\n        <tbody>\n          <tr>\n            <td>Gold price</td>\n            <td><code>/api/v1/gold</code></td>\n            <td><code>type</code> = SJC · DOJI HN · PNJ · BTMC; <code>period</code></td>\n            <td>date · buy_price · sell_price</td>\n          </tr>\n          <tr>\n            <td>Silver price</td>\n            <td><code>/api/v1/silver</code></td>\n            <td><code>period</code></td>\n            <td>date · buy_price · sell_price</td>\n          </tr>\n          <tr>\n            <td>FX rate (VCB)</td>\n            <td><code>/api/v1/sbv-rate</code></td>\n            <td><code>bank</code> = VCB; <code>currency</code> = USD · EUR · JPY…; <code>period</code></td>\n            <td>date · buy · buy_cash · sell</td>\n          </tr>\n          <tr>\n            <td>Interbank rate (SBV)</td>\n            <td><code>/api/v1/sbv-interbank</code></td>\n            <td><code>period</code></td>\n            <td>dates · overnight · month_1 · month_3 · month_6…</td>\n          </tr>\n          <tr>\n            <td>Deposit rates</td>\n            <td><code>/api/v1/termdepo</code></td>\n            <td><code>period</code></td>\n            <td>date · term_1m · term_3m · term_6m · term_12m · term_24m</td>\n          </tr>\n          <tr>\n            <td>CPI / Inflation</td>\n            <td><code>/api/v1/macro/cpi</code></td>\n            <td><code>period</code></td>\n            <td>period · yoy_pct · months</td>\n          </tr>\n          <tr>\n            <td>Global data</td>\n            <td><code>/api/v1/global-macro</code></td>\n            <td><code>period</code></td>\n            <td>date · gold_price · silver_price · nasdaq_price</td>\n          </tr>\n        </tbody>\n      ",
  "ex.datasets.example": "The <code>period</code> parameter accepts: <code>7d</code> · <code>1m</code> · <code>1y</code> · <code>all</code>. Example — get <strong>1 year of deposit rates</strong>:",
  "ex.datasets.info": "\n        See the full endpoint list (including VN30, news…) in the <a href=\"api-docs.html\" style=\"color:var(--terracotta);\">API Reference</a>.\n      ",

  "ex.trouble.h2": "Common issues",
  "ex.trouble.q1": "401 error / \"Access to the resource is forbidden\"",
  "ex.trouble.a1": "Wrong or revoked token. Get the latest key on the <a href=\"/pages/developer.html\" style=\"color:var(--terracotta);\">Developer page</a> (each \"Generate New Key\" revokes the old one).",
  "ex.trouble.q2": "Power Query asks you to log in (Organizational / Windows…)",
  "ex.trouble.a2": "Choose <strong>Anonymous</strong>. The token already travels in the URL, so no other authentication is needed.",
  "ex.trouble.q3": "JSON data sits inside a single <code>data</code> column",
  "ex.trouble.a3": "That's expected — click <strong>To Table</strong>, then click the expand icon (↔) on the header to split it into columns. Or add <code>&amp;page=1&amp;limit=500</code> so the API returns a flat list of rows that's easier to expand.",
  "ex.trouble.contact": "Need help? Email <a href=\"mailto:findatasolution@gmail.com\" style=\"color:var(--terracotta);\">findatasolution@gmail.com</a> · See also the <a href=\"google-sheets.html\" style=\"color:var(--terracotta);\">Google Sheets guide</a>."
};
