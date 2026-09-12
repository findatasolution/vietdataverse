# Viet Dataverse — Product Backlog

> Workflow: mỗi session chọn 1 item, nói "Làm [ID]" → Claude Code build, bạn review + approve.  
> Priority: 🔴 HIGH · 🟡 MEDIUM · ⚪ LOW/DEFER

---

## 🔴 HIGH — Làm ngay (core revenue + stability)

### [REV-01] VN30 data source (`vnstock3`) — gỡ khỏi API/FE, giữ nội bộ để đối chiếu
- `vnstock3` (bọc SSI/TCBS) cấm mọi hoạt động thương mại kể cả gián tiếp — áp dụng cho cả bản miễn phí vì VDV là tổ chức thương mại. Chi tiết: `CLAUDE.md` mục "VN30 data source (`vnstock3`)..."
- ✅ **Xong (2026-09-10)**: `be/routers/vn30_data.py` không còn endpoint `/vn30/*` hay `/market/vnindex` nào — gỡ TOÀN BỘ, không chỉ field giá (profile/sector/OHLCV/BCTC-quý/ratio/VN-Index đều là vnstock3-sourced, theo đúng lý luận "đi theo chuỗi nguồn gốc dữ liệu"). Đã rà và sửa mọi chỗ trên `fe/` từng hiển thị/nhắc tới dữ liệu này (xem CLAUDE.md để có danh sách file đầy đủ). Crawler vnstock3 (`crawl_vn30_*.py` + GitHub Actions) **giữ nguyên, vẫn chạy ngầm** — chỉ đường ra API/FE bị gỡ.
- ⏳ **Còn lại**: viết crawler BCTC tự động từ IR/cổng công bố thay vnstock3 — đã chứng minh khả thi thủ công cho 27 công ty (`listed_company_financials`), nhưng chưa tự động hoá. Đây là điều kiện để REV-02 bán được.
- **Prototype `crawl_tools/crawl_bctc_financials.py` đã chạy được với Gemini vision (2026-09-10)** — tìm PDF (mirror vietstock) → định vị trang bằng OCR cục bộ rẻ → gửi ảnh cho LLM vision trích cấu trúc → validate cơ học (`validate_financial_statements.py`, chặn dữ liệu sai không cho `validated=true`). Đã test thật: VNM/HDB/SHB/VIB (FY2025) sạch; FPT FY2024 (test đối chứng) lộ ra 2 lỗi hệ thống đã sửa (định vị trang không cố định 2 trang; validator từng trộn lẫn nhiều `period_end`) — lưới validate chặn đúng, không có gì sai lọt thành `validated=true`.
- **Cập nhật (2026-09-10, cùng ngày)**: FPT FY2024 đã sửa xong hoàn toàn thủ công (đối chứng OCR 300dpi tươi — phát hiện thêm cấu trúc TT200 còn thiếu trong dict: mã 224 "TSCĐ thuê tài chính" là con thứ 3 của 220 cùng 221/227, mã 226 từng gán sai cha, mã 240 cần cả 241 lẫn 242, mã 430/431 thiếu — đã bổ sung `bctc_line_code_dict`). MSN FY2024 crawl tự động sạch ngay (0 lỗi). PLX FY2024 lộ thêm lỗi Gemini đọc sai *giá trị* (không phải cấu trúc) ở nhiều mã cùng lúc — mã 200 lệch >12 lần (273 nghìn tỷ thay vì 21.7 nghìn tỷ), mã 210/211/216/260/261/262/415/416/418/420 đều bị đọc sai chữ số — đã sửa thủ công bằng OCR 300dpi tươi đối chứng, 0 vi phạm ARITHMETIC. **Kết luận: Gemini free tier có thể sai giá trị nghiêm trọng ở bất kỳ mã nào, không chỉ mã hiếm — lưới validate + đối chứng thủ công vẫn là bắt buộc, không thể tự động hoá 100% cho tới khi có model tốt hơn.**
- **Quyết định hướng nguồn LLM (2026-09-10): Gemini free tier không đủ dùng** (rate limit quá chặt cho khối lượng crawl thật, đã gặp timeout nhiều lần khi test) — **chuyển sang chạy model vision mã nguồn mở (ứng viên: Qwen2.5-VL-32B, hoặc GLM-4.5V/GLM-4.1V) trên Kaggle** (GPU free tier — P100 16GB hoặc 2×T4 32GB, 30 giờ/tuần). Ràng buộc thực tế: Kaggle không phải server thường trực (session ~9-12h, cần tunnel cloudflared/ngrok lấy URL tạm) → vận hành kiểu **batch** (bật notebook, crawl 1 mẻ, tắt), không phải service chạy nền liên tục như Gemini API. Việc cần làm: (1) viết Kaggle notebook khởi động vLLM/Ollama + model + tunnel, (2) tách lớp gọi LLM trong `crawl_bctc_financials.py` để trỏ được vào endpoint OpenAI-compatible này thay vì Gemini REST — **chưa làm**, chỉ mới quyết định hướng.
- Kế hoạch đầy đủ: `docs/research/2026-09-08-financial-statements-subscription-plan.md`.
- **Tại sao HIGH:** gate bắt buộc trước khi bán gói BCTC. Rủi ro pháp lý ở bề mặt public đã xử lý; rủi ro còn lại chỉ nằm ở crawler nội bộ (đã chấp nhận có kiểm soát, xem CLAUDE.md).

### [REV-02] Gói BCTC cá nhân (25-55k/tháng) — sau khi REV-01 xong
- Bán truy cập báo cáo tài chính nhiều năm (không phải giá/ratios) cho cá nhân, target sinh viên/nhà nghiên cứu tài chính.
- Kế hoạch đầy đủ: `docs/research/2026-09-08-financial-statements-subscription-plan.md`.
- **Phụ thuộc REV-01** — không bán được nếu chưa có crawler BCTC nguồn sạch.
- Marketing qua CLB sinh viên tài chính các trường (không cold-email — vi phạm NĐ 91/2020), không phải quảng cáo trả tiền.

### [API-01] API Docs page — viết lại rõ ràng cho người mua
- Trang `/pages/api-docs.html` hiện tại quá kỹ thuật
- Rewrite: mở đầu bằng use-case ("Tôi muốn pull giá vàng vào Python"), sau đó mới show endpoint
- Thêm code snippet Python/JS cho mỗi endpoint chính
- Thêm section "Rate limits & Pricing" rõ ràng
- **Tại sao:** API là core revenue, docs tệ = không ai mua

### [API-02] Pagination cho tất cả data endpoints
- Thêm `?page=1&limit=50` cho `/gold`, `/silver`, `/sbv-rate`, `/termdepo`, `/vn30/ohlcv`
- Default limit: 30 rows
- Response thêm `{"total": N, "page": 1, "limit": 30, "data": [...]}`
- **Tại sao:** AI agent thường pull theo chunk, pagination là must-have

### [API-03] API Key onboarding flow cải thiện
- Sau khi tạo key, show hướng dẫn 3 bước ngay trên UI (không redirect đi đâu)
- Thêm "Test your key" button — gọi `/gold` với key của họ, show kết quả live
- **Tại sao:** Reduce friction cho user mới

### ~~[KM-01] Web reader cho knowledge packs~~ ✅ Done
### ~~[KM-02] "Copy to Claude" button trên library page~~ ✅ Done

### [CONTENT-01] Nâng cấp 5 pack mới — thêm section "Cách dùng"
- Mỗi pack thêm section đầu: dành cho developer (IDE) và researcher (Copy to Claude)
- Pack 5 (Data Sources): thêm code snippet Python sẵn chạy được
- Pack 3 (Term Deposit): thêm bảng so sánh lãi suất thực vs nominal
- **Tại sao:** Content hiện tại chưa đủ actionable

---

## 🟡 MEDIUM — Làm sau khi HIGH xong

### [DQ-01] DQ agent phải chặn/báo động, không chỉ gửi email
- Sự cố 2026-07-18: 24h.com.vn công bố DOJI thiếu 1 chữ số (`14,450` thay vì `144,500`); giá sai lên chart + API và nằm đó 20 ngày
- `crawl_tools/data_quality_check.py` ĐÃ phát hiện (rule range 50M–200M) nhưng chỉ gửi email WARNING tới `findatasolution@gmail.com` — không ai đọc, workflow vẫn xanh
- Crawler đã được vá (validate trước insert, xem `crawl_tools/gold_validation.py`) nên lỗi cùng dạng không lọt nữa; phần còn thiếu là **lớp cảnh báo**
- Cần: DQ agent exit non-zero khi có ERROR (không chỉ CRITICAL) để workflow đỏ → GitHub email chủ repo, giống `uptime-check.yml`; cân nhắc chạy pytest `crawl_tools/` trong CI
- Sweep 2026-08-07 sau khi dọn: **0 ERROR** trên toàn bộ 8 bảng vĩ mô
- **Tại sao:** cảnh báo không ai đọc = không có cảnh báo

### [DQ-02] Lỗ hổng dữ liệu GSO còn tồn đọng
- `vn_gso_cpi_monthly`: thiếu hẳn `2025-03` và `2025-06`; 17 tháng thiếu `cpi_yoy_pct`; mới nhất `2026-06`
- `vn_gso_gdp_quarterly`, `vn_gso_iip_monthly`, `vn_gso_trade_monthly`: **0 rows** — bảng tồn tại nhưng chưa từng có dữ liệu
- `global_macro`: `sp500`/`dowjones` NULL 31 ngày trong 1 năm qua (chủ yếu ngày FRED fallback bù cho cuối tuần/nghỉ lễ); nay public đúng là `null`, không còn `0`
- **Tại sao:** chart CPI khuyết điểm, và schema gợi ý có GDP/IIP/trade trong khi thực tế không có

### [REV-03] Tìm nguồn VN-Index sạch để khôi phục chart
- VN-Index bị gỡ khỏi Overview grid + market-overview panel 2026-09-10 (cùng đợt REV-01) vì nguồn duy nhất (`vn_macro_vnindex_daily`) là vnstock3-sourced.
- Đã thử nhanh, chưa ra: Yahoo Finance (không có mã VN-Index trong coverage), SSI iBoard (nền tảng giao dịch riêng của SSI, khả năng ToS hạn chế thương mại tương tự vnstock3, không an toàn hơn).
- Hướng chưa thử: HOSE có thể tự công bố báo cáo giao dịch/tổng kết hàng ngày dạng PDF (như cách công bố BCTC bắt buộc) — nếu có, đây là nguồn công bố bắt buộc, không phải sản phẩm dữ liệu vendor, giống pattern đã dùng cho BCTC.
- **Tại sao MEDIUM, không HIGH:** VN-Index là 1/10 mini-chart, không chặn REV-01/REV-02. Khôi phục khi tìm được nguồn sạch, không vội.

### [API-04] Webhook / scheduled data push
- User đăng ký nhận data mới qua webhook URL của họ
- Mỗi sáng sau khi crawler chạy → push data mới tới endpoint
- **Tại sao:** Fintech startup cần data pipeline tự động, không muốn poll

### [API-06] Officialize 1s Pulse API
- Audit 2026-07-05: `ARGUS_FINTEL_DB.mri_analysis` có 4.044 rows (2.022 VI + 2.022 EN), 300 rows/7 ngày; query 50 rows hiện khoảng 1,3 ms
- Endpoint `/api/v1/market-pulse` đang public và trả tối đa 50 bài, nhưng Developer catalog đang ghi `premium_developer` — cần chốt một access policy duy nhất
- Thêm pagination + filter (`source`, `label`, `min_mri`, time range), `total`, freshness metadata và response contract ổn định
- Thêm index `(lang, generated_at DESC)` và `(label, generated_at DESC)`; đổi `source_date` từ text sang timestamp
- Dedup/backfill 52 nhóm trùng `(url, lang)`, thêm unique constraint/upsert; chuẩn hoá label `TRADE_GEOPOLITICS`
- Chốt public preview vs API-key full response; review quyền redistribution theo từng RSS source trước khi thương mại hoá nội dung tóm tắt
- **Tại sao:** DB đủ nhanh để phục vụ API nhưng schema, access policy, dedup và licensing chưa production-grade

### [RESEARCH — CHƯA PHÊ DUYỆT] Các lựa chọn nguồn miễn phí cho 1s Pulse
- Đây chỉ là kết quả khảo sát, **không phải hạng mục đã chốt để triển khai**. Không code/deploy mở rộng nguồn cho tới khi user chọn phương án.
- Pipeline hiện đã dùng `feedparser`; nguồn Việt bị bỏ ngày 2026-06-30 để giới hạn scope ở sentiment quốc tế, không phải do lỗi parser
- Audit 2026-07-05: RSS CafeF chứng khoán trả 50 entries (XML hợp lệ nhưng sai Content-Type), VnExpress Kinh doanh trả 60 entries và parse sạch
- Option miễn phí khả thi: RSS CafeF/VnExpress/Vietstock; RSS/HTML press room của IMF, ngân hàng trung ương, chính phủ và corporate IR; SEC EDGAR public API; YouTube Data API free quota/channel feed; Bluesky public API và Mastodon public endpoints
- Không coi là option miễn phí production-grade: X API hiện pay-per-use; LinkedIn cấm crawler và read scopes bị giới hạn; Truth Social API trả 403 từ datacenter trong audit này
- Audit thư viện unofficial 2026-07-05: `ntscraper==0.4.0` kiểm tra 10 Nitter instances nhưng không tìm được instance hoạt động; `twikit==2.3.3` không-auth lỗi `Couldn't get KEY_BYTE indices` trên Python 3.12 và luồng chuẩn cần account/cookie; `Mastodon.py==2.2.1` gọi Truth account statuses vẫn nhận 403 dù instance metadata trả 200
- Không đưa `ntscraper`, `twikit` hoặc Truth hidden endpoints vào production: ngoài độ ổn định thấp, điều khoản hiện tại của X và Truth Social đều cấm scraping/automated access khi chưa được cho phép
- Nếu sau này được duyệt: tách lane nguồn, đặt quota/ranking riêng, lưu provenance/trust metadata, dedup và chỉ public metadata + derived MRI + canonical link sau khi review license
- **Tại sao:** feedparser giúp RSS nhanh/ổn định nhưng không biến social platform đóng thành nguồn miễn phí/bền vững

### [CHAT-01] MVP "Chat với dữ liệu VN" — prototype
- Interface chat đơn giản, pre-loaded với context VN
- Mỗi câu hỏi → tự gọi API lấy data realtime → trả lời
- Target: finance student / researcher không biết code
- **Tại sao:** TAM lớn nhất, nhưng phức tạp hơn — làm sau khi API stable

### [KM-03] 8 pack cũ (id 6–13) đã bị disable — chưa từng có file thật, cần chốt hướng trước khi viết lại
- **2026-09-07**: audit phát hiện cả 8 pack (`tt200-chart-of-accounts-vn`, `vn-stock-trader-glossary`, `vn-macro-indicators-context`, `vn-banking-regulation-schema`, `vn-finance-sentiment-lexicon`, `vn-credit-risk-scoring-schema`, `vn-esg-reporting-framework`, `vn-crypto-regulation-protocols`) có `status='published'` nhưng **`file_r2_key = NULL`** — không phải thiếu chất lượng, mà **chưa từng có file thật được upload lên R2** (seed data từ đầu, xác nhận không tồn tại trong R2 bucket). 2 buyer đã "mua" (cả 2 đều 0 credit, free) bấm Download/Copy to Claude thì nhận lỗi 503 "Mock data — chờ admin setup R2 bucket."
- **Đã xử lý ngay:** đổi `status → 'disabled'` cho cả 8 id (chặn buyer mới mua trúng hàng rỗng; 2 buyer cũ vẫn giữ quyền re-download 30 ngày nếu sau này có file thật)
- **Bug nhỏ đi kèm, chưa fix:** nút "Copy to Claude" (`fe/app.knowledge.js` `copyToClaudeFromLibrary`) không check `res.ok` khi gọi `/knowledge/download/*`, nên khi lỗi chỉ hiện message chung chung "Không lấy được nội dung pack." thay vì message thật từ backend như nút "Tải file" đang làm đúng
- **Trước khi viết lại nội dung**, cân nhắc lại cách tiếp cận — xem [[project_product_strategy]]: bán knowledge pack tĩnh có traction ~0 (2 lượt "mua" duy nhất của lô này đều free), khớp với kết luận đã chốt tháng 7 rằng <5% marketplace skill/MCP tương tự monetize được vì thị trường mặc định kỳ vọng miễn phí. Hướng thay thế đang cân nhắc: biến 8 domain này thành live context/tool gọi API thay vì file .md tĩnh, tận dụng đúng lợi thế dữ liệu sống thay vì cạnh tranh ở nội dung giải thích khái niệm (LLM đã biết sẵn phần lớn). Chưa chốt.
- **Tại sao:** buyer bấm mua phải sản phẩm rỗng là trải nghiệm tệ nhất có thể có trên marketplace; viết lại nội dung trước khi trả lời được "domain này thị trường có cần không" là lãng phí công sức

### ~~[I18N-01] Trang docs (`fe/pages/*.html`) không có bản tiếng Anh~~ ✅ Done cho 7 trang dev-facing
- **2026-09-09**: audit xác nhận `fe/pages/*.html` không có `data-i18n`, `docs-sidebar.js` không có logic lang, toggle En/Vi của SPA (`app.js`) không lan sang docs độc lập.
- **2026-09-10 — đã triển khai** cơ chế mới, không tái dùng `app.js`: `fe/pages/docs-i18n.js` (engine dùng chung, đọc/ghi cùng key `localStorage.lang` với SPA nên chọn ngôn ngữ ở SPA và ở docs đồng bộ) + `fe/pages/docs-i18n-data/<page>.js` (dictionary EN riêng từng trang, key = `data-i18n="..."` gắn trên từng block). `docs-sidebar.js` chỉ render nút toggle (`#docs-lang-toggle`) khi trang có khai báo `window.DOCS_I18N_EN` — 6 trang chưa dịch (terms/privacy/takedown/cookie-policy/about-us/google-sheets-appscript) không hiện nút, tránh trải nghiệm "bấm EN mà không đổi gì".
- **Đã dịch đầy đủ 7 trang dev/agent-builder-facing** (đúng phạm vi đã chốt, loại legal ra vì rủi ro dịch sai pháp lý chưa qua luật sư): `docs.html` (20 key), `api-docs.html` (43 key, kèm cả `GROUP_LABELS`/text JS-generated của endpoint catalog fetch động — nghe event `docs-lang-changed` để re-render đúng ngôn ngữ), `guide-buyer.html` (50 key), `guide-seller.html` (45 key), `knowledge-pack-spec.html` (65 key, gồm cả 2 block skeleton + 2 ví dụ dài dịch nguyên khối), `google-sheets.html` (53 key), `excel.html` (40 key). Mỗi file đã verify: số key trong HTML khớp 100% số key trong dictionary (không thiếu/thừa), HTML parse sạch, JS syntax hợp lệ.
- **Giới hạn đã biết:** `ep.description` (mô tả endpoint) trong `api-docs.html` đến từ backend `/api/v1/developer/endpoints`, vẫn tiếng Việt — dịch phần này cần đổi backend, ngoài phạm vi lần này. Code block/URL/tên biến giữ nguyên (không dịch), đúng chủ đích.
- **Còn lại, chưa làm** (ngoài phạm vi đã chốt 2026-09-09): terms.html, privacy.html, takedown.html, cookie-policy.html, about-us.html, google-sheets-appscript.html — vẫn tiếng Việt only, cần quyết định riêng do rủi ro dịch legal.

### [INFRA-01] Auto smoke test API sau mỗi push
- GitHub Action: sau mỗi push lên main → curl các endpoint chính, check response shape
- Alert nếu endpoint trả về 500 hoặc data rỗng
- **Tại sao:** Tránh production silent failures

### [ADMIN-01] Admin: export user list CSV
- Trang admin thêm button "Export users" → download CSV (email, created_at, plan)
- **Tại sao:** Cần cho email marketing, không muốn phụ thuộc vào SQL query

---

## ⚪ LOW / DEFER — Khi có traction

### [CHAT-02] Chat subscription billing — ₫99k/tháng
- Chỉ build khi CHAT-01 có người dùng thực
- Defer cho đến khi có ít nhất 20 beta users

### [KM-04] Seller onboarding flow cải thiện
- Hiện tại seller flow đã work, đủ dùng
- Cải thiện UX khi có seller thực sự muốn đăng ký

### [API-05] SDK Python/JS cho Viet Dataverse API
- Wrap API vào package `pip install vietdataverse`
- Defer đến khi có >50 API users thực

### [CONTENT-02] Thêm pack mới — "Đọc BCTC Ngân hàng VN"
- Target: analyst đọc báo cáo tài chính ngân hàng
- Tier 2 pack (100 credits)
- Defer cho đến khi 5 pack mới đã stable và được dùng

### [CONTENT-03] Pack "Agent vàng SJC tự động"
- Tier 3 pack kết hợp knowledge + API call thực
- Demo: agent tự pull premium SJC hàng ngày, alert khi bất thường
- Killer feature nhưng phức tạp — làm sau

---

---

## ⚖️ LEGAL — Phải làm trước khi scale (không phải kỹ thuật)

> Không cần Claude Code build — cần bạn tự xử lý hoặc hỏi luật sư.  
> Ghi lại đây để không bị bỏ sót khi có revenue thực.

### [LEGAL-01] 🔴 Marketplace có cần đăng ký sàn TMĐT không?
- **Rủi ro:** Nghị định 85/2021/NĐ-CP quy định nếu vận hành "sàn giao dịch TMĐT" (platform để bên thứ 3 bán hàng) → cần đăng ký với Bộ Công Thương tại website.gov.vn
- **Câu hỏi cần trả lời:**
  - Viet Dataverse có phải "sàn" không, hay chỉ là "website TMĐT" (bán sản phẩm của chính mình)?
  - Nếu chỉ bán VD Official packs (là của mình) → website TMĐT thông thường, không cần đăng ký sàn
  - Nếu có seller bên ngoài bán → có thể cần đăng ký sàn
- **Hành động:** Giữ marketplace ở chế độ "VD Official only" cho đến khi có tư vấn pháp lý rõ ràng, hoặc giới hạn seller là cá nhân bạn

### [LEGAL-02] 🔴 Crawl dữ liệu tự động — từng nguồn
- **SBV (sbv.gov.vn):** Dữ liệu nhà nước, công khai → rủi ro thấp. Không có ToS cấm crawl rõ ràng. Nên thêm attribution "Nguồn: NHNN Việt Nam"
- **GSO (gso.gov.vn):** Tương tự SBV — công khai, low risk
- **BTMC / DOJI / SJC / PNJ (giá vàng):** Đây là doanh nghiệp tư nhân. Website của họ có ToS không cho phép scrape thương mại. **Rủi ro trung bình** — hiện chưa có tiền lệ kiện tụng ở VN, nhưng khi có traction lớn có thể bị contact
- **ACB (lãi suất tiết kiệm):** Ngân hàng, ToS thường cấm automated access. **Rủi ro trung bình**
- **TCBS API (unofficial):** Không có authorization. **Rủi ro cao** nếu dùng thương mại — họ có thể block IP hoặc gửi legal notice
- **Yahoo Finance:** ToS cấm commercial scraping rõ ràng. `yfinance` là wrapper unofficial. **Rủi ro cao cho commercial use**
- **Hành động:** Thêm attribution rõ ràng cho mọi nguồn; cân nhắc liên hệ BTMC/ACB xin phép chính thức khi có traction; tránh resell raw data của Yahoo Finance trực tiếp

### [LEGAL-03] 🟡 Bảo vệ dữ liệu cá nhân người dùng (Nghị định 13/2023)
- VN PDPA có hiệu lực từ 07/2023: thu thập email, thông tin thanh toán cần có Privacy Policy + consent rõ ràng
- **Kiểm tra:** Trang Privacy Policy hiện tại (`/legal/privacy`) đã đủ chưa
- **Cần có:** Điều khoản nào thu thập dữ liệu gì, lưu bao lâu, chia sẻ với ai (Auth0, PayOS)
- **Hành động:** Review và update Privacy Policy page

### [LEGAL-04] 🟡 Copyright của knowledge packs
- Content trong pack do bạn viết → bạn sở hữu, OK
- Nếu dùng số liệu từ GSO/SBV trong pack → cần citation, không được trình bày như data của mình
- Nếu seller bên ngoài upload pack có nội dung vi phạm → bạn cần DMCA takedown flow (đã có trong roadmap)
- **Hành động:** Thêm Terms for Sellers rõ ràng khi mở seller onboarding

### [LEGAL-05] ⚪ Giấy phép kinh doanh cá nhân
- Nếu có revenue thực từ API/marketplace → cần đăng ký hộ kinh doanh cá nhân hoặc công ty
- Ngưỡng thực tế: khi revenue > 100 triệu/năm thì bắt buộc kê khai thuế
- PayOS yêu cầu thông tin doanh nghiệp/cá nhân để settlement — kiểm tra lại account PayOS hiện tại
- **Hành động:** Defer đến khi có revenue thực, nhưng đừng để quá lâu

---

## Đang chờ triển khai / xác minh

- [x] **Prod chuyển từ Render → Hetzner box (shared với mythreel.studio)** — `vietdataverse.online` + `www` đã trỏ về box `62.238.25.95`, chạy container FastAPI (API + FE) sau Caddy chung, cert Let's Encrypt production hợp lệ, RAM ~68MB/640MB. Auto-deploy qua GitHub Actions (`deploy-hetzner.yml`) đã bật + xanh: mỗi push `main` và mỗi lần "Generate Static Chart Data" → box `git reset --hard origin/main` + `docker compose up -d --build`. **Hết cảnh prod stale do quên manual redeploy.** Chi tiết: `DEPLOY.md`.
  - [x] DNS `api.vietdataverse.online A → 62.238.25.95` đã thêm (2026-07-11). Caddy tự cấp cert Let's Encrypt hợp lệ khi resolve; verified admin.html → 200, `/api/v1/gold` → 401, Excel taskpane → 200. Sống lại toàn bộ URL `api.*` tuyệt đối trong docs/knowledge pack, Excel add-in, CI smoke-test + crawl webhook, SEO JSON-LD/sitemap — không đổi code.
  - Còn lại (user): sau vài ngày ổn định → xoá service Render.
  - [x] Fix path `/api/docs` → thật (2026-07-11): Swagger ở `/docs`, JSON ở `/openapi.json` (FastAPI mặc định; `/api/docs` chưa từng tồn tại → 404). Sửa `sitemap.xml`, `_layout_head.html` (contentUrl→`/openapi.json`, link→`/docs`), `fe/llms.txt`, và allowlist `be/middleware.py`. Không còn `/api/docs` nào trong repo.
- [x] Admin dashboard period report — 24h / 7d / YTD + API activity; code trong `c4a2d930f`, đã deploy lên Hetzner box (origin/main HEAD chạy trên prod).
- [x] API access audit — track public-anonymous/rejected calls + khoá analytics/generation routes cho admin; code trong `c4a2d930f`, đã deploy lên Hetzner box (metering xác minh: gold anon → 401).
- [x] **Prod chuyển tiếp từ Hetzner (Đức) → BKHOST Cloud VPS B (Việt Nam, `103.130.215.180`) — 2026-09-04.** Lý do: `nso.gov.vn` (nguồn crawler GSO CPI/GDP/IIP/Trade) reset kết nối từ mọi IP datacenter nước ngoài — đã xác minh cả GitHub Actions runner lẫn chính box Hetzner đều bị chặn; IP Việt Nam của BKHOST thì không. `mythreel.studio` (chạy chung box Hetzner trước đó) bị ngưng dịch vụ cùng đợt — dữ liệu thật của nó nằm trên Neon/R2 (external), không mất gì khi xoá box. Box Hetzner đã **xoá hẳn** sau khi xác nhận DNS + cert TLS + toàn bộ route hoạt động ổn định trên box mới. Workflow deploy đổi tên `deploy-hetzner.yml` → `deploy.yml`, secret đổi `HETZNER_*` → `DEPLOY_*` (SSH key mới, key cũ không còn dùng được vì box đã xoá). Chi tiết + trạng thái mới: `CLAUDE.md` mục "Where production actually serves from". **Lưu ý**: box-side crawl fallback cho gold/silver (systemd timer) chưa được dựng lại trên box mới — Actions vẫn là luồng chính, không ảnh hưởng vận hành hàng ngày.
- [ ] **Fuel-forecast B2B (dự báo giá xăng dầu trong nước) — Phase 1, Plan 1 (data pipeline) đang triển khai** trên branch `feat/fuel-forecast-pipeline`. Kiến trúc medallion (Bronze R2 → Silver `FUEL_FORECAST_DB`). **Plan 1 + Plan 2 LIVE** (merged PR #1 + Plan 2 on main, 2026-07-12). 36 unit test xanh (giảm từ 75 sau khi xoá structural-v1, xem dưới). **Dữ liệu (2026-09-10):** 25 kỳ BCT/fuel (đến 2026-08-27), Bronze R2 raw + sha256.
  - **structural-v1 đã xoá HOÀN TOÀN (2026-09-10)** — theo yêu cầu, vì nó thua random-walk (skill −0.19…0.00) ở mọi lần backtest. Xoá `be/fuel/formula.py`, `be/fuel/world_model.py`, và toàn bộ hàm liên quan trong `calibration.py`/`backtest.py`/`forecast.py`. **`delta-world-v1` giờ là model DUY NHẤT.**
  - **Độ cứng thống kê mới (2026-09-10)**, tính trực tiếp từ dữ liệu thật (không chỉ tin số backtest có sẵn), theo khung của Hyndman & Athanasopoulos *Forecasting: Principles and Practice* (sách mở, OTexts.com/fpp3 — `skill_vs_rw` của dự án chính là `1 − MASE`): hệ số pass-through k có ý nghĩa thống kê mạnh cả 3 loại (p<0.0001, t=6.6–23.4), R²=0.65–0.96, thắng RW theo kiểm định phi tham số Wilcoxon (p<0.01, không chỉ 1 con số skill điểm). **Điểm yếu chưa xử lý:** residual có tự tương quan âm đáng kể (lag-1 = −0.45…−0.57) và fail Shapiro-Wilk (p<0.001) — nghĩa là khoảng tin cậy Gaussian `z·resid_std` hiện dùng chưa được hiệu chỉnh đúng lý thuyết (coverage thực tế 88–94% vẫn ổn vì bảo thủ hơn mức danh nghĩa ~80%, nhưng đây là chỗ cần AR(1) hoặc bootstrap interval, chưa làm). Chi tiết đầy đủ + bảng số: `CLAUDE.md` mục "Fuel forecast model — structural-v1 removed, delta-world-v1 only".
  - **Live forecast (`forecast.py`) đổi từ "point forecast" sang "world-conditional scenario"**: không còn giả vờ biết trước giá thế giới kỳ tới (vì không có feed MOPS real-time) — output giờ là "nếu world đổi X thì retail đổi k·X" với 3 kịch bản low/base/high, base = giữ nguyên giá hiện tại. Không còn phụ thuộc Brent/RBOB.
  - **Đã khảo sát crawl MOPS trực tiếp từ S&P Global Platts (2026-09-10) — KHÔNG khả thi.** Platts/Commodity Insights không có API/trang public free; truy cập cần accreditation + hợp đồng thương mại, giá không công khai ("liên hệ sales"). Không có gì để scrape công khai — khác hẳn cách project hiện lấy MOPS gián tiếp qua bản tin MOIT (miễn phí, hợp pháp, chỉ trễ vì là ex-post).
  - **`fuel_world_daily` (Brent/RBOB, `crawl_fuel_world.py`) giờ không còn consumer nào** trong `be/fuel/` — vẫn để crawler chạy (miễn phí, không rủi ro pháp lý) làm dữ liệu tham khảo, không tự động nối lại vào model nếu không có lý do rõ ràng (chính là proxy đã thất bại). `fuel_formula_params` (bảng DB) chưa từng có code đọc/ghi — dead từ đầu, chưa xoá khỏi schema.
  - **Sự cố crawler đã fix (2026-09-08): pipeline BCT đứng im 2 tháng (09/07→27/08) trong khi CI báo xanh mỗi tuần.** MOIT chuyển bản tin "điều hành giá xăng dầu" từ category `thi-truong-trong-nuoc` sang `phat-trien-nang-luong` mà không báo; `discover_latest()` chỉ quét category cũ, cứ khớp lại đúng link 09/07 và upsert idempotent → exit 0 mỗi tuần dù không có dữ liệu mới. Đã backfill 2 kỳ thật (13/08, 27/08, xác minh bằng crawl trực tiếp) và sửa `crawl_moit_fuel.py`: quét cả 2 category + dò trực tiếp URL theo pattern cố định; ngưỡng cảnh báo cứng 25 ngày không tiến kỳ mới → fail loud thay vì im lặng thành công. Chi tiết: `CLAUDE.md` mục "Fuel (domestic) crawl — MOIT re-files bulletins without notice". Nhịp kỳ giá có vẻ đã đổi từ hàng tuần sang ~2 tuần/lần kể từ 08/2026 — chưa chắc chắn 100%, cần theo dõi thêm.
  - **Plan 3/4 — PIVOT đã triển khai (2026-09-10/11), không còn "chưa bắt đầu".** Thay vì Plan 4 gốc (corporate API service riêng, xác thực OAuth2, `.corp-prod-env`), quyết định **chốt với user trong phiên này**: bán qua đúng cơ chế subscription trả bằng ví (wallet credit) mà Agent Market đã có, không xây payment rail mới. Đây là **pivot có chủ đích, không phải bỏ sót** — Plan 4 gốc coi B2B corporate API là kênh riêng biệt; bản triển khai thật gộp Plan 3 (public data endpoint) và billing vào một, vì fuel-forecast là sản phẩm subscription đầu tiên của một primitive dùng chung (`platform_products`/`platform_subscriptions`/`platform_subscription_events`, nằm trên `KNOWLEDGE_MARKET_DB` — xem `CLAUDE.md` mục "Platform subscriptions + Fuel Forecast gated API").
    - Đã có: `GET /api/v1/fuel-forecast/{fuel}` (free tier = lịch sử + kịch bản `base`, xem `breakdown` chỉ còn disclaimer; advanced tier = đủ 3 kịch bản + breakdown đầy đủ, mở khi có subscription `active`), `/api/v1/subscriptions/plans|me|subscribe|cancel|history`, trang sản phẩm thật `fe/pages/fuel-forecast.html` (fetch thật, nút subscribe thật, thẻ "Lịch sử thanh toán").
    - **Còn thiếu 1 mảnh:** cron billing hàng ngày (`.github/workflows/subscription-billing.yml`, `python be/services/subscription.py --run-billing-cycle`) đã viết xong nhưng **CHƯA commit/merge** — chặn bởi GitHub repo secret `KNOWLEDGE_MARKET_DB` chưa tồn tại (`gh secret list` xác nhận). Cho tới khi secret được thêm và workflow merge, subscription không tự gia hạn/tự huỷ khi hết hạn — `subscribe`/`cancel` vẫn chạy được thủ công qua API/FE.
    - **Trước khi thu tiền thật:** ý kiến luật sư NĐ169 vẫn **chưa xác nhận xong** — cơ chế billing đã tồn tại không đồng nghĩa đã được phép mở cho khách hàng trả tiền thật; đây vẫn là gate bắt buộc trước khi launch thương mại, không đổi so với trước.

---

## Đã xong ✅

- [x] Admin dashboard — user/revenue/feedback metrics and signup trend
- [x] Seed 5 VD Official knowledge packs (id 20–24)
- [x] Fix download flow cho free packs
- [x] Fix list products API (description + seller_name)
- [x] Remove junk test products (id 5, 15, 16, 17, 18)
- [x] Admin access script (run_set_admin.py)
- [x] KM-02 — Copy to Claude button (library card + post-purchase modal)
- [x] KM-01 — Web reader inline (markdown → HTML modal, zero deps)
- [x] Excel Add-in — manifest.xml + task pane, mount /excel-addin/, CORS for Office domains
- [x] **2026-09-09: Meta/canonical/OG cho 6 trang docs public thiếu hoàn toàn thẻ SEO** — `docs.html`, `api-docs.html`, `about-us.html`, `terms.html`, `privacy.html`, `takedown.html` (đều có mặt trong `sitemap.xml`) không có `meta description`/`meta robots`/`canonical`/OG, trong khi các trang cùng template khác (`guide-buyer.html`, `guide-seller.html`, `knowledge-pack-spec.html`...) đã có đủ. Đã thêm đúng pattern hiện có, không đổi nội dung/layout. Không phải nguyên nhân chính khiến AI/Google không trích dẫn site (site vẫn chưa có authority/index đáng kể — xem `[[project_seo_positioning]]`), nhưng là gap thật cần vá cho đúng 2 trang quan trọng nhất (`docs.html`, `api-docs.html`).
- [x] **2026-09-09: HowTo + FAQPage schema (JSON-LD) cho content sẵn có, không viết mới** — `api-docs.html` (HowTo khớp đúng section "Cài đặt API trong 4 bước"), `guide-buyer.html` + `guide-seller.html` (FAQPage khớp đúng section FAQ đã có sẵn Q&A thật). Không trang docs nào có schema trước đó dù nhiều trang đã có sẵn nội dung dạng FAQ/HowTo tự nhiên.
- [x] **2026-09-10: Đồng bộ style `api-docs.html` với các trang docs khác** — `.section-title` của `api-docs.html` tự định nghĩa CSS riêng (1.5rem, không border-bottom, margin khít) thay vì kế thừa `.doc-content h2` chung (1.375rem, có gạch chân, margin 48px) như `guide-buyer.html`/`guide-seller.html` đang dùng — sửa để heading đồng nhất giữa mọi trang docs.
- [x] **2026-09-10: Thanh search trong docs topbar (trước đây chỉ là `<span>` trang trí, không hoạt động)** — `fe/pages/build_search_index.py` (stdlib `html.parser`, không thêm dependency) quét heading/section-id của 13 trang docs ra `docs-search-index.json` (129 mục); `docs-sidebar.js` filter live khi gõ, không phân biệt dấu tiếng Việt, Enter nhảy tới kết quả đầu, ⌘K/Ctrl+K focus vào ô search. Chạy lại script sau khi sửa heading/section id bất kỳ trang docs nào.
- [x] **2026-09-12: Chart giá vàng/bạc đứng im ở giá mở cửa cả ngày dù giá nguồn đổi nhiều lần trong ngày** — báo cáo trực tiếp: chiều 12/9 nguồn (24h.com.vn) đã cập nhật DOJI HN lên 143,0/146,0 triệu nhưng chart vẫn hiện 142,4/145,4 triệu (giá crawl lúc 08:45 sáng). **2 lớp guard chồng nhau cùng gây ra bug này, phải sửa cả hai mới hết:**
  1. `crawl_gold_silver.py` (trong script): guard "nếu hôm nay đã có row thì skip" ở cả 3 chỗ (gold + 2 nguồn silver) — chốt cứng giá lần crawl thành công đầu tiên trong ngày dù `ON CONFLICT DO UPDATE` đã có sẵn nhưng không bao giờ được chạm tới. Đã bỏ hẳn guard, luôn upsert mỗi lần crawl thành công.
  2. `gold-silver-crawl.yml` (tầng workflow, phát hiện SAU khi tưởng đã xong — đọc thiếu phần jobs lúc sửa lớp 1): step "Skip if domestic and global data are already fresh" kiểm tra `gold_rows>0 and silver_rows>0` rồi set `done=true`, khiến **toàn bộ 8 lần rerun 9h07–16h07 VN không bao giờ chạy `crawl_gold_silver.py`** một khi đã có 1 row hôm đó — vô hiệu hoá hoàn toàn fix ở lớp 1 trên production dù test local (bypass workflow, chạy script trực tiếp) tưởng đã pass. Đã bỏ hẳn step guard này + input `force_global` (không còn ý nghĩa), giờ mọi lần trigger (daily + 8 hourly) đều chạy full script — phần global (Yahoo Finance) vốn đã idempotent qua COALESCE nên chạy thêm vài lần/ngày vô hại.
  - Đã chạy crawler thủ công + trigger tay workflow `Generate Static Chart Data` để vá ngay dữ liệu hôm 12/9 thay vì chờ vòng chạy tiếp theo.
  - **Tại sao đây là bug thật, không phải chỉ "độ trễ 1 lần/ngày":** hệ thống retry hourly vốn đã tồn tại sẵn cho mục đích khác (retry khi lỗi) ở CẢ HAI tầng — sửa lỗi này khiến retry ở cả hai tầng cùng làm đúng chức năng thứ hai (refresh intraday) mà thiết kế ban đầu vô tình chặn mất.
  - **Bài học quy trình:** khi sửa 1 bug "guard chặn update", phải rà toàn bộ chuỗi gọi (script → workflow gọi nó → workflow khác phụ thuộc nó) chứ không chỉ chỗ tìm ra đầu tiên — guard trùng ý tưởng có thể tồn tại ở nhiều tầng độc lập.

---

## Cách dùng backlog này

```
Bạn: "Làm API-01"
Claude Code: đọc spec, build, test, báo cáo
Bạn: review diff, approve hoặc chỉnh hướng
```

Không cần giải thích lại context. Mỗi item đã đủ spec để bắt tay làm ngay.
