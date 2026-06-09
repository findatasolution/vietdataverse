# Vietnam Macro Decoder
**Dành cho:** AI agent builder cần hiểu bối cảnh kinh tế vĩ mô Việt Nam  
**Định dạng:** Knowledge pack — nhét thẳng vào system prompt hoặc RAG context

---

## 1. Các chỉ số vĩ mô quan trọng nhất ở Việt Nam

### CPI (Lạm phát)
- Nguồn: Tổng cục Thống kê (GSO), công bố ngày 29-30 hàng tháng
- Mục tiêu Chính phủ: dưới 4.5%/năm (giai đoạn 2021-2025)
- Cách đọc: CPI YoY > 4% → NHNN có xu hướng giữ lãi suất cao hoặc tăng
- Basket gồm: lương thực (33%), nhà ở & vật liệu (18%), giao thông (9%), y tế (6%)
- Lưu ý: CPI VN nhạy cảm với giá xăng dầu và giá thịt heo hơn các nền kinh tế phát triển

### Lãi suất điều hành (SBV Policy Rate)
- Ngân hàng Nhà nước Việt Nam (NHNN/SBV) quyết định
- Lãi suất tái cấp vốn (refinancing rate): benchmark chính
- Chu kỳ cắt giảm 2023: từ 6% → 4.5% (cắt 4 lần liên tiếp)
- Khi SBV cắt lãi suất → lãi suất huy động ngân hàng thương mại giảm theo 1-3 tháng sau
- Khi SBV giữ/tăng → tín hiệu lo ngại lạm phát hoặc áp lực tỷ giá

### Tỷ giá USD/VND
- Chế độ: managed float — NHNN can thiệp khi VND mất giá quá 2-3% so với đầu năm
- Áp lực tỷ giá thường đến từ: Fed tăng lãi suất, nhập siêu tăng, dòng vốn FDI/FII rút
- Dải biên độ: NHNN cho phép dao động ±5% quanh tỷ giá trung tâm công bố hàng ngày
- Tỷ giá VCB thường là tham chiếu thực tế của thị trường
- Ngưỡng tâm lý: 24.000, 25.000, 26.000 VND/USD

### Tăng trưởng GDP
- Nguồn: GSO, công bố cuối mỗi quý
- Mục tiêu 2024-2025: 6-6.5%/năm
- Cấu trúc: công nghiệp chế biến (đặc biệt Samsung, Intel) ~28% GDP, dịch vụ ~42%
- GDP VN phụ thuộc nhiều vào xuất khẩu (~90% GDP) → nhạy với kinh tế Mỹ, EU, Trung Quốc

---

## 2. Mối quan hệ giữa các chỉ số (dùng cho agent reasoning)

```
Fed tăng lãi suất
  → USD mạnh lên toàn cầu
  → VND chịu áp lực mất giá
  → NHNN có thể phải tăng lãi suất để bảo vệ tỷ giá
  → Lãi suất huy động ngân hàng VN tăng
  → Dòng tiền dịch chuyển từ cổ phiếu/vàng sang tiết kiệm

Lạm phát VN tăng vượt 4%
  → NHNN giữ hoặc tăng lãi suất
  → Chi phí vay tăng → doanh nghiệp BĐS/xây dựng bị ảnh hưởng nhiều nhất
  → VN-Index thường điều chỉnh nhóm BĐS, vật liệu xây dựng

NHNN cắt lãi suất
  → 1-3 tháng sau: lãi suất tiết kiệm ngân hàng thương mại giảm
  → Tiền dịch chuyển ra khỏi tiết kiệm vào cổ phiếu/bất động sản
  → Nhóm ngân hàng, BĐS trên VN-Index thường được hưởng lợi trước
```

---

## 3. Lịch công bố dữ liệu quan trọng

| Chỉ số | Cơ quan | Thời điểm công bố |
|--------|---------|-------------------|
| CPI tháng | GSO | Ngày 29-30 hàng tháng |
| GDP quý | GSO | Cuối tháng cuối quý |
| Xuất nhập khẩu | GSO/Hải quan | Ngày 13-15 tháng tiếp theo |
| Tỷ giá trung tâm | NHNN | Mỗi ngày làm việc, 8h sáng |
| Lãi suất điều hành | NHNN | Không định kỳ, họp bất thường |
| Dự trữ ngoại hối | NHNN | Hàng quý (thường chậm 1 quý) |

---

## 4. Nguồn dữ liệu API có thể dùng trong agent

```python
# Viet Dataverse API — dữ liệu đã làm sạch, sẵn dùng
GET https://api.vietdataverse.online/api/v1/macro/cpi          # CPI lịch sử
GET https://api.vietdataverse.online/api/v1/sbv-rate           # Tỷ giá SBV hàng ngày
GET https://api.vietdataverse.online/api/v1/termdepo           # Lãi suất tiết kiệm
GET https://api.vietdataverse.online/api/v1/gold               # Giá vàng trong nước
```

---

## 5. Prompt snippet — dùng ngay trong agent

```
Khi phân tích tình hình kinh tế Việt Nam, ưu tiên theo thứ tự:
1. Lạm phát (CPI) so với mục tiêu 4.5%
2. Xu hướng lãi suất SBV (tăng/giữ/cắt)
3. Áp lực tỷ giá USD/VND (so với đầu năm)
4. Tăng trưởng GDP gần nhất

Nếu CPI > 4% VÀ tỷ giá mất giá > 2%: môi trường rủi ro cao, ưu tiên tài sản phòng thủ.
Nếu CPI < 3% VÀ SBV đang cắt lãi suất: môi trường thuận lợi cho tăng trưởng.
```
