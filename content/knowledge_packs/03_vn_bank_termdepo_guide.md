# Vietnam Bank Term Deposit Rate Guide
**Dành cho:** Agent tư vấn tài chính cá nhân, so sánh lãi suất tiết kiệm ngân hàng  
**Cập nhật:** Dữ liệu lịch sử từ 2020, API realtime từ Viet Dataverse

---

## Cách dùng pack này

### Dành cho Developer / Agent Builder

Dán pack này vào system prompt để agent tư vấn tiết kiệm cá nhân, tự tính lãi suất thực, và nhận biết pha chu kỳ lãi suất.

```python
import requests

API_KEY = "your-api-key"  # Lấy tại vietdataverse.online/account
headers = {"X-API-Key": API_KEY}

# Lãi suất tiết kiệm ACB theo tất cả kỳ hạn
td  = requests.get("https://api.vietdataverse.online/api/v1/termdepo?bank=ACB",
                   headers=headers).json()["data"][0]
# CPI mới nhất để tính lãi suất thực
cpi = requests.get("https://api.vietdataverse.online/api/v1/macro/cpi",
                   headers=headers).json()["data"][0]

cpi_yoy = cpi["cpi_yoy"]  # ví dụ: 3.2

# Tính lãi suất thực cho từng kỳ hạn
print(f"CPI hiện tại: {cpi_yoy}%/năm")
print(f"{'Kỳ hạn':<12} {'Danh nghĩa':>12} {'Thực':>12} {'Đánh giá':>16}")
print("-" * 55)
for term, rate in [
    ("1 tháng",  td.get("term_1m")),
    ("3 tháng",  td.get("term_3m")),
    ("6 tháng",  td.get("term_6m")),
    ("12 tháng", td.get("term_12m")),
    ("24 tháng", td.get("term_24m")),
]:
    if rate is None:
        continue
    real = rate - cpi_yoy
    note = "✅ sinh lời thực" if real > 2 else ("⚠️ khiêm tốn" if real >= 0 else "❌ âm")
    print(f"{term:<12} {rate:>11.2f}%  {real:>11.2f}%  {note}")
```

**Bảng lãi suất thực vs danh nghĩa (ví dụ với CPI = 3.2%):**

| Kỳ hạn | Lãi danh nghĩa | Lãi thực | Nhận xét |
|--------|----------------|----------|---------|
| 1 tháng | 3.8%/năm | 0.6%/năm | Dương, nhưng thấp |
| 3 tháng | 4.2%/năm | 1.0%/năm | Bảo toàn vốn |
| 6 tháng | 4.8%/năm | 1.6%/năm | Khá |
| 12 tháng | 5.5%/năm | **2.3%/năm** | Tốt — sinh lời thực |
| 24 tháng | 5.8%/năm | **2.6%/năm** | Tốt nhất nếu khóa được |

*Lãi thực > 2%: tiền "thực sự tăng trưởng". Lãi thực < 0%: tiền đang mất giá trong ngân hàng.*

### Dành cho Researcher / Người không biết code

1. Nhấn **"📋 Copy to Claude"** trên trang thư viện Viet Dataverse
2. Mở [Claude.ai](https://claude.ai) → paste vào cửa sổ chat
3. Hỏi về tiết kiệm ngân hàng — Claude biết cách tính lãi thực, biết vòng chu kỳ lãi suất VN

**Câu hỏi gợi ý:**
- "Hiện tại lãi suất tiết kiệm 12 tháng có đang 'thực sự sinh lời' không khi tính cả lạm phát?"
- "Tôi có 500 triệu muốn gửi tiết kiệm — nên chia như thế nào và kỳ hạn bao lâu?"
- "NHNN vừa cắt lãi suất — tôi còn kịp khóa 12 tháng với lãi cao không?"
- "Lãi tiết kiệm ngân hàng nhỏ cao hơn 2% so với Big 4 — rủi ro đó có đáng không?"

---

## 1. Cấu trúc lãi suất tiết kiệm VN

### Phân loại ngân hàng và mức lãi suất thông thường

| Nhóm | Ví dụ | Lãi suất | Đặc điểm |
|------|-------|----------|----------|
| Big 4 (quốc doanh) | Vietcombank, BIDV, VietinBank, Agribank | Thấp nhất | An toàn nhất, không lo phá sản |
| Ngân hàng TMCP lớn | ACB, Techcombank, MB, VPBank | Trung bình | Cân bằng rủi ro-lợi nhuận |
| Ngân hàng TMCP nhỏ/online | BVBank, OceanBank, SCB* | Cao nhất | Rủi ro cao hơn |

*SCB là ví dụ cảnh báo: lãi suất cao bất thường → rủi ro thanh khoản

### Kỳ hạn phổ biến và quy tắc lợi suất
```
Kỳ hạn thường gặp: 1 tháng, 3 tháng, 6 tháng, 12 tháng, 18 tháng, 24 tháng
Quy tắc thông thường: kỳ hạn dài hơn = lãi suất cao hơn
Ngoại lệ: khi NHNN đang cắt lãi suất, đường cong có thể bị phẳng hoặc đảo ngược
```

---

## 2. Chu kỳ lãi suất VN và cách agent nhận biết

### Giai đoạn NHNN tăng lãi suất
**Dấu hiệu:** Tỷ giá căng, lạm phát vượt 4%, Fed tăng lãi suất  
**Hành vi ngân hàng:** Tăng lãi suất huy động để giữ tiền gửi  
**Chiến lược tiết kiệm tối ưu:** Gửi kỳ hạn ngắn (1-3 tháng), chờ lãi suất lên đỉnh rồi khóa dài

### Giai đoạn NHNN cắt lãi suất
**Dấu hiệu:** Lạm phát dưới 3%, tăng trưởng chậm, NHNN muốn kích thích kinh tế  
**Hành vi ngân hàng:** Hạ lãi suất huy động 0.5-1% sau 1-2 tháng  
**Chiến lược tiết kiệm tối ưu:** Khóa kỳ hạn dài (12-24 tháng) ngay khi NHNN vừa cắt

### Cách phát hiện đỉnh/đáy lãi suất
```python
# Tín hiệu đỉnh lãi suất (chuẩn bị gửi dài hạn):
- NHNN đã tăng 2+ lần liên tiếp
- Lạm phát đang giảm dần từ đỉnh
- Tỷ giá ổn định trở lại
- Lãi suất 12 tháng ACB/Techcombank > 8%/năm

# Tín hiệu đáy lãi suất (không nên khóa dài):
- NHNN đã cắt 2+ lần liên tiếp
- Lạm phát đang tăng trở lại
- Lãi suất 12 tháng < 5%/năm
```

---

## 3. Tính lãi suất thực (Real Rate)

```
Lãi suất thực = Lãi suất danh nghĩa - CPI

Ví dụ:
  ACB 12 tháng: 5.5%/năm
  CPI hiện tại: 3.2%/năm
  → Lãi suất thực: 5.5% - 3.2% = 2.3%/năm

Ngưỡng đánh giá:
  Lãi suất thực > 2%: tiết kiệm đang "thực sự sinh lời"
  Lãi suất thực 0-2%: tiết kiệm vẫn tốt hơn cash, nhưng khiêm tốn
  Lãi suất thực < 0%: tiền tiết kiệm đang mất giá trị thực → cân nhắc kênh khác
```

---

## 4. Bảo hiểm tiền gửi — điều agent phải biết

- Bảo hiểm tiền gửi VN (DIV): bảo hiểm tối đa **125 triệu VND/người/ngân hàng** (từ 12/2021)
- Nghĩa là: gửi 200 triệu ở 1 ngân hàng nhỏ → nếu ngân hàng đó phá sản, chỉ nhận lại 125 triệu
- Khuyến nghị cho số tiền > 125 triệu: **phân tán ra nhiều ngân hàng** hoặc ưu tiên Big 4

---

## 5. Prompt snippet cho agent tiết kiệm

```
Khi tư vấn gửi tiết kiệm ngân hàng VN:

1. Lấy lãi suất hiện tại: [dùng API Viet Dataverse /api/v1/termdepo]
2. Tính lãi suất thực = lãi suất ngân hàng - CPI hiện tại
3. Xác định pha chu kỳ:
   - SBV đang cắt lãi suất? → đề xuất khóa dài 12-24 tháng
   - SBV đang tăng? → đề xuất kỳ ngắn 1-3 tháng, theo dõi tiếp
4. Nhắc về giới hạn bảo hiểm 125 triệu/ngân hàng
5. KHÔNG so sánh với cổ phiếu hay vàng trừ khi user hỏi

Luôn ưu tiên tính an toàn trước lợi suất.
```

---

## 6. Dữ liệu API

```python
# Lãi suất tiết kiệm ACB theo kỳ hạn, lịch sử hàng ngày
GET https://api.vietdataverse.online/api/v1/termdepo?bank=ACB&period=1y

# Lịch sử lãi suất để phân tích xu hướng
GET https://api.vietdataverse.online/api/v1/termdepo?bank=ACB&period=3y

# CPI để tính lãi suất thực
GET https://api.vietdataverse.online/api/v1/macro/cpi
```
