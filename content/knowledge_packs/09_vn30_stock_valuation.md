# VN30 Stock Valuation Guide
**Dành cho:** Agent phân tích định giá cổ phiếu VN, hỗ trợ quyết định mua/bán/nắm giữ  
**Phạm vi:** 30 cổ phiếu vốn hóa lớn nhất HSX — chiếm ~80% thanh khoản toàn thị trường

---

## Cách dùng pack này

### Dành cho Developer / Agent Builder

```python
import requests

API_KEY = "your-api-key"
headers = {"X-API-Key": API_KEY}

# Dữ liệu OHLCV + ratios
ohlcv  = requests.get("https://api.vietdataverse.online/api/v1/vn30/ohlcv?ticker=VCB&period=1y",
                      headers=headers).json()["data"]
# Tính return 52 tuần
price_now  = ohlcv[0]["close"]
price_52w  = ohlcv[-1]["close"]
return_1y  = (price_now - price_52w) / price_52w * 100
print(f"VCB 52W return: {return_1y:.1f}%")

# So sánh với VN-Index (dùng E1VFVN30 proxy)
idx = requests.get("https://api.vietdataverse.online/api/v1/vn30/ohlcv?ticker=E1VFVN30&period=1y",
                   headers=headers).json()["data"]
```

### Dành cho Researcher / Người không biết code

1. Nhấn **"📋 Copy to Claude"** trên thư viện Viet Dataverse
2. Mở [Claude.ai](https://claude.ai) → paste vào chat

**Câu hỏi gợi ý:**
- "P/E của VN-Index đang ở đâu? Có đắt so với lịch sử không?"
- "VCB vs TCB — tôi nên mua bank nào ở thời điểm này?"
- "Làm thế nào để biết một cổ phiếu trong VN30 đang rẻ hay đắt?"

---

## 1. Khung định giá cho cổ phiếu VN30

### P/E (Price-to-Earnings)

```
VN-Index lịch sử P/E:
  Vùng rẻ lịch sử:  < 10x (đáy khủng hoảng COVID 2020, GFC 2008)
  Vùng hợp lý:       10-15x (phần lớn thời gian)
  Vùng định giá đầy: 15-18x (thị trường bình thường)
  Vùng đắt:         > 18x (gần đỉnh chu kỳ)

So sánh với khu vực (2024):
  VN30 P/E: ~12-14x (discount so với Thái Lan 18x, Philippines 16x)
  Nguyên nhân discount: thanh khoản thấp, FII ownership limit, corporate governance
```

### P/B (Price-to-Book) — quan trọng hơn cho ngân hàng VN

```
Nhóm ngân hàng VN30 P/B lịch sử:
  Vùng rẻ:    P/B < 1.0x (cổ phiếu giao dịch dưới giá trị sổ sách)
  Vùng hợp lý: P/B 1.0-1.8x
  Vùng đắt:   P/B > 2.0x

VCB P/B ~3.0x → premium vì: NPL thấp nhất ngành, ROE cao (~20%)
TCB P/B ~1.5x → hợp lý nhưng phụ thuộc mảng trái phiếu doanh nghiệp
ACB P/B ~2.0x → chất lượng tài sản tốt, bán lẻ mạnh
```

### ROE (Return on Equity) — phân biệt chất lượng

```
VN30 ROE benchmark:
  Xuất sắc:  ROE > 20% (VCB, MWG lúc đỉnh)
  Tốt:       ROE 15-20%
  Trung bình: ROE 10-15%
  Yếu:       ROE < 10% (thường bị discount P/B)
```

---

## 2. Định giá theo ngành — tùy nhóm dùng metric khác

| Nhóm ngành | Metric chính | Metric phụ | Lưu ý đặc thù VN |
|------------|-------------|------------|-----------------|
| Ngân hàng | P/B, ROE, NIM | NPL ratio, CAR | Phải xem NIM xu hướng |
| BĐS | NAV discount/premium | Landbank size | Khó định giá vì thiếu data |
| Hàng tiêu dùng | P/E, Revenue growth | Margin trend | VNM, MWG — xem market share |
| Năng lượng | EV/EBITDA | P/E | GAS: link trực tiếp giá LNG |
| Hàng không | EV/EBITDA, P/Sales | Load factor | HVN phụ thuộc giá dầu |
| Thép | EV/ton capacity | Inventory days | HPG: spread thép-quặng |

---

## 3. Phân tích tương đối — so sánh trong ngành

```python
# Framework so sánh ngân hàng VN30
banks = {
    "VCB": {"roe": 20.0, "pb": 3.0, "nim": 3.2, "npl": 0.9},
    "BID": {"roe": 18.0, "pb": 2.1, "nim": 2.9, "npl": 1.2},
    "CTG": {"roe": 16.0, "pb": 1.6, "nim": 2.7, "npl": 1.5},
    "MBB": {"roe": 22.0, "pb": 1.8, "nim": 5.1, "npl": 1.8},
    "TCB": {"roe": 18.5, "pb": 1.5, "nim": 4.2, "npl": 1.1},
}
# VCB: premium P/B justified bởi ROE cao nhất + NPL thấp nhất
# MBB: ROE cao nhất, NIM cao nhất, nhưng NPL đang tăng
# TCB: định giá hấp dẫn nếu mảng trái phiếu doanh nghiệp phục hồi
```

---

## 4. Các bẫy định giá phổ biến ở VN

```
Bẫy 1 — P/E thấp vì earnings đỉnh:
  Doanh nghiệp BĐS thường có EPS đỉnh 1-2 năm → P/E thấp bề ngoài
  → Luôn xem EPS trend, không chỉ trailing P/E

Bẫy 2 — P/B thấp vì tài sản chất lượng kém:
  Ngân hàng nhỏ P/B 0.6x → rẻ? Không — NPL ẩn có thể ăn hết book value
  → Kiểm tra NPL, LLCR trước khi tin vào P/B thấp

Bẫy 3 — ROE ảo từ đòn bẩy cao:
  BĐS dùng đòn bẩy D/E > 3x → ROE 20% nhưng rủi ro phá sản cao
  → Ưu tiên ROE của doanh nghiệp có D/E < 1x

Bẫy 4 — So sánh P/E với ngành khác nhau:
  P/E 20x cho ngân hàng ≠ P/E 20x cho công nghệ
  → Luôn so sánh trong cùng nhóm ngành
```

---

## 5. Prompt snippet cho agent định giá

```
Khi phân tích định giá cổ phiếu VN30:

Bước 1 — Xác định nhóm ngành (ngân hàng/BĐS/tiêu dùng/năng lượng)
Bước 2 — Chọn metric phù hợp (P/E, P/B, EV/EBITDA)
Bước 3 — So sánh với:
  a) Lịch sử 5 năm của chính cổ phiếu đó
  b) Trung bình ngành VN30 cùng nhóm
  c) Giai đoạn tương tự trong chu kỳ kinh tế
Bước 4 — Xem ROE trend (tăng/giảm/ổn định)
Bước 5 — Kết luận: Rẻ / Hợp lý / Đắt so với lịch sử

KHÔNG đưa ra khuyến nghị mua/bán tuyệt đối.
KHÔNG dự báo giá mục tiêu.
Luôn đính kèm: "Phân tích chỉ mang tính tham khảo."
```

---

## 6. Nguồn dữ liệu API

```python
# OHLCV + volume cho bất kỳ ticker VN30
GET https://api.vietdataverse.online/api/v1/vn30/ohlcv?ticker=VCB&period=2y
GET https://api.vietdataverse.online/api/v1/vn30/ohlcv?ticker=TCB&period=2y

# Lãi suất — ảnh hưởng cost of capital và định giá chung
GET https://api.vietdataverse.online/api/v1/termdepo?period=1y

# List tất cả ticker VN30 có thể query
GET https://api.vietdataverse.online/api/v1/vn30/tickers
```
