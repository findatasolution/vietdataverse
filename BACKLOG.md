# Viet Dataverse — Product Backlog

> Workflow: mỗi session chọn 1 item, nói "Làm [ID]" → Claude Code build, bạn review + approve.  
> Priority: 🔴 HIGH · 🟡 MEDIUM · ⚪ LOW/DEFER

---

## 🔴 HIGH — Làm ngay (core revenue + stability)

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

### [API-04] Webhook / scheduled data push
- User đăng ký nhận data mới qua webhook URL của họ
- Mỗi sáng sau khi crawler chạy → push data mới tới endpoint
- **Tại sao:** Fintech startup cần data pipeline tự động, không muốn poll

### [CHAT-01] MVP "Chat với dữ liệu VN" — prototype
- Interface chat đơn giản, pre-loaded với context VN
- Mỗi câu hỏi → tự gọi API lấy data realtime → trả lời
- Target: finance student / researcher không biết code
- **Tại sao:** TAM lớn nhất, nhưng phức tạp hơn — làm sau khi API stable

### [KM-03] Upgrade 8 pack cũ (id 6–13) — rewrite theo framework mới
- Chuyển từ "giải thích kiến thức" → "giải quyết task cụ thể"
- Thêm TA rõ ràng, prompt snippet sẵn dùng, ví dụ thực
- Làm từng pack một, 1 pack/tuần
- **Tại sao:** Hiện tại chất lượng chưa đủ để justify có-credit packs

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

## Đã xong ✅

- [x] Admin dashboard — user metrics, signup trend chart
- [x] Seed 5 VD Official knowledge packs (id 20–24)
- [x] Fix download flow cho free packs
- [x] Fix list products API (description + seller_name)
- [x] Remove junk test products (id 5, 15, 16, 17, 18)
- [x] Admin access script (run_set_admin.py)
- [x] KM-02 — Copy to Claude button (library card + post-purchase modal)
- [x] KM-01 — Web reader inline (markdown → HTML modal, zero deps)
- [x] Excel Add-in — manifest.xml + task pane, mount /excel-addin/, CORS for Office domains

---

## Cách dùng backlog này

```
Bạn: "Làm API-01"
Claude Code: đọc spec, build, test, báo cáo
Bạn: review diff, approve hoặc chỉnh hướng
```

Không cần giải thích lại context. Mỗi item đã đủ spec để bắt tay làm ngay.
