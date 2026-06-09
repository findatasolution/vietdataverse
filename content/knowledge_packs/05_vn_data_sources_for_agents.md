# Vietnam Financial Data Sources for AI Agents
**Dành cho:** Developer xây dựng agent tài chính VN, cần biết lấy dữ liệu từ đâu  
**Nội dung:** Danh sách nguồn dữ liệu, chất lượng, cách dùng trong agent

---

## 1. Viet Dataverse API — Dữ liệu đã làm sạch

Nguồn tổng hợp duy nhất ở VN có API có cấu trúc, free tier, và documentation:

```
Base URL: https://api.vietdataverse.online/api/v1/

Endpoints có sẵn:
  /gold                    Giá vàng SJC, DOJI, PNJ, BTMC — hàng ngày
  /silver                  Giá bạc Phú Quý — hàng ngày
  /sbv-rate                Tỷ giá USD/VND (VCB + SBV) — hàng ngày
  /termdepo                Lãi suất tiết kiệm ACB — hàng ngày
  /macro/cpi               CPI Việt Nam — hàng tháng
  /global?symbol=GC%3DF    Vàng quốc tế (XAU/USD)
  /global?symbol=SI%3DF    Bạc quốc tế (XAG/USD)
  /global?symbol=%5EIXIC   Nasdaq Composite
  /vn30/ohlcv              Giá cổ phiếu VN30 — hàng ngày

Authentication: Bearer token (API Key từ account settings)
Rate limit Free tier: 1.000 calls/tháng
```

---

## 2. Nguồn dữ liệu công khai — Không cần API key

### Ngân hàng Nhà nước Việt Nam (SBV)
```
URL: https://www.sbv.gov.vn/

Có gì:
  - Tỷ giá trung tâm USD/VND (cập nhật hàng ngày)
  - Lãi suất điều hành (thông báo khi có thay đổi)
  - Dự trữ ngoại hối (hàng quý, thường chậm)
  - Số liệu tín dụng (hàng tháng/quý)

Hạn chế: Không có API, chỉ có HTML/PDF. Cần scrape hoặc dùng Viet Dataverse.
```

### Tổng cục Thống kê (GSO)
```
URL: https://www.gso.gov.vn/

Có gì:
  - CPI hàng tháng (quan trọng nhất)
  - GDP hàng quý
  - Xuất nhập khẩu hàng tháng
  - Dân số, lao động, FDI

Hạn chế: File Excel/PDF, không có API. Có portal data.gso.gov.vn nhưng ít dữ liệu hơn website chính.
```

### HoSE & HNX (Sở Giao dịch Chứng khoán)
```
HoSE: https://www.hsx.vn/
HNX:  https://www.hnx.vn/

Có gì:
  - Dữ liệu giao dịch cuối ngày (end-of-day)
  - Thông tin niêm yết, báo cáo tài chính
  - Lịch sự kiện (chia cổ tức, ĐHCĐ)

Hạn chế: Không có API chuẩn. Có thể download CSV theo ngày.
```

---

## 3. Nguồn dữ liệu có API — Chủ yếu cho chứng khoán

### TCBS (Techcombank Securities)
```python
# Free, không cần đăng ký, unofficial API
import requests

# Lịch sử giá cổ phiếu
url = "https://apipubaws.tcbs.com.vn/stock-insight/v1/stock/his-price"
params = {"ticker": "VCB", "type": "stock", "resolution": "D", "from": 1700000000, "to": 1750000000}
# Trả về OHLCV theo ngày

# Thông tin tài chính doanh nghiệp
url = "https://apipubaws.tcbs.com.vn/tcanalysis/v1/finance/{ticker}/incomestatement"
```
**Lưu ý:** API không chính thức, có thể thay đổi bất kỳ lúc nào. Dùng cho prototype, không dùng cho production.

### DNSE
```python
# Free API, có documentation hơn TCBS
# https://developers.dnse.com.vn/

# Giá realtime + lịch sử
GET https://api.dnse.com.vn/market-data/v1/securities/{ticker}/ohlc
```

### SSI iBoard
```
URL: https://iboard.ssi.com.vn/
Có API không chính thức cho dữ liệu realtime
Thường dùng trong các project open-source VN
```

---

## 4. Yahoo Finance — Dữ liệu quốc tế

```python
import yfinance as yf

# Các ticker liên quan đến VN
tickers = {
    "GC=F":  "Vàng quốc tế (XAU/USD)",
    "SI=F":  "Bạc quốc tế (XAG/USD)",
    "CL=F":  "Dầu thô WTI",
    "DX-Y.NYB": "Dollar Index (DXY)",
    "^IXIC": "Nasdaq",
    "^GSPC": "S&P 500",
    "VNM":   "VanEck Vietnam ETF (proxy cho thị trường VN)",
}

df = yf.download("GC=F", period="1y", interval="1d")
```

---

## 5. Dữ liệu kinh tế vĩ mô quốc tế

### FRED (Federal Reserve Economic Data)
```
URL: https://fred.stlouisfed.org/
API: https://fred.stlouisfed.org/docs/api/fred/

Series quan trọng với VN:
  FEDFUNDS      - Lãi suất Fed Funds
  CPIAUCSL      - CPI Mỹ
  DTWEXBGS      - Dollar Index
  DEXVNUS       - Tỷ giá VND/USD (dữ liệu Fed, không realtime)
```

### World Bank API
```
URL: https://data.worldbank.org/
API: https://api.worldbank.org/v2/

Ví dụ: GDP VN
GET https://api.worldbank.org/v2/country/VN/indicator/NY.GDP.MKTP.CD?format=json
```

---

## 6. Kiến trúc Agent nên dùng

```
[User query]
     ↓
[Agent nhận diện cần dữ liệu gì]
     ↓
[Tool call → Viet Dataverse API]  ← ưu tiên: đã làm sạch, structured
     ↓
[Nếu cần thêm] → Yahoo Finance (quốc tế) hoặc TCBS (cổ phiếu chi tiết)
     ↓
[Agent tổng hợp + reasoning]
     ↓
[Output cho user]
```

**Nguyên tắc:** Không hardcode dữ liệu vào prompt — luôn dùng tool call để lấy data realtime. Dữ liệu cũ hơn 1 ngày trong phân tích tài chính = có thể gây nhầm lẫn.
