# Commodity Markets & Vietnam Economy
**Dành cho:** Agent phân tích tác động hàng hóa quốc tế lên kinh tế và thị trường VN  
**Đặc biệt:** VN vừa là nước nhập khẩu (dầu, thép phế, ngô) vừa là nước xuất khẩu (gạo, cà phê, cao su, tôm)

---

## Cách dùng pack này

### Dành cho Developer / Agent Builder

```python
import requests

API_KEY = "your-api-key"
headers = {"X-API-Key": API_KEY}

# Vàng quốc tế (XAU/USD) — barometer rủi ro toàn cầu
gold  = requests.get("https://api.vietdataverse.online/api/v1/global?symbol=GC%3DF&period=3m",
                     headers=headers).json()["data"]
# Bạc (XAG/USD) — ít hơn vàng nhưng hữu ích cho so sánh
silver = requests.get("https://api.vietdataverse.online/api/v1/global?symbol=SI%3DF&period=3m",
                      headers=headers).json()["data"]

gold_return = (gold[0]["close"] - gold[-1]["close"]) / gold[-1]["close"] * 100
print(f"Vàng 3 tháng: {gold_return:+.1f}% — {'risk-off (lo ngại)' if gold_return > 5 else 'bình thường'}")
```

### Dành cho Researcher / Người không biết code

1. Nhấn **"📋 Copy to Claude"** trên thư viện Viet Dataverse
2. Mở [Claude.ai](https://claude.ai) → paste vào chat

**Câu hỏi gợi ý:**
- "Giá dầu Brent vừa tăng $10/thùng — ảnh hưởng đến lạm phát VN và cổ phiếu GAS thế nào?"
- "VN xuất khẩu gạo nhiều — khi giá gạo thế giới tăng thì kinh tế VN hưởng lợi hay thiệt?"
- "Giá thép thế giới giảm — HPG (Hòa Phát) được hay mất?"

---

## 1. Hàng hóa VN nhập khẩu — rủi ro chi phí

### Dầu mỏ & Xăng dầu (~60% nhu cầu từ nhập khẩu)
```
Tác động khi giá dầu tăng $10/thùng:
  CPI VN tăng thêm ~0.3-0.4% (qua xăng dầu và vận tải)
  PLX: biên lợi nhuận lọc dầu ngắn hạn có thể cải thiện
  HVN (Vietnam Airlines): chi phí nhiên liệu ~25-30% tổng chi phí → EPS giảm mạnh
  HPG (thép): chi phí năng lượng tăng, margin bị ép

Proxy theo dõi: WTI (CL=F) hoặc Brent trên Yahoo Finance
Tác động VN: lag ~1-2 tháng qua chu kỳ điều chỉnh giá xăng
```

### Thép phế liệu (HPG nhập ~60% nguyên liệu từ Mỹ, Nhật)
```
Spread thép thành phẩm - thép phế tăng → HPG margin tốt
Spread thu hẹp → HPG điều chỉnh

Giá thép thanh xây dựng VN thường lag thép quốc tế 1-2 tháng
Nhu cầu nội địa: phục hồi BĐS + đầu tư công → yếu tố VN-specific
```

### Ngô, đậu nành (nhập khẩu cho thức ăn chăn nuôi)
```
Nguồn: Mỹ, Brazil
Ảnh hưởng: giá heo, gà tăng → CPI lương thực tăng
Giá ngô/đậu tương quốc tế tăng → 2-4 tháng sau → giá thịt VN tăng
```

---

## 2. Hàng hóa VN xuất khẩu — nguồn thu ngoại tệ

### Gạo (~6-7 triệu tấn/năm, đứng top 3 xuất khẩu thế giới)
```
Giá gạo thế giới tăng → xuất khẩu VN được giá → USD thu về nhiều → VND ổn định
Rủi ro: Ấn Độ cấm xuất khẩu gạo (2023) → VN hưởng lợi ngắn hạn, nhưng cạnh tranh dài hạn tăng
Tháng xuất khẩu cao điểm: Q2-Q3 (vụ Hè Thu)

Cổ phiếu liên quan: PAN Group (không trong VN30 nhưng ảnh hưởng lớn)
```

### Cà phê (~1.5 triệu tấn/năm, đứng 2 thế giới — chủ yếu Robusta)
```
Giá Robusta London (LCC) tăng → các tỉnh Tây Nguyên hưởng lợi
VN chiếm ~40% Robusta thế giới → biến động giá cà phê VN ảnh hưởng giá toàn cầu
Mùa thu hoạch: tháng 11-2 → áp lực tăng cung vào Q4/Q1

Rủi ro: El Niño → hạn hán Tây Nguyên → sản lượng giảm → giá tăng ngắn hạn
```

### Cao su (~1 triệu tấn/năm)
```
Giá cao su Singapore (RSS3) tăng → miền Đông Nam Bộ, Tây Nguyên hưởng lợi
Nhu cầu toàn cầu gắn với sản xuất ô tô (Trung Quốc chiếm ~40% cầu)
Khi Trung Quốc tăng trưởng chậm → cao su VN xuất khẩu khó
```

### Tôm (~3.5 tỷ USD xuất khẩu/năm)
```
Thị trường chính: Mỹ, Nhật, EU
Cạnh tranh: Ecuador, Ấn Độ đang mở rộng nuôi tôm → áp lực giá
Rủi ro: Mỹ điều tra chống bán phá giá → thuế tăng → xuất khẩu giảm
```

---

## 3. Ma trận tác động hàng hóa × VN30

| Hàng hóa | Tăng giá | Cổ phiếu hưởng lợi | Cổ phiếu bị ảnh hưởng |
|----------|----------|---------------------|----------------------|
| Dầu tăng | GAS (+), PLX (±) | GAS | HVN, HPG |
| Thép tăng | Spread HPG tùy | HSG, HPG (tùy spread) | BĐS, xây dựng |
| Vàng tăng mạnh | Risk-off signal | — | Toàn thị trường thường điều chỉnh |
| Gạo tăng | CPI có thể tăng nhẹ | — | NHNN thận trọng hơn |

---

## 4. Prompt snippet cho agent hàng hóa

```
Khi phân tích tác động hàng hóa quốc tế lên VN:

1. Phân loại: VN nhập hay xuất hàng hóa đó?
   - Nhập: tác động qua chi phí sản xuất, CPI → thường tiêu cực
   - Xuất: tác động qua doanh thu xuất khẩu → thường tích cực

2. Mức độ tác động: chiếm % nào trong GDP/CPI?
   - Dầu: ảnh hưởng CPI cao nhất (~0.35% per $10/bbl)
   - Gạo: ít tác động CPI nội địa, chủ yếu qua xuất khẩu

3. Cổ phiếu VN30 bị ảnh hưởng trực tiếp:
   - Xác định công ty có exposure lớn nhất với hàng hóa đó

4. Thời gian truyền dẫn: 1-4 tháng tùy hàng hóa
```

---

## 5. Nguồn dữ liệu API

```python
# Vàng quốc tế (barometer risk-off)
GET https://api.vietdataverse.online/api/v1/global?symbol=GC%3DF&period=6m

# Bạc (thường cùng chiều vàng nhưng biến động mạnh hơn)
GET https://api.vietdataverse.online/api/v1/global?symbol=SI%3DF&period=6m

# Nasdaq (proxy risk appetite toàn cầu)
GET https://api.vietdataverse.online/api/v1/global?symbol=%5EIXIC&period=6m

# Giá vàng trong nước (ảnh hưởng tâm lý nhà đầu tư VN)
GET https://api.vietdataverse.online/api/v1/gold?type=SJC%20HN&period=6m

# Cổ phiếu GAS, HPG, HVN trong VN30
GET https://api.vietdataverse.online/api/v1/vn30/ohlcv?ticker=GAS&period=6m
```
