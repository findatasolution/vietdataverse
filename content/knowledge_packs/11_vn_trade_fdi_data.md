# Vietnam Trade & FDI Data for Agents
**Dành cho:** Agent phân tích kinh tế vĩ mô VN, đánh giá sức khỏe nền kinh tế qua cán cân thương mại và FDI  
**Tại sao quan trọng:** VN là nền kinh tế hướng xuất khẩu — XNK và FDI giải thích phần lớn biến động tỷ giá và tăng trưởng

---

## Cách dùng pack này

### Dành cho Developer / Agent Builder

```python
import requests

API_KEY = "your-api-key"
headers = {"X-API-Key": API_KEY}

# CPI (proxy vĩ mô)
cpi = requests.get("https://api.vietdataverse.online/api/v1/macro/cpi",
                   headers=headers).json()["data"]

# Tỷ giá (kết quả cán cân thương mại)
fx  = requests.get("https://api.vietdataverse.online/api/v1/sbv-rate?period=1y",
                   headers=headers).json()["data"]

# Dữ liệu XNK thực tế lấy từ GSO/Hải quan (không có API)
# → Dùng Nasdaq/S&P như proxy sức khỏe kinh tế Mỹ (thị trường XK lớn nhất)
spx = requests.get("https://api.vietdataverse.online/api/v1/global?symbol=%5EGSPC&period=6m",
                   headers=headers).json()["data"]
print(f"S&P 500 6M: {spx[0]['close']:,.0f} (proxy cầu xuất khẩu sang Mỹ)")
```

### Dành cho Researcher / Người không biết code

1. Nhấn **"📋 Copy to Claude"** trên thư viện Viet Dataverse
2. Mở [Claude.ai](https://claude.ai) → paste vào chat

**Câu hỏi gợi ý:**
- "Mỹ sắp vào suy thoái — xuất khẩu VN sang Mỹ sẽ bị ảnh hưởng thế nào?"
- "FDI vào VN đang tăng hay giảm? Ngành nào đang nhận FDI nhiều nhất?"
- "Cán cân thương mại VN đang thặng dư hay thâm hụt? Ý nghĩa với tỷ giá?"

---

## 1. Cấu trúc xuất khẩu VN — ai mua hàng của VN

```
Thị trường xuất khẩu chính (2024, ~ổn định nhiều năm):
  Mỹ:         ~30% tổng XK (~90-100 tỷ USD/năm)
  Trung Quốc: ~18-20%
  EU:         ~12-15%
  ASEAN:      ~10%
  Nhật:       ~7-8%
  Hàn Quốc:  ~6-7%

Ngành xuất khẩu chính:
  Điện tử (Samsung, Intel): ~35-40% tổng XK
  Dệt may, da giày: ~15%
  Máy móc thiết bị: ~10%
  Thủy sản: ~4%
  Gỗ và sản phẩm gỗ: ~4%
  Cà phê, gạo, cao su: ~5%
```

**Implication cho agent:**
- Khi Mỹ suy thoái hoặc đồng đô la mạnh → XK điện tử VN sang Mỹ chậm lại
- Đơn hàng Samsung tăng/giảm → ảnh hưởng trực tiếp đến tăng trưởng GDP VN

---

## 2. Cấu trúc nhập khẩu VN

```
Ngành nhập khẩu chính:
  Máy móc, thiết bị:     ~30% (nguyên liệu sản xuất)
  Điện tử, linh kiện:    ~25% (Samsung re-import/export)
  Vải, nguyên liệu may:  ~10%
  Xăng dầu:              ~7%
  Thép, kim loại:        ~5%

Nguồn nhập khẩu chính:
  Trung Quốc: ~35% tổng NK
  Hàn Quốc:  ~18%
  ASEAN:     ~12%
  Nhật:      ~7%
  EU:        ~5%
```

**Implication:**
- VN phụ thuộc Trung Quốc về nguyên liệu sản xuất → supply chain risk
- Nhập khẩu nhiều từ TQ → khi VND mất giá so USD, chi phí nhập TQ tăng (qua CNY-USD)
- Trade war Mỹ-Trung → VN thường được hưởng lợi (chuyển dịch đơn hàng sang VN)

---

## 3. FDI — Vốn đầu tư trực tiếp nước ngoài

```
Tổng quan FDI VN:
  Đăng ký: ~35-40 tỷ USD/năm
  Giải ngân thực tế: ~18-22 tỷ USD/năm (phần giải ngân quan trọng hơn)
  
Top nhà đầu tư:
  Singapore: ~30% (hub đầu tư SE Asia)
  Hàn Quốc: ~20% (Samsung, LG)
  Nhật Bản: ~15%
  Trung Quốc: ~10% (đang tăng mạnh)
  
Ngành nhận FDI nhiều nhất:
  Chế biến chế tạo: ~60%
  Bất động sản: ~15%
  Điện, điện tử: ~10%
```

**Tại sao FDI quan trọng với tỷ giá:**
- FDI giải ngân → USD được chuyển thành VND → cung USD tăng → VND ổn định
- FDI chậm → ít cung USD → áp lực tỷ giá tăng

---

## 4. Proxy Indicators khi không có API

Vì GSO/Hải quan không có API, dùng các proxy có thể lấy được:

| Chỉ số thực | Proxy từ Viet Dataverse | Mức độ tương quan |
|------------|------------------------|-------------------|
| Kim ngạch XK sang Mỹ | S&P 500, Nasdaq (cầu Mỹ) | Trung bình |
| FDI giải ngân | VND/USD stability | Tốt |
| Cán cân thương mại | Tỷ giá trend (thặng dư → VND ổn) | Tốt |
| Đơn hàng Samsung | VN30 index chung + tỷ giá | Gián tiếp |

---

## 5. Prompt snippet cho agent thương mại-FDI

```
Khi phân tích sức khỏe thương mại VN:

Không có API trực tiếp cho XNK → dùng proxy:
1. Tỷ giá USD/VND trend (xuất siêu → VND ổn, thâm hụt → VND căng)
2. Dự trữ ngoại hối (NHNN công bố hàng quý — xem báo cáo gần nhất)
3. Sức khỏe kinh tế Mỹ (S&P 500) → cầu XK VN sang Mỹ

Tín hiệu cán cân thương mại tốt:
  VND ổn định trong bối cảnh USD mạnh toàn cầu
  → Nghĩa là VN đang tạo đủ USD từ xuất khẩu + FDI

Tín hiệu xấu:
  VND mất giá nhanh dù không có cú sốc toàn cầu rõ ràng
  → Có thể đang nhập siêu hoặc FDI chậm lại
```

---

## 6. Nguồn dữ liệu API

```python
# Tỷ giá — proxy cán cân thương mại
GET https://api.vietdataverse.online/api/v1/sbv-rate?period=1y

# S&P 500 — proxy cầu Mỹ (thị trường XK số 1 của VN)
GET https://api.vietdataverse.online/api/v1/global?symbol=%5EGSPC&period=6m

# Nasdaq — proxy cầu điện tử/công nghệ (Samsung, Intel)
GET https://api.vietdataverse.online/api/v1/global?symbol=%5EIXIC&period=6m

# Nguồn thực tế (không có API, phải đọc thủ công):
# GSO: https://www.gso.gov.vn/ → Báo cáo tháng → Xuất nhập khẩu
# Hải quan: https://www.customs.gov.vn/
# TCTK portal: https://portal.gso.gov.vn/
```
