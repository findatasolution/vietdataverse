# Fuel Forecast — Data Quality & Model Roadmap

Ordered by dependency — each stage assumes the previous one is solid before
work moves forward. Scope as of 2026-09-15: **E5RON92 + DO005S only** (RON95
dropped — product targets commercial/transport fuel cost, not passenger-car
gasoline).

## 1. Nguồn dữ liệu (source) OK

- [x] Nguồn chính thức: bản tin MOIT (`moit.gov.vn`) — xác nhận đây là MOPS
  thật (không phải proxy Brent/RBOB).
- [x] Pipeline không phụ thuộc Gemini/LLM — parser thuần regex
  (`be/fuel/moit_parser.py`), rủi ro/chi phí thấp hơn OCR hay LLM-extraction.
- [x] Xác nhận Bronze (R2, raw HTML + sha256) → Silver (`fuel_price_cycle`,
  `FUEL_FORECAST_DB`) đúng kiến trúc medallion.
- [ ] **Backfill khoảng trống 2024-03 → 2025-05** (14 tháng thiếu) — đang chạy
  probe weekly-Thursday theo 3 pattern URL đã xác nhận, nền tảng là mốc thật
  "04/01/2024 bắt đầu chu kỳ tuần" (Vietstock). Kết quả sẽ báo riêng.
- [ ] Đánh giá có nên mở rộng backfill về 2022-2023 (chu kỳ 10 ngày) sau khi
  biết tỷ lệ hit của giai đoạn 2024 — quyết định sau, không làm mù.
- [ ] webgia.com **không dùng được** cho fuel (link archive là link chết) —
  đã loại, không thử lại trừ khi có bằng chứng mới.

## 2. Data đầu vào clean + đúng validation

- [x] Bỏ 4 cột không dùng (`base_price`, `bog_contrib`, `bog_use`, `taxes`) —
  chỉ giữ `world_avg_price`, `retail_price` (2 biến model thực sự dùng).
- [x] Bỏ RON95 khỏi parser/DB/router/FE — chỉ còn E5RON92 + DO005S.
- [ ] Dọn dữ liệu RON95 cũ khỏi `fuel_price_cycle`, `fuel_forecast`,
  `fuel_backtest` sau khi backfill xong (tránh xoá nhầm dòng đang insert).
- [ ] Chạy lại `crawl_tools/data_quality_check.py`/tương đương cho
  `fuel_price_cycle` sau backfill — kiểm tra range, gap, trùng lặp trên tập
  dữ liệu mới lớn hơn nhiều.

## 3. Pipeline crawl vận hành ổn định

- [x] `fuel-pipeline.yml` — GitHub Actions, cron `'0 2 * * 4'` (09:00 VN
  thứ Năm), không chạy trên box.
- [x] Lỗi "MOIT đổi category không báo" (07/2026) đã fix cho crawl live.
- [ ] Cân nhắc thêm 2 pattern URL mới (`/thong-bao/...`, `/thong-bao/...-tai-ky-dieu-hanh-...`)
  phát hiện trong đợt backfill này vào `discover_latest()`/`MOIT_NEWS_INDEXES`
  nếu MOIT tiếp tục đổi cách đặt tên bài — hiện `discover_latest()` mới chỉ
  quét category, chưa thử đa pattern slug như bản backfill.
- [ ] Bật cron billing subscription (`subscription-billing.yml`) — cần user
  tự thêm secret `KNOWLEDGE_MARKET_DB` (bị chặn bởi chính sách an toàn Claude
  Code, đã đưa link/hướng dẫn).

## 4. Model performance tốt

- [x] `delta-world-v1` thắng random-walk có ý nghĩa thống kê (p<0.0001,
  Wilcoxon p<0.01) trên cả E5RON92 (skill 0.52-0.56) và DO005S (skill 0.78-0.82).
- [ ] Re-run backtest sau khi có dữ liệu backfill (n hiện tại chỉ 17-19,
  quá nhỏ để tin cậy cao — mục tiêu n≥50 sau backfill 2024).
- [ ] Spike đánh giá XGBoost/model hiện đại hơn OLS — **đã brainstorm nhưng
  chưa được user gật đầu triển khai**; chờ dữ liệu backfill trước vì n nhỏ
  hiện tại khiến so sánh không có ý nghĩa.
- [ ] Xử lý residual tự tương quan âm (AR(1) hoặc bootstrap CI) — vẫn treo,
  ưu tiên thấp hơn backfill vì không ảnh hưởng production ngay.

## 5. Chart/visualize hoạt động

- [x] Fan chart (`fe/pages/fuel-forecast.html`) đã live — lịch sử + kịch bản
  low/base/high + lock overlay theo tier.
- [x] Đã bỏ tab RON95, mặc định E5RON92.
- [ ] Cập nhật footer text "kỳ đầu 03/2024 bị bỏ do cách quãng 14 tháng" sau
  khi backfill lấp khoảng trống này — hiện đang nói sai nếu backfill thành công.
- [ ] Cập nhật bảng skill/R² tĩnh trên FE (`skillByFuel`/`r2ByFuel`) sau khi
  backtest chạy lại trên dữ liệu mới.
