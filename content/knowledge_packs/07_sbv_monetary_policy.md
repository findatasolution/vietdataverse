# SBV Monetary Policy Decoder
**Dành cho:** Agent phân tích chính sách tiền tệ, dự báo xu hướng lãi suất và tác động lên thị trường tài sản  
**Cốt lõi:** NHNN không hoạt động theo lịch cố định như Fed — phải đọc tín hiệu gián tiếp

---

## Cách dùng pack này

### Dành cho Developer / Agent Builder

```python
import requests

API_KEY = "your-api-key"
headers = {"X-API-Key": API_KEY}

# Lãi suất huy động để đọc kỳ vọng thị trường
td_1y = requests.get("https://api.vietdataverse.online/api/v1/termdepo?period=6m",
                     headers=headers).json()["data"]
cpi   = requests.get("https://api.vietdataverse.online/api/v1/macro/cpi",
                     headers=headers).json()["data"]

# Phát hiện xu hướng lãi suất từ hành vi ngân hàng
rates_12m = [r["term_12m"] for r in td_1y if r.get("term_12m")]
if len(rates_12m) >= 2:
    trend = "tăng" if rates_12m[0] > rates_12m[-1] else "giảm"
    print(f"Lãi suất 12 tháng ACB đang {trend}: {rates_12m[-1]:.2f}% → {rates_12m[0]:.2f}%")
    print(f"CPI hiện tại: {cpi[0]['cpi_yoy']}%")
```

### Dành cho Researcher / Người không biết code

1. Nhấn **"📋 Copy to Claude"** trên thư viện Viet Dataverse
2. Mở [Claude.ai](https://claude.ai) → paste vào chat

**Câu hỏi gợi ý:**
- "NHNN vừa cắt lãi suất — tôi đang gửi tiết kiệm 6 tháng, còn kịp chuyển sang 24 tháng không?"
- "Khi nào thì NHNN sẽ tăng lãi suất trở lại? Tín hiệu nào tôi cần theo dõi?"
- "Lạm phát 3.5% với lãi suất SBV 4.5% — môi trường này tốt hay xấu cho cổ phiếu?"

---

## 1. Cách NHNN quyết định lãi suất

NHNN không có lịch họp cố định như FOMC của Fed. Điều chỉnh lãi suất thường diễn ra:

```
Khi nào NHNN thay đổi lãi suất:
  - Khi CPI vượt ngưỡng mục tiêu 4.5% liên tiếp 2-3 tháng (→ tăng)
  - Khi tăng trưởng GDP dưới mục tiêu và CPI thấp (→ cắt)
  - Khi Fed thay đổi mạnh → tỷ giá căng → NHNN phản ứng
  - Khi hệ thống ngân hàng cần thanh khoản khẩn cấp

Công cụ chính của NHNN:
  1. Lãi suất tái cấp vốn (refinancing rate) — benchmark
  2. Lãi suất chiết khấu (discount rate) — thường thấp hơn 1%
  3. Nghiệp vụ thị trường mở (OMO) — bơm/hút thanh khoản ngắn hạn
  4. Tỷ lệ dự trữ bắt buộc (RRR) — ít dùng hơn
```

**Chu kỳ gần nhất (2022-2024):**
```
2022: Giữ lãi suất 4% → tăng lên 6% (2 lần) do Fed tăng + tỷ giá căng
2023: Cắt 4 lần từ 6% → 4.5% (kích thích sau COVID, lạm phát hạ)
2024: Giữ 4.5% — cân bằng tăng trưởng vs áp lực tỷ giá
```

---

## 2. Đọc tín hiệu lãi suất từ thị trường

NHNN thường "signaling" trước khi hành động. Đây là các tín hiệu:

### Tín hiệu SBV chuẩn bị CẮT lãi suất
```
✅ CPI dưới 3% và đang giảm dần
✅ Tăng trưởng GDP thấp hơn mục tiêu (< 6%)
✅ Doanh nghiệp kêu khó tiếp cận tín dụng (Chính phủ yêu cầu nới)
✅ Fed đã bắt đầu cắt lãi suất trước
✅ Tỷ giá ổn định hoặc VND đang mạnh lên
✅ Lãi suất huy động ngân hàng thương mại tự giảm trước (ngân hàng "đi trước")
```

### Tín hiệu SBV chuẩn bị TĂNG lãi suất
```
⚠️ CPI vượt 4% và chưa có dấu hiệu hạ nhiệt
⚠️ VND mất giá > 2.5% YTD — NHNN cần lãi suất cao để giữ vốn
⚠️ Fed tăng mạnh và bất ngờ
⚠️ Tín dụng toàn hệ thống tăng > 15% — lo ngại bong bóng tài sản
⚠️ Ngân hàng thương mại tăng lãi suất huy động trước khi NHNN công bố
```

---

## 3. Truyền dẫn lãi suất — mất bao lâu để thấy hiệu quả?

```
NHNN điều chỉnh lãi suất
  │
  ├─► 0-1 tháng: Lãi suất OMO (ngắn hạn liên ngân hàng) thay đổi ngay
  │
  ├─► 1-3 tháng: Lãi suất huy động ngân hàng thương mại điều chỉnh
  │   (ACB, Techcombank thường đi trước các ngân hàng quốc doanh)
  │
  ├─► 3-6 tháng: Lãi suất cho vay điều chỉnh (ảnh hưởng doanh nghiệp)
  │
  └─► 6-12 tháng: Tác động thực tế lên đầu tư, tiêu dùng, GDP
```

**Thực tế VN:** Truyền dẫn chậm hơn so với nền kinh tế phát triển vì:
- Nhiều doanh nghiệp vay ngắn hạn, đảo nợ liên tục → cảm nhận lãi suất mới nhanh hơn
- Thị trường trái phiếu kém phát triển → lãi suất dài hạn ít biến động

---

## 4. Tác động lên các loại tài sản theo pha

| Pha NHNN | Cổ phiếu | Vàng | BĐS | Tiền gửi |
|----------|----------|------|-----|----------|
| Cắt lãi suất (nới lỏng) | 📈 Tích cực | 📈 Tích cực | 📈 Tích cực (lag 6-12 tháng) | 📉 Kém hấp dẫn |
| Tăng lãi suất (thắt chặt) | 📉 Tiêu cực | Trung tính | 📉 Tiêu cực | 📈 Hấp dẫn |
| Giữ nguyên | Theo yếu tố khác | Theo USD | Theo tín dụng | Ổn định |

---

## 5. Prompt snippet cho agent chính sách tiền tệ

```
Khi phân tích chính sách tiền tệ NHNN:

Bước 1 — Xác định pha hiện tại:
  Cắt / Giữ / Tăng? So sánh với 12 tháng trước.

Bước 2 — Đọc tín hiệu thị trường:
  Lãi suất huy động ACB 12m đang tăng hay giảm so với 3 tháng trước?
  → Ngân hàng thương mại thường đi trước NHNN 1-2 tháng

Bước 3 — Kiểm tra 3 biến số:
  CPI YoY vs 4.5% target
  Tỷ giá USD/VND YTD change vs 2% threshold
  GDP growth vs 6% target

Bước 4 — Kết luận:
  Nếu cả 3 thuận chiều → NHNN có dư địa giữ hoặc cắt tiếp
  Nếu tỷ giá + CPI đều căng → NHNN bị kẹt (không thể cắt dù muốn)
```

---

## 6. Nguồn dữ liệu API

```python
# Lãi suất tiết kiệm — proxy truyền dẫn chính sách
GET https://api.vietdataverse.online/api/v1/termdepo?period=1y

# CPI — biến số chính của NHNN
GET https://api.vietdataverse.online/api/v1/macro/cpi

# Tỷ giá — ràng buộc thứ hai của NHNN
GET https://api.vietdataverse.online/api/v1/sbv-rate?period=1y
```
