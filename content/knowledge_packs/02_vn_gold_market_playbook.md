# Vietnam Gold Market Playbook
**Dành cho:** Agent phân tích giá vàng, tư vấn mua bán vàng tại Việt Nam  
**Đặc điểm nổi bật:** Thị trường vàng VN hoạt động khác hoàn toàn so với quốc tế

---

## Cách dùng pack này

### Dành cho Developer / Agent Builder

Dán pack này vào system prompt để agent tự tính **premium SJC** và phân tích giá vàng VN so với quốc tế.

```python
import requests

API_KEY = "your-api-key"  # Lấy tại vietdataverse.online/account
headers = {"X-API-Key": API_KEY}

# Giá vàng SJC trong nước (VND/lượng)
sjc   = requests.get("https://api.vietdataverse.online/api/v1/gold?type=SJC HN",
                     headers=headers).json()["data"][0]
# Tỷ giá USD/VND
fx    = requests.get("https://api.vietdataverse.online/api/v1/sbv-rate",
                     headers=headers).json()["data"][0]
# Giá vàng quốc tế (USD/oz)
xauusd = requests.get("https://api.vietdataverse.online/api/v1/global?symbol=GC%3DF",
                      headers=headers).json()["data"][0]

# Tính premium
usd_per_oz  = xauusd["close"]
vcb_sell    = fx["vcb_sell"]
gia_qt_vnd  = usd_per_oz * vcb_sell / 26.45  # VND/lượng
premium     = sjc["sell_price"] - gia_qt_vnd

print(f"SJC bán: {sjc['sell_price']:,.0f} VND/lượng")
print(f"Giá quốc tế quy đổi: {gia_qt_vnd:,.0f} VND/lượng")
print(f"Premium SJC: {premium/1_000_000:.1f} triệu VND/lượng")
```

### Dành cho Researcher / Người không biết code

1. Nhấn **"📋 Copy to Claude"** trên trang thư viện Viet Dataverse
2. Mở [Claude.ai](https://claude.ai) → paste vào cửa sổ chat
3. Hỏi về thị trường vàng VN — Claude đã biết đặc thù premium SJC, mùa vụ, và cách đọc tín hiệu

**Câu hỏi gợi ý:**
- "Premium SJC là gì? Khi nào thì premium cao là bất thường?"
- "Tôi muốn mua vàng để giữ giá trị, nên mua SJC hay DOJI hay nhẫn PNJ?"
- "Vía Thần Tài năm nay tôi có nên mua vàng không?"
- "Giá vàng quốc tế tăng thì vàng SJC có tăng tương tự không?"

---

## 1. Tại sao vàng VN khác vàng quốc tế?

### Thương hiệu & chênh lệch giá (Premium)
Việt Nam có thị trường vàng miếng **bị kiểm soát bởi Nhà nước** từ năm 2012 (Nghị định 24).
Chỉ SJC được phép sản xuất vàng miếng → độc quyền → giá SJC thường cao hơn giá quốc tế quy đổi từ **3-10 triệu đồng/lượng**.

| Thương hiệu | Loại | Đặc điểm |
|-------------|------|----------|
| **SJC** | Vàng miếng nhà nước | Thanh khoản cao nhất, chênh lệch cao nhất với quốc tế |
| **DOJI** | Vàng miếng + trang sức | Giá sát quốc tế hơn SJC |
| **PNJ** | Trang sức + nhẫn | Phổ biến ở phân khúc bán lẻ |
| **BTMC (Bảo Tín Minh Châu)** | Vàng miếng + nhẫn | Phổ biến ở miền Bắc |

### Spread mua-bán
Spread bình thường của SJC: **400.000 – 600.000 VND/lượng**  
Khi thị trường biến động mạnh: spread có thể lên **1-2 triệu VND/lượng**  
→ Agent cần tính spread vào cost khi khuyến nghị mua/bán

---

## 2. Công thức quy đổi giá quốc tế → VN

```
Giá vàng quốc tế (USD/oz) × Tỷ giá USD/VND ÷ 26.45 (lượng/oz) = Giá ngang bằng quốc tế (VND/lượng)

Ví dụ: $2,300/oz × 25,000 VND ÷ 26.45 = ~2,175,000 VND/chỉ = ~21,750,000 VND/lượng
Nếu SJC đang bán 85 triệu/lượng → premium = 85tr - 21.75tr = 63.25tr (rất cao, bất thường)
Nếu SJC đang bán 78 triệu/lượng → premium = 78tr - 21.75tr = 56.25tr (bình thường giai đoạn 2023-2024)
```

**Ngưỡng premium SJC:**
- < 3 triệu/lượng: thấp bất thường (thường sau khi NHNN bán vàng can thiệp)
- 3–8 triệu/lượng: vùng bình thường lịch sử (2015-2022)
- 8–15 triệu/lượng: cao, thị trường đang căng thẳng
- > 15 triệu/lượng: cực đoan, thường kèm biến động tỷ giá mạnh

---

## 3. Các yếu tố tác động giá vàng VN

### Từ quốc tế (truyền dẫn qua tỷ giá + giá USD/oz)
- Fed tăng lãi suất → USD mạnh → vàng quốc tế USD giảm, nhưng VND/oz có thể không giảm nếu VND cũng mất giá
- Căng thẳng địa chính trị (chiến tranh, khủng hoảng tài chính) → vàng tăng toàn cầu
- Dữ liệu lạm phát Mỹ (CPI, PCE) → ảnh hưởng kỳ vọng Fed → ảnh hưởng vàng

### Từ trong nước
- Tỷ giá USD/VND tăng (VND mất giá) → vàng VN quy đổi tăng
- NHNN bán vàng SJC can thiệp → giá SJC giảm, thu hẹp premium
- Tâm lý tích trữ dịp Tết Nguyên Đán (tháng 1-2) và ngày Vía Thần Tài → cầu tăng đột biến
- Ngày Thần Tài (mùng 10 tháng Giêng âm lịch): nhu cầu mua vàng nhẫn tăng gấp 3-5 lần ngày thường

---

## 4. Tính mùa vụ giá vàng VN

```
Tháng 1-2 (trước Tết): nhu cầu cao, giá thường nhỉnh
Tháng 2 (Vía Thần Tài): spike ngắn hạn vàng nhẫn
Tháng 3-6: giao dịch bình thường
Tháng 7-8: thường thấp (hè, ít giao dịch)
Tháng 9-10: tăng nhẹ (chuẩn bị cuối năm)
Tháng 11-12: tích lũy trước Tết
```

---

## 5. Prompt snippet cho agent vàng

```
Khi phân tích giá vàng Việt Nam:

Bước 1 — Xác định premium hiện tại:
  premium = giá SJC bán - (giá XAU/USD × tỷ giá USD/VND ÷ 26.45)

Bước 2 — Đánh giá mức premium:
  < 3 triệu: NHNN vừa can thiệp hoặc thị trường yếu
  3-8 triệu: bình thường
  > 8 triệu: cầu nội địa tăng mạnh hoặc tỷ giá căng

Bước 3 — Kiểm tra yếu tố thời vụ (có phải gần Tết/Thần Tài không?)

Bước 4 — Xem xu hướng XAU/USD (giá quốc tế) để biết động lực dài hạn

KHÔNG khuyến nghị mua/bán — chỉ phân tích bối cảnh và premium.
```

---

## 6. Nguồn dữ liệu thực tế

```python
# Giá vàng theo thương hiệu, cập nhật hàng ngày
GET https://api.vietdataverse.online/api/v1/gold?type=SJC
GET https://api.vietdataverse.online/api/v1/gold?type=DOJI
GET https://api.vietdataverse.online/api/v1/gold?type=PNJ
GET https://api.vietdataverse.online/api/v1/gold?type=BTMC

# Tỷ giá USD/VND để tính premium
GET https://api.vietdataverse.online/api/v1/sbv-rate

# Giá vàng quốc tế (XAU/USD)
GET https://api.vietdataverse.online/api/v1/global?symbol=GC%3DF
```
