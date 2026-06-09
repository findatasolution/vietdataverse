# VN30 Sector Rotation Playbook
**Dành cho:** Agent phân tích cổ phiếu VN, xây dựng chiến lược danh mục theo chu kỳ kinh tế  
**Phạm vi:** 30 cổ phiếu vốn hóa lớn nhất HSX (VN30 Index)

---

## Cách dùng pack này

### Dành cho Developer / Agent Builder

Dán pack này vào system prompt để agent phân tích danh mục VN30, nhận biết sector đang được hưởng lợi dựa trên 3 tín hiệu vĩ mô: lãi suất SBV + tỷ giá + giá dầu.

```python
import requests

API_KEY = "your-api-key"  # Lấy tại vietdataverse.online/account
headers = {"X-API-Key": API_KEY}

# 3 tín hiệu vĩ mô để xác định pha rotation
sbv_rate = requests.get("https://api.vietdataverse.online/api/v1/sbv-rate",
                        headers=headers).json()["data"]
oil      = requests.get("https://api.vietdataverse.online/api/v1/global?symbol=CL%3DF",
                        headers=headers).json()["data"]
# Dữ liệu OHLCV cổ phiếu cụ thể
vcb      = requests.get("https://api.vietdataverse.online/api/v1/vn30/ohlcv?ticker=VCB&period=3m",
                        headers=headers).json()["data"]

# Inject context vào agent:
context = f"""
Tỷ giá USD/VND hiện tại: {sbv_rate[0]['vcb_sell']:,.0f} (so 30 ngày trước: {sbv_rate[-1]['vcb_sell']:,.0f})
Giá dầu WTI: ${oil[0]['close']:.1f}/thùng
VCB 3 tháng qua: từ {vcb[-1]['close']:,.0f} → {vcb[0]['close']:,.0f}
"""
# Dùng context này kèm với nội dung pack để agent phân tích rotation
```

### Dành cho Researcher / Người không biết code

1. Nhấn **"📋 Copy to Claude"** trên trang thư viện Viet Dataverse
2. Mở [Claude.ai](https://claude.ai) → paste vào cửa sổ chat
3. Hỏi về chiến lược cổ phiếu theo chu kỳ — Claude biết nhóm ngành nào hưởng lợi khi lãi suất thay đổi

**Câu hỏi gợi ý:**
- "SBV vừa cắt lãi suất lần đầu — nhóm cổ phiếu nào trong VN30 thường tăng mạnh nhất?"
- "Tỷ giá USD/VND đang tăng — doanh nghiệp nào trong VN30 bị ảnh hưởng xấu nhất?"
- "Tôi đang nắm VIC và VHM — nếu lãi suất tăng trở lại thì sao?"
- "Giá dầu tăng mạnh ảnh hưởng thế nào đến GAS, PLX, và HVN trong VN30?"

---

## 1. Phân nhóm ngành trong VN30

### Nhóm Ngân hàng (~40-45% tỷ trọng VN30)
VCB, BID, CTG, MBB, TCB, VPB, ACB, HDB, STB, MSB, VIB, OCB  
→ Nhóm có tỷ trọng lớn nhất, chi phối xu hướng toàn chỉ số

### Nhóm Bất động sản & Xây dựng
VIC, VHM, NVL, PDR, DXG, KDH  
→ Nhạy cảm nhất với lãi suất và tín dụng

### Nhóm Hàng tiêu dùng & Bán lẻ
VNM, MWG, PNJ, SAB, MSN  
→ Phòng thủ, ít biến động theo chu kỳ kinh tế

### Nhóm Năng lượng & Vật liệu
GAS, PLX, HPG, HSG  
→ Nhạy với giá hàng hóa toàn cầu (dầu, thép)

### Nhóm Hàng không & Logistics
HVN, ACV  
→ Nhạy với giá dầu và phục hồi du lịch

---

## 2. Rotation theo chu kỳ lãi suất

### Khi NHNN cắt lãi suất (giai đoạn nới lỏng)
```
Giai đoạn đầu (0-3 tháng sau cắt):
  ✅ Ngân hàng: NIM cải thiện, tín dụng tăng trưởng kỳ vọng → mua
  ✅ BĐS: chi phí vốn giảm, thanh khoản thị trường cải thiện → mua
  ⚠️  Tiêu dùng: trung tính

Giai đoạn giữa (3-9 tháng):
  ✅ BĐS: giao dịch thực tế phục hồi → tăng mạnh nhất
  ✅ Vật liệu xây dựng (HPG, HSG): theo sau BĐS
  ✅ Bán lẻ (MWG): tiêu dùng phục hồi khi lãi suất thấp

Giai đoạn cuối (9-18 tháng):
  ✅ Toàn thị trường thường tăng
  ⚠️  Cẩn thận BĐS nếu đã tăng quá mạnh
```

### Khi NHNN tăng lãi suất (giai đoạn thắt chặt)
```
  ❌ BĐS: bị ảnh hưởng đầu tiên và nặng nhất
  ❌ Ngân hàng nhỏ, vốn yếu: NIM bị ép
  ✅ Ngân hàng lớn (VCB, BID): tương đối phòng thủ
  ✅ Hàng tiêu dùng thiết yếu (VNM, SAB): ổn định
  ✅ GAS: hưởng lợi nếu giá dầu cao đi kèm
```

---

## 3. Rotation theo tỷ giá USD/VND

### VND mất giá (USD/VND tăng)
```
  ✅ Xuất khẩu: nhóm dệt may (không có trong VN30 nhưng liên quan)
  ✅ VNM: một phần doanh thu từ xuất khẩu sữa
  ❌ Nhập khẩu nguyên liệu: HPG (nhập thép phế), PLX (nhập xăng dầu)
  ❌ Doanh nghiệp vay USD: VIC, VHM, HVN
```

### VND mạnh lên (USD/VND giảm)
```
  ✅ Doanh nghiệp vay USD nặng: VIC, HVN
  ✅ Nhập khẩu nguyên liệu: HPG, PLX
```

---

## 4. Rotation theo giá dầu

```
Dầu tăng:
  ✅ GAS: doanh thu tỷ lệ thuận với giá dầu/khí
  ✅ PLX: margin lọc dầu có thể cải thiện ngắn hạn
  ❌ HVN: chi phí nhiên liệu chiếm 25-30% chi phí
  ❌ HPG: chi phí năng lượng tăng

Dầu giảm:
  Ngược lại hoàn toàn
```

---

## 5. Chỉ số kỹ thuật nhanh cho VN30

```
VN30 P/E lịch sử:
  Vùng rẻ:    P/E < 12x → thường là đáy chu kỳ
  Vùng hợp lý: P/E 12-16x
  Vùng đắt:   P/E > 18x → cẩn thận, thường gần đỉnh

VN-Index / VN30 correlation: > 0.95 → VN30 gần như đại diện toàn thị trường

Thanh khoản báo động:
  < 10.000 tỷ/phiên: thị trường ảm đạm
  10.000-20.000 tỷ: bình thường
  > 25.000 tỷ: sôi động, thường kèm biến động mạnh
```

---

## 6. Prompt snippet cho agent phân tích VN30

```
Khi phân tích VN30 hoặc tư vấn danh mục:

1. Xác định pha lãi suất (SBV đang tăng/giữ/cắt?)
2. Xác định pha tỷ giá (VND đang mạnh/yếu?)
3. Xác định giá dầu toàn cầu (tăng/giảm?)
4. Map sang nhóm ngành hưởng lợi/bất lợi theo bảng rotation

Khi tất cả 3 yếu tố thuận chiều cho ngân hàng (cắt lãi suất + VND ổn + dầu bình thường):
→ Nhóm ngân hàng thường dẫn dắt đà tăng

LUÔN nhắc: "Phân tích này chỉ mang tính tham khảo, không phải khuyến nghị đầu tư."
```

---

## 7. Dữ liệu API

```python
# Dữ liệu OHLCV VN30 stocks
GET https://api.vietdataverse.online/api/v1/vn30/ohlcv?ticker=VCB&period=1y

# Lãi suất SBV để xác định chu kỳ
GET https://api.vietdataverse.online/api/v1/sbv-rate

# Giá dầu quốc tế (Brent proxy qua GC=F)
GET https://api.vietdataverse.online/api/v1/global?symbol=GC%3DF
```
