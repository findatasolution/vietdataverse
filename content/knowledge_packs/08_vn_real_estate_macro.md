# Vietnam Real Estate Macro Cycle
**Dành cho:** Agent phân tích thị trường BĐS Việt Nam, tư vấn thời điểm mua/bán, theo dõi chu kỳ  
**Cảnh báo:** Dữ liệu BĐS VN rất khan hiếm và thiếu minh bạch — chủ yếu dùng proxy indicators

---

## Cách dùng pack này

### Dành cho Developer / Agent Builder

```python
import requests

API_KEY = "your-api-key"
headers = {"X-API-Key": API_KEY}

# BĐS VN không có price index API — dùng proxy indicators
# Proxy 1: Lãi suất (chi phí vốn mua nhà)
td = requests.get("https://api.vietdataverse.online/api/v1/termdepo?period=2y",
                  headers=headers).json()["data"]
# Proxy 2: VN30 nhóm BĐS (VIC, VHM, NVL)
vic = requests.get("https://api.vietdataverse.online/api/v1/vn30/ohlcv?ticker=VIC&period=1y",
                   headers=headers).json()["data"]

rate_now  = td[0].get("term_12m", 0)
rate_prev = td[-1].get("term_12m", 0)
print(f"Lãi suất 12m: {rate_prev:.1f}% → {rate_now:.1f}% ({'↓ hỗ trợ BĐS' if rate_now < rate_prev else '↑ kém hỗ trợ'})")
```

### Dành cho Researcher / Người không biết code

1. Nhấn **"📋 Copy to Claude"** trên thư viện Viet Dataverse
2. Mở [Claude.ai](https://claude.ai) → paste vào chat

**Câu hỏi gợi ý:**
- "NHNN vừa cắt lãi suất 0.5% — thị trường BĐS phục hồi trong bao lâu?"
- "Tôi đang nghĩ mua căn hộ Hà Nội — chu kỳ BĐS VN đang ở giai đoạn nào?"
- "BĐS VN có bong bóng không? Tôi nên lo ngại ở mức nào?"

---

## 1. Chu kỳ BĐS VN — 4 giai đoạn

Thị trường BĐS VN có chu kỳ khoảng 8-12 năm, tương tự các nền kinh tế đang phát triển:

```
Giai đoạn 1 — Đáy & Phục hồi sớm (1-2 năm):
  Dấu hiệu: Lãi suất đã cắt, tín dụng nới, nhưng giao dịch vẫn thấp
  Hành động thông minh: Mua — giá chưa phản ánh lãi suất thấp
  Nhóm cổ phiếu: VIC, VHM bắt đầu tạo đáy

Giai đoạn 2 — Tăng trưởng (3-5 năm):
  Dấu hiệu: Giao dịch tăng, giá tăng, nhiều dự án mới ra mắt
  Hành động: Nắm giữ / mua tích lũy
  Nhóm cổ phiếu: VHM, NVL dẫn dắt

Giai đoạn 3 — Bong bóng (1-2 năm):
  Dấu hiệu: Nhà đầu tư F0 ồ ạt vào, đòn bẩy cao, giá tăng phi lý
  Cảnh báo: Tín dụng BĐS > 20% tổng tín dụng, NHNN siết
  Nhóm cổ phiếu: Biến động mạnh, khó đoán

Giai đoạn 4 — Điều chỉnh (1-2 năm):
  Dấu hiệu: Thanh khoản đóng băng, giá giảm, doanh nghiệp BĐS khó khăn
  Cơ hội: Chuẩn bị mua ở giai đoạn 1 tiếp theo
  Nhóm cổ phiếu: NVL, DXG bị ảnh hưởng nặng nhất
```

---

## 2. Proxy Indicators — Thay thế cho Price Index

Vì VN không có chỉ số giá BĐS minh bạch như Case-Shiller (Mỹ), dùng proxy:

### Proxy tốt nhất

| Proxy | Đọc thế nào | Nguồn |
|-------|-------------|-------|
| Lãi suất cho vay mua nhà | < 8%/năm = hỗ trợ; > 10% = kém hỗ trợ | ACB/VCB công bố |
| Tín dụng BĐS / Tổng tín dụng | > 20% = rủi ro; < 15% = lành mạnh | NHNN |
| Cổ phiếu VHM, VIC (YTD) | Tăng > 20% = giai đoạn 2-3; giảm = giai đoạn 4 | Viet Dataverse |
| Giá trái phiếu doanh nghiệp BĐS | Spread tăng cao = stress; spread thấp = bình thường | VBMA |
| Số lượng dự án mới ra mắt | Nhiều = giai đoạn 2-3; ít = đáy | Báo cáo quý |

### Proxy cảnh báo sớm (leading indicators)
```
Cảnh báo đỉnh: (xuất hiện ít nhất 3/5)
  □ Lãi suất tăng 2+ lần trong năm
  □ Báo chí viết nhiều về "cơn sốt đất"
  □ Tỷ lệ vay/giá (LTV) trung bình > 70%
  □ Giá đất nền vùng ven tăng > 50% trong 2 năm
  □ Nhiều F0 (nhà đầu tư mới) vào thị trường

Cảnh báo đáy: (xuất hiện ít nhất 3/5)
  □ Tín dụng BĐS bị siết chặt > 18 tháng
  □ Doanh nghiệp BĐS phát hành trái phiếu không ra được
  □ Giao dịch sơ cấp giảm > 60% so đỉnh
  □ NHNN bắt đầu nới lỏng chính sách
  □ Chính phủ ban hành gói kích thích BĐS (nhà ở xã hội)
```

---

## 3. Tác động macro lên BĐS VN

```
Lãi suất SBV cắt → 6-12 tháng sau → giao dịch BĐS phục hồi
  Cơ chế: chi phí vay giảm → khả năng thanh toán tăng → cầu tăng

Tỷ giá VND mất giá → người có USD mua BĐS nhiều hơn (cất trữ)
  → BĐS cao cấp Hà Nội, TP.HCM hưởng lợi

FDI tăng → nhu cầu BĐS công nghiệp và nhà ở gần KCN tăng
  Địa bàn: Bình Dương, Đồng Nai, Bắc Giang, Hải Phòng

Kiều hối tăng (Tết, Q4) → một phần đổ vào BĐS, cầu tăng cuối năm
```

---

## 4. Phân biệt phân khúc

| Phân khúc | Nhạy với | Đặc điểm |
|-----------|----------|-----------|
| Căn hộ trung/cao cấp TP.HCM, HN | Lãi suất, thu nhập tầng lớp trung | Thanh khoản tốt hơn |
| Đất nền / BĐS vùng ven | Tâm lý đầu cơ, chính sách quy hoạch | Biến động mạnh nhất |
| BĐS công nghiệp (KCN) | FDI, chuỗi cung ứng | Ổn định nhất, yield tốt |
| Nhà ở xã hội | Chính sách Chính phủ | Ít biến động theo chu kỳ |

---

## 5. Prompt snippet cho agent BĐS

```
Khi phân tích thị trường BĐS VN, không dùng giá tuyệt đối (không có index đáng tin cậy).
Thay vào đó phân tích:

1. Pha chu kỳ (1-4) dựa trên proxy indicators
2. Lãi suất cho vay mua nhà hiện tại (từ ACB termdepo data làm proxy)
3. Xu hướng cổ phiếu VIC, VHM (VN30 data)
4. Chính sách tín dụng BĐS hiện tại (NHNN có đang siết không?)

Kết luận:
  Giai đoạn 1-2 + lãi suất thấp → thị trường tích cực
  Giai đoạn 3-4 + lãi suất tăng → thận trọng

KHÔNG đưa ra dự báo giá — chỉ phân tích pha chu kỳ và môi trường vĩ mô.
```

---

## 6. Nguồn dữ liệu API

```python
# Cổ phiếu BĐS trong VN30 (VIC, VHM, NVL)
GET https://api.vietdataverse.online/api/v1/vn30/ohlcv?ticker=VHM&period=2y
GET https://api.vietdataverse.online/api/v1/vn30/ohlcv?ticker=VIC&period=2y

# Lãi suất — proxy chi phí vốn mua nhà
GET https://api.vietdataverse.online/api/v1/termdepo?period=2y

# CPI — áp lực lạm phát ảnh hưởng sức mua
GET https://api.vietdataverse.online/api/v1/macro/cpi
```
