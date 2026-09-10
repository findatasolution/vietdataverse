window.DOCS_I18N_EN = {
  "gs.toc.label": "Contents",
  "gs.toc.overview": "Flow overview",
  "gs.toc.register": "Register as a seller",
  "gs.toc.upload": "Upload a product",
  "gs.toc.payout": "Pricing &amp; Payout",
  "gs.toc.important": "Important notes",
  "gs.toc.packspec": "Pack structure spec",

  "gs.h1": "Seller Guide — Sell Knowledge Products",
  "gs.lead": "Become a seller on the Viet Dataverse Knowledge Market in 5 minutes. Create a seller account, upload a file, the system auto-validates it, and your product goes live immediately — no admin review needed.",

  "gs.overview.h2": "Flow overview",
  "gs.overview.p": "Create a seller account → Upload a file → System auto-validates → Product goes live immediately (no admin review).",

  "gs.register.h2": "Step 1 — Register as a seller",
  "gs.register.step1": "\n        <div class=\"doc-step-num\">1</div>\n        <div class=\"doc-step-body\">Log in to Viet Dataverse (top-right of the header).</div>\n      ",
  "gs.register.step2": "\n        <div class=\"doc-step-num\">2</div>\n        <div class=\"doc-step-body\">Go to the <strong>Knowledge Market</strong> tab.</div>\n      ",
  "gs.register.step3": "\n        <div class=\"doc-step-num\">3</div>\n        <div class=\"doc-step-body\">Click <strong>\"+ Become a Seller\"</strong>.</div>\n      ",
  "gs.register.step4": "\n        <div class=\"doc-step-num\">4</div>\n        <div class=\"doc-step-body\">Read the Terms → check the agree box → click <strong>\"Continue\"</strong>.</div>\n      ",
  "gs.register.step5": "\n        <div class=\"doc-step-num\">5</div>\n        <div class=\"doc-step-body\">The system sends a verification email — open your inbox and click the link to activate.</div>\n      ",
  "gs.register.info": "\n        <strong>Tip:</strong> The verification email is valid for 24 hours. If you don't receive it, click \"Resend email\" after 60 seconds.\n      ",

  "gs.upload.h2": "Step 2 — Upload a product",
  "gs.upload.step1": "\n        <div class=\"doc-step-num\">1</div>\n        <div class=\"doc-step-body\">After verifying your email, the action bar shows <strong>\"Seller dashboard\"</strong>.</div>\n      ",
  "gs.upload.step2": "\n        <div class=\"doc-step-num\">2</div>\n        <div class=\"doc-step-body\">Click <strong>\"Upload new product\"</strong>.</div>\n      ",
  "gs.upload.step3": "\n        <div class=\"doc-step-num\">3</div>\n        <div class=\"doc-step-body\">\n          <p style=\"margin:0 0 12px;\">Fill in the form:</p>\n          <table class=\"doc-table\">\n            <thead>\n              <tr><th>Field</th><th>Requirement</th></tr>\n            </thead>\n            <tbody>\n              <tr><td>Title</td><td>3–200 characters, Vietnamese OK</td></tr>\n              <tr><td>Slug</td><td>URL-friendly, no diacritics, use <code>-</code> (e.g. <code>vn-cpi-schema</code>)</td></tr>\n              <tr><td>Description</td><td><strong>At least 50 characters</strong> — describe the content, audience, value</td></tr>\n              <tr><td>Category</td><td>Pick 1 of 8 categories</td></tr>\n              <tr><td>Format</td><td>.md / .json / .yaml / .csv</td></tr>\n              <tr><td>Price (credits)</td><td><code>0</code> = free. <code>1 credit = 1,000 VND</code></td></tr>\n              <tr><td>Preview %</td><td>0–40, default 25 (how much a buyer can preview before buying)</td></tr>\n              <tr><td>Frameworks</td><td>Compatible AI tools, comma-separated (<code>claude, langchain</code>)</td></tr>\n              <tr><td>File</td><td>At least 100 bytes, UTF-8</td></tr>\n            </tbody>\n          </table>\n        </div>\n      ",
  "gs.upload.step4": "\n        <div class=\"doc-step-num\">4</div>\n        <div class=\"doc-step-body\">\n          <p style=\"margin:0 0 8px;\">Click <strong>\"Upload\"</strong> — the system runs 4 automatic checks (a few seconds):</p>\n          <ul>\n            <li>Malware / magic bytes</li>\n            <li>File format (parseable)</li>\n            <li>Minimum content (≥ 100 bytes, description ≥ 50 chars)</li>\n            <li>No PII (national ID, personal phone numbers)</li>\n          </ul>\n        </div>\n      ",
  "gs.upload.step5": "\n        <div class=\"doc-step-num\">5</div>\n        <div class=\"doc-step-body\">Pass everything → the product <strong>goes live immediately</strong> (status: published).</div>\n      ",
  "gs.upload.warn": "\n        <strong>Rejected?</strong> The modal shows which check failed and how to fix it. Fix the file/description and re-upload.\n      ",

  "gs.payout.h2": "Step 3 — Pricing &amp; Payout",
  "gs.payout.p1": "For every transaction:",
  "gs.payout.list": "\n        <li><strong>Seller keeps 90%</strong> (VND-equivalent value)</li>\n        <li><strong>Platform keeps 10%</strong></li>\n      ",
  "gs.payout.p2": "Pending revenue accumulates in your <strong>Seller Dashboard</strong>. Once it reaches <strong>500,000 VND</strong>, you can request a payout via bank transfer (handled manually by admin — you'll be emailed for your account details).",

  "gs.important.h2": "Important notes",
  "gs.important.copyright": "\n        <strong>Copyright:</strong> Sellers are fully legally responsible for uploaded content. 3 violations (via DMCA or buyer reports) results in a permanent ban.\n      ",
  "gs.important.pii": "\n        <strong>PII:</strong> Never upload a file containing someone else's national ID or phone number — it will be rejected immediately.\n      ",
  "gs.important.tax": "\n        <strong>Tax:</strong> Revenue ≥ 100M VND/year must be declared for personal income tax under Circular 40/2021. Sellers are responsible for their own tax filing.\n      ",

  "gs.faq.q1": "Can I edit a product after publishing it?",
  "gs.faq.a1": "Currently only metadata (title, description, price) can be edited. File content requires uploading a new version (Phase 2).",
  "gs.faq.q2": "Can I delete a product?",
  "gs.faq.a2": "Yes. Go to Seller Dashboard → click <strong>\"Hide\"</strong> on the product. Buyers who already purchased it can still download it for 30 days.",
  "gs.faq.q3": "What happens if a buyer reports my product?",
  "gs.faq.a3": "1 report → a warning. 3 reports within 12 months → the product is automatically hidden and the seller is warned. If you believe a report is incorrect, contact <code>support@vietdataverse.online</code>.",
  "gs.faq.q4": "When do I get paid out?",
  "gs.faq.a4": "Once your pending balance reaches ≥ 500K VND, email a request to <code>payout@vietdataverse.online</code>. Admin processes it within 5 business days.",

  "gs.packspec.h2": "Knowledge Pack structure spec",
  "gs.packspec.p1": "The file structure requirements have their own page for easy reference. The spec page covers: the 3 pack types, the 7 required sections, a pre-submit checklist, banned content, and the automatic disclaimer.",
  "gs.packspec.card": "\n        <div>\n          <div style=\"font-family:'Lora',Georgia,serif;font-size:1rem;font-weight:500;color:var(--near-black);margin-bottom:4px;\">Knowledge Pack structure spec</div>\n          <div style=\"font-size:0.875rem;color:var(--olive-gray);\">7 required sections · 3 pack types · 12-point checklist · Real examples</div>\n        </div>\n        <a href=\"knowledge-pack-spec.html\" style=\"display:inline-flex;align-items:center;gap:6px;background:var(--terracotta);color:#faf9f5;padding:10px 18px;border-radius:8px;font-size:0.875rem;font-weight:500;text-decoration:none;white-space:nowrap;\">\n          View the structure spec →\n        </a>\n      ",
  "gs.packspec.p2": "Need help? Email <a href=\"mailto:support@vietdataverse.online\" style=\"color:var(--terracotta);\">support@vietdataverse.online</a>"
};
