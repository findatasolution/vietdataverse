# Vietnam Agricultural Commodities
**Dành cho:** Agent phân tích hàng hóa nông nghiệp VN, tư vấn cho doanh nghiệp xuất nhập khẩu nông sản  
**Tầm quan trọng:** VN là top 3 xuất khẩu gạo, top 2 cà phê, top 3 hạt tiêu — nông nghiệp chiếm ~12-14% GDP

---

## Cách dùng pack này

### Dành cho Developer / Agent Builder

```python
import requests, yfinance as yf

API_KEY = "your-api-key"
headers = {"X-API-Key": API_KEY}

# Proxy giá cà phê Robusta (London) qua Yahoo Finance
coffee_robusta = yf.download("RC=F", period="6mo", interval="1d")
latest_price = float(coffee_robusta["Close"].iloc[-1])
print(f"Cà phê Robusta London: ${latest_price:.0f}/tấn")

# Proxy vàng (barometer rủi ro, ảnh hưởng gián tiếp qua USD/VND)
gold_intl = requests.get(
    "https://api.vietdataverse.online/api/v1/global?symbol=GC%3DF&period=1m",
    headers=headers
).json()["data"][0]["close"]

# Giá nông sản VN thực tế: không có API — cần crawl từ Agroviet, MARD
```

### Dành cho Researcher / Người không biết code

1. Nhấn **"📋 Copy to Claude"** trên thư viện Viet Dataverse
2. Mở [Claude.ai](https://claude.ai) → paste vào chat

**Câu hỏi gợi ý:**
- "Giá cà phê Robusta London đang ở mức cao nhất 30 năm — người trồng cà phê Tây Nguyên được lợi gì?"
- "VN xuất khẩu gạo nhiều nhưng người dân VN có bị ảnh hưởng bởi giá gạo thế giới không?"
- "El Niño năm nay ảnh hưởng thế nào đến sản lượng cà phê và cao su VN?"

---

## 1. Cà phê — VN là cường quốc Robusta

```
Vị thế VN trên thế giới:
  Tổng sản lượng: ~1.5-1.8 triệu tấn/năm
  Thị phần Robusta: ~40% thế giới (so sánh: Brazil ~30%)
  Xuất khẩu: ~3.5-4 tỷ USD/năm

Vùng trồng chính:
  Đắk Lắk (thủ phủ cà phê VN): ~500.000 ha
  Lâm Đồng (Đà Lạt): Arabica quality, giá cao hơn
  Gia Lai, Đắk Nông, Kon Tum: Robusta

Mùa vụ và giá:
  Thu hoạch: tháng 11-2 (niên vụ Oct-Sep)
  Giá tăng: khi tồn kho thế giới thấp + El Niño hạn hán
  Giá giảm: khi Brazil và VN mùa bội thu cùng lúc

Theo dõi: Robusta London (RC=F, đơn vị USD/tấn)
  Ngưỡng sinh lời nông dân: ~2.000 USD/tấn
  Đỉnh 2024: ~4.000 USD/tấn (mức kỷ lục 30 năm)
```

---

## 2. Gạo — VN top 3 xuất khẩu thế giới

```
Sản lượng: ~43-44 triệu tấn lúa/năm (~28 triệu tấn gạo)
Tiêu thụ nội địa: ~18-19 triệu tấn
Xuất khẩu: ~7-8 triệu tấn (~4-5 tỷ USD)

Vùng sản xuất:
  Đồng bằng sông Cửu Long (ĐBSCL): ~60% sản lượng cả nước
  Đồng bằng sông Hồng: chủ yếu tiêu thụ nội địa

Thị trường XK chính:
  Philippines: 30% (phụ thuộc chặt vào VN)
  Trung Quốc: 20-25% (biến động tùy quan hệ chính trị)
  Indonesia, Malaysia, Châu Phi: phần còn lại

Loại gạo và giá:
  Gạo jasmine (thơm): 600-700 USD/tấn (cao cấp)
  Gạo IR 5451 (thường): 400-450 USD/tấn
  Gạo ST25 (ngon nhất thế giới): giá cao nhất, thị trường ngách

Ảnh hưởng CPI VN:
  Giá gạo nội địa ổn định hơn thế giới do Chính phủ kiểm soát
  Khi xuất khẩu tăng mạnh → giá nội địa có thể tăng nhẹ
  NHNN thường can thiệp nếu giá gạo tăng ảnh hưởng CPI
```

---

## 3. Cao su — VN top 5 thế giới

```
Sản lượng: ~1 triệu tấn/năm
Vùng sản xuất: Bình Phước, Bình Dương, Đồng Nai, Tây Nguyên
Xuất khẩu: ~1.5-2 tỷ USD/năm

Theo dõi: Rubber Singapore (RSS3, SGX)
Cầu chính: Trung Quốc (~40% cầu cao su tự nhiên toàn cầu)
  → Khi TQ tăng trưởng chậm → giá cao su giảm

Ứng dụng: lốp xe (~70%), sản phẩm công nghiệp (30%)
  → Ngành ô tô toàn cầu ảnh hưởng trực tiếp
```

---

## 4. Hạt tiêu & Điều — VN thống trị thị trường ngách

```
Hạt tiêu:
  Sản lượng: ~280-300 nghìn tấn/năm
  Thị phần: ~30-35% thế giới (top 1)
  Vùng: Bình Phước, Đắk Nông, Đồng Nai
  
Điều (cashew nhân):
  Sản lượng chế biến: ~700-750 nghìn tấn nhân
  Thị phần: ~70-75% cashew nhân toàn cầu (số 1 tuyệt đối)
  VN nhập nguyên liệu từ Châu Phi, chế biến và tái xuất
```

---

## 5. Rủi ro khí hậu — El Niño & La Niña

```
El Niño (khô hạn Đông Nam Á):
  Ảnh hưởng VN: hạn hán ĐBSCL → lúa, cà phê, cao su giảm sản lượng
  Tần suất: 3-5 năm/lần
  Tín hiệu: tháng 3-4, ENSO index dương mạnh → chuẩn bị cho vụ mùa thấp
  
La Niña (mưa nhiều):
  Ảnh hưởng VN: lũ lụt ĐBSCL → lúa thiệt hại
  Nhưng cà phê, cao su Tây Nguyên thường được mùa

Theo dõi: NOAA ENSO forecast (https://www.cpc.ncep.noaa.gov/)
```

---

## 6. Prompt snippet cho agent nông nghiệp

```
Khi phân tích nông sản VN:

1. Xác định mùa vụ hiện tại:
   Cà phê: đang thu hoạch (Nov-Feb) hay đang trồng?
   Lúa: vụ Đông Xuân (Jan-Mar) / Hè Thu (Apr-Jul) / Thu Đông (Sep-Nov)

2. Kiểm tra điều kiện thời tiết:
   El Niño hay La Niña? → ảnh hưởng sản lượng

3. Giá quốc tế so ngưỡng sinh lời nông dân:
   Cà phê: < 2000 USD/tấn → nông dân lỗ
   Gạo:   < 400 USD/tấn → ít khuyến khích trồng thêm

4. Chính sách xuất khẩu: VN có đang hạn chế xuất khẩu không?
   (2023: Ấn Độ cấm xuất khẩu gạo → VN hưởng lợi)

Luôn phân biệt: giá quốc tế ≠ giá nông dân nhận
(Có sự khác biệt lớn qua thương lái và chi phí logistics)
```

---

## 7. Nguồn dữ liệu

```python
# Giá vàng/bạc quốc tế (proxy rủi ro toàn cầu)
GET https://api.vietdataverse.online/api/v1/global?symbol=GC%3DF&period=6m

# Giá nông sản VN (không có API — nguồn tham khảo):
# Agroviet: https://www.agroviet.gov.vn/
# MARD: https://www.mard.gov.vn/
# Cục Xuất nhập khẩu: https://vitic.gov.vn/

# Giá quốc tế qua Yahoo Finance (cần yfinance):
import yfinance as yf
# KC=F  — Cà phê Arabica (ICE)
# RC=F  — Cà phê Robusta (Euronext)
# RR=F  — Gạo thô (CBOT)
# RUB=F — Cao su (không ổn định)
```
