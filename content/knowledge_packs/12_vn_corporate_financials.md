# Reading Vietnamese Corporate Financial Statements
**Dành cho:** Agent phân tích cơ bản doanh nghiệp niêm yết VN, đọc BCTC, tính các chỉ số tài chính  
**Đặc thù:** BCTC VN tuân theo VAS (Vietnam Accounting Standards) — khác IFRS ở một số điểm quan trọng

---

## Cách dùng pack này

### Dành cho Developer / Agent Builder

```python
import requests

API_KEY = "your-api-key"
headers = {"X-API-Key": API_KEY}

# Giá cổ phiếu để tính P/E, P/B từ giá thị trường
vcb_price = requests.get(
    "https://api.vietdataverse.online/api/v1/vn30/ohlcv?ticker=VCB&period=7d",
    headers=headers
).json()["data"][0]["close"]

# EPS, Book Value cần lấy từ BCTC (không có API)
# Dùng TCBS unofficial API cho financial data
import requests as req
tcbs_url = "https://apipubaws.tcbs.com.vn/tcanalysis/v1/finance/VCB/incomestatement"
# Sau khi lấy EPS từ TCBS:
eps_ttm  = 5200  # ví dụ: EPS trailing 12 tháng (VND)
pe_ratio = vcb_price / eps_ttm
print(f"VCB P/E: {pe_ratio:.1f}x (giá: {vcb_price:,.0f})")
```

### Dành cho Researcher / Người không biết code

1. Nhấn **"📋 Copy to Claude"** trên thư viện Viet Dataverse
2. Mở [Claude.ai](https://claude.ai) → paste vào chat

**Câu hỏi gợi ý:**
- "VCB vừa công bố BCTC Q3 — cách đọc báo cáo thu nhập của ngân hàng VN khác gì so với doanh nghiệp thường?"
- "EBIT, EBITDA, NIM là gì — tôi cần xem chỉ số nào khi đánh giá ngân hàng vs doanh nghiệp sản xuất?"
- "VHM có tỷ lệ nợ rất cao — bao nhiêu là đáng lo ngại trong ngành BĐS VN?"

---

## 1. Cấu trúc BCTC VN — 4 báo cáo chính

```
1. Bảng cân đối kế toán (Balance Sheet)
   Tài sản = Nợ phải trả + Vốn chủ sở hữu
   Key items: Tiền mặt, Hàng tồn kho, Nợ ngắn hạn, Vốn điều lệ

2. Báo cáo kết quả kinh doanh (Income Statement)
   Doanh thu thuần → Lợi nhuận gộp → EBIT → LNTT → LNST
   Key metrics: Biên lợi nhuận gộp, EBITDA margin, ROE

3. Báo cáo lưu chuyển tiền tệ (Cash Flow Statement)
   CFO (hoạt động) + CFI (đầu tư) + CFF (tài chính)
   Key check: CFO > 0 liên tiếp = doanh nghiệp thực sự tạo tiền

4. Thuyết minh BCTC
   Chi tiết về nợ vay, tài sản cố định, giao dịch liên quan — PHẢI đọc phần này
```

---

## 2. Khác biệt VAS vs IFRS — điều agent cần biết

| Điểm khác | VAS | IFRS | Ảnh hưởng |
|-----------|-----|------|-----------|
| Ghi nhận doanh thu BĐS | Khi bàn giao | Khi kiểm soát | VHM, NVL có EPS spike bất thường |
| Đánh giá lại tài sản | Không thường xuyên | Theo thị trường | Book value VN thường understate |
| Công ty liên kết | Equity method | Equity method | Tương tự |
| Leasing | Thuê hoạt động = chi phí | IFRS 16: ghi nhận tài sản | D/E của MWG có thể thấp hơn thực |
| Nợ xấu ngân hàng | VAMC, CIC | ECL model | NPL của VN thường underreported |

---

## 3. Phân tích theo ngành — chỉ số khác nhau

### Ngân hàng (chiếm ~40% VN30)
```
Metric quan trọng nhất:
  NIM (Net Interest Margin): thu lãi - trả lãi / tổng tài sản sinh lãi
    Tốt: > 3.5%  |  Trung bình: 2.5-3.5%  |  Yếu: < 2.5%
  
  NPL (Non-Performing Loan ratio): nợ xấu / tổng dư nợ
    An toàn: < 2%  |  Chú ý: 2-3%  |  Nguy hiểm: > 3%
  
  CAR (Capital Adequacy Ratio): Basel II/III
    Tối thiểu theo quy định: 8%  |  An toàn: > 10%
  
  CASA ratio: tiền gửi không kỳ hạn / tổng huy động
    Cao → chi phí vốn thấp → lợi thế cạnh tranh
    MBB, TCB CASA cao → NIM tốt ngay cả khi lãi suất thị trường thay đổi
```

### Doanh nghiệp sản xuất (HPG, VNM, MWG)
```
Gross Margin = (Doanh thu - COGS) / Doanh thu
  Tốt cho sản xuất: > 25%  |  Bán lẻ: > 15%

EBITDA Margin = EBITDA / Revenue
  HPG thép: 15-20% khi thị trường tốt
  MWG bán lẻ: 5-8% (thấp vì margin ngành bán lẻ thấp)

Working Capital = Current Assets - Current Liabilities
  Âm = vấn đề thanh khoản ngắn hạn
```

### BĐS (VIC, VHM, NVL)
```
Key metrics đặc thù:
  NAV (Net Asset Value): giá trị đất + dự án - nợ
  Landbank (quỹ đất): số ha/căn hộ tương lai — giá trị chiến lược
  
Tỷ lệ nợ/vốn (D/E):
  BĐS VN D/E cao hơn chuẩn quốc tế:
    < 2x: an toàn  |  2-3x: bình thường ngành  |  > 3x: rủi ro cao
  
Gross Profit from BĐS: thường cao (30-50%) nhưng không ổn định theo dự án
```

---

## 4. Cờ đỏ — Red Flags trong BCTC VN

```
Cảnh báo cần xem xét thêm:

❌ Doanh thu tăng mạnh nhưng CFO âm liên tiếp
   → Doanh thu "trên giấy", chưa thu được tiền

❌ Khoản phải thu tăng nhanh hơn doanh thu
   → Khách hàng chưa trả tiền hoặc ghi nhận doanh thu sớm

❌ Hàng tồn kho tăng đột biến (BĐS/sản xuất)
   → Sản phẩm không bán được

❌ Nợ liên quan đến bên liên quan (related party) lớn
   → Rủi ro lợi ích nhóm (phổ biến ở VN)

❌ Lợi nhuận sau kiểm toán thấp hơn trước kiểm toán > 10%
   → Có vấn đề với cách ghi nhận ban đầu

❌ Kiểm toán đưa ra ý kiến ngoại trừ (qualified opinion)
   → Tín hiệu nghiêm trọng
```

---

## 5. Nguồn dữ liệu tài chính doanh nghiệp VN

```python
# Giá thị trường từ Viet Dataverse
GET https://api.vietdataverse.online/api/v1/vn30/ohlcv?ticker=VCB&period=30d

# BCTC: không có API chính thức — dùng nguồn sau
# TCBS (unofficial, khá đầy đủ):
GET https://apipubaws.tcbs.com.vn/tcanalysis/v1/finance/{ticker}/incomestatement
GET https://apipubaws.tcbs.com.vn/tcanalysis/v1/finance/{ticker}/balancesheet

# Vietstock (cần đăng ký):
# https://vietstock.vn/

# HOSE (HoSE): báo cáo chính thức từ công ty niêm yết
# https://www.hsx.vn/ → Công ty → Báo cáo tài chính
```

---

## 6. Prompt snippet cho agent phân tích BCTC

```
Khi phân tích BCTC doanh nghiệp VN:

1. Xác định ngành → chọn metric phù hợp:
   Ngân hàng → NIM, NPL, CAR, CASA
   BĐS → D/E, NAV, landbank
   Sản xuất → Gross margin, EBITDA, Working capital
   Bán lẻ → Same-store sales growth, inventory turnover

2. Luôn kiểm tra CFO (lưu chuyển tiền từ hoạt động):
   CFO dương liên tiếp = dấu hiệu tốt
   CFO âm dù lãi = cờ đỏ

3. So sánh với ngành, không phải tuyệt đối:
   D/E 2x của BĐS VN ≠ rủi ro như D/E 2x của bán lẻ

4. Đọc thuyết minh BCTC phần nợ liên quan:
   Giao dịch nội bộ lớn = rủi ro corporate governance

KHÔNG đưa ra khuyến nghị đầu tư từ BCTC một mình.
Luôn kết hợp với định giá và phân tích ngành.
```
