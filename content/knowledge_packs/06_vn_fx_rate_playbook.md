# Vietnam FX Rate Playbook (USD/VND)
**Dành cho:** Agent phân tích tỷ giá, cảnh báo rủi ro tỷ giá cho doanh nghiệp và nhà đầu tư  
**Đặc điểm:** VND là đồng tiền managed float — không thả nổi tự do, không cố định — hiểu đúng cơ chế này là cốt lõi

---

## Cách dùng pack này

### Dành cho Developer / Agent Builder

```python
import requests

API_KEY = "your-api-key"
headers = {"X-API-Key": API_KEY}

# Tỷ giá USD/VND hàng ngày (VCB + SBV)
fx = requests.get("https://api.vietdataverse.online/api/v1/sbv-rate?period=90d",
                  headers=headers).json()["data"]

# Tính áp lực tỷ giá so đầu năm
rate_ytd_start = fx[-1]["vcb_sell"]  # đầu năm (dữ liệu cũ nhất trong 90d)
rate_now       = fx[0]["vcb_sell"]   # hôm nay
depreciation_pct = (rate_now - rate_ytd_start) / rate_ytd_start * 100

print(f"VND đã mất giá {depreciation_pct:.2f}% so đầu kỳ")
if depreciation_pct > 2:
    print("⚠️ Ngưỡng cảnh báo — NHNN có thể can thiệp")
```

### Dành cho Researcher / Người không biết code

1. Nhấn **"📋 Copy to Claude"** trên thư viện Viet Dataverse
2. Mở [Claude.ai](https://claude.ai) → paste vào chat

**Câu hỏi gợi ý:**
- "VND vừa mất giá 1.5% trong tháng — NHNN sẽ làm gì? Ảnh hưởng đến lãi suất không?"
- "Tôi nhập khẩu hàng từ Mỹ — khi nào nên mua USD để hedge tỷ giá?"
- "Tại sao tỷ giá VCB khác tỷ giá trung tâm SBV? Cái nào phản ánh thị trường hơn?"

---

## 1. Cơ chế Managed Float của VND

Việt Nam không có tỷ giá cố định cũng không thả nổi hoàn toàn:

```
Tỷ giá trung tâm (central rate):
  NHNN công bố mỗi ngày làm việc lúc 8h sáng
  Được tính dựa trên rổ 8 đồng tiền (USD, EUR, CNY, JPY, KRW, SGD, TWD, THB)
  
Biên độ giao dịch:
  Ngân hàng thương mại được phép giao dịch ±5% so với tỷ giá trung tâm
  
Tỷ giá thực tế thị trường:
  VCB, ACB, Techcombank công bố tỷ giá mua/bán riêng
  Thường xuyên ở đầu biên độ khi áp lực mạnh
```

**Tại sao managed float?** NHNN cần cân bằng 3 mục tiêu:
1. Kiểm soát lạm phát (tỷ giá cao → hàng nhập khẩu đắt)
2. Hỗ trợ xuất khẩu (VND yếu → hàng VN rẻ hơn trên thị trường quốc tế)
3. Thu hút FDI (ổn định tỷ giá → nhà đầu tư nước ngoài tin tưởng)

---

## 2. Các yếu tố tác động tỷ giá USD/VND

### Từ bên ngoài (không kiểm soát được)
```
Fed tăng lãi suất → USD mạnh toàn cầu → VND chịu áp lực mất giá
  → Lịch sử: Fed cycle 2022-2023 đẩy USD/VND từ 23.000 lên 24.800 (+8%)

Căng thẳng thương mại US-China → dòng vốn rút khỏi emerging markets
  → VND, IDR, MYR thường bị bán cùng lúc

Giá dầu tăng → nhập siêu tăng → cầu USD tăng → VND yếu
  (VN nhập khẩu ~60% xăng dầu tiêu thụ)
```

### Từ trong nước (NHNN có thể tác động)
```
Cán cân thương mại: xuất siêu → cung USD dồi dào → VND ổn định
  VN thường xuất siêu 5-15 tỷ USD/năm → yếu tố đỡ tỷ giá

FDI giải ngân: mỗi tỷ USD FDI vào → áp lực tăng giá VND
  FDI ~18-20 tỷ USD/năm = nguồn cung USD lớn và ổn định

Kiều hối: ~17-20 tỷ USD/năm, đỉnh vào Q4 (Tết)
  → Q4 thường là thời điểm tỷ giá dễ thở nhất

Dự trữ ngoại hối: NHNN bán USD can thiệp khi tỷ giá vượt ngưỡng
  Mức an toàn: > 3 tháng nhập khẩu (~80-90 tỷ USD hiện tại)
```

---

## 3. Ngưỡng tỷ giá và tín hiệu can thiệp

```
Ngưỡng tâm lý và hành động:

VND mất giá < 1% YTD:  Bình thường, không can thiệp
VND mất giá 1-2% YTD:  NHNN theo dõi chặt, có thể phát tín hiệu
VND mất giá 2-3% YTD:  NHNN bắt đầu bán dự trữ ngoại hối (can thiệp)
VND mất giá > 3% YTD:  Can thiệp mạnh + khả năng tăng lãi suất

Dấu hiệu NHNN sắp can thiệp:
  - Tỷ giá VCB bán liên tục ở mức đầu biên độ (gần ±5%)
  - Chênh lệch VCB sell - SBV central rate > 350 VND
  - NHNN phát biểu "ổn định thị trường ngoại tệ"
  - Dự trữ ngoại hối giảm liên tiếp 2-3 tháng
```

---

## 4. Ảnh hưởng tỷ giá lên các ngành/tài sản

| Tỷ giá | Hưởng lợi | Bị ảnh hưởng xấu |
|--------|-----------|------------------|
| USD/VND tăng (VND mất giá) | Xuất khẩu dệt may, thủy sản, gỗ | Doanh nghiệp vay USD (VIC, HVN) |
| USD/VND tăng | Kiều hối → BĐS, tiêu dùng | Nhập khẩu nguyên liệu (HPG, PLX) |
| USD/VND giảm (VND mạnh) | Doanh nghiệp vay USD | Cạnh tranh xuất khẩu giảm |
| USD/VND ổn định | FDI tiếp tục vào | — |

---

## 5. Prompt snippet cho agent tỷ giá

```
Khi phân tích rủi ro tỷ giá USD/VND:

1. Tính % thay đổi YTD: (rate_now - rate_jan1) / rate_jan1 * 100
2. So sánh với ngưỡng: <1% (an toàn) / 1-2% (theo dõi) / >2% (rủi ro)
3. Xem xu hướng Fed: đang tăng/giữ/cắt lãi suất?
4. Kiểm tra cán cân thương mại VN gần nhất (GSO)
5. Đưa ra khuyến nghị hedge nếu doanh nghiệp có exposure USD

KHÔNG dự báo tỷ giá cụ thể — chỉ phân tích áp lực và rủi ro.
Luôn nhắc: NHNN có thể can thiệp bất ngờ.
```

---

## 6. Nguồn dữ liệu API

```python
# Tỷ giá USD/VND theo ngày (VCB + SBV central rate)
GET https://api.vietdataverse.online/api/v1/sbv-rate?bank=VCB&period=1y

# So sánh VCB vs SBV central rate
GET https://api.vietdataverse.online/api/v1/sbv-rate?bank=SBV&period=1y

# DXY proxy (vàng quốc tế phản ánh USD strength)
GET https://api.vietdataverse.online/api/v1/global?symbol=GC%3DF&period=3m
```
