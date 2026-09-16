# Fuel Forecast — Data Quality & Model Roadmap

## Backfill methodology (standard for future gap-filling — 2026-09-16)

Decision: 3 options were ranked by the user — (1) fixed-location dashboard
with a logically-changing URL, (2) free third-party API/dataset, (3) deep
research (web search) for historical info. **Option 1 does not exist for
this source** — MOIT publishes only prose news articles, never a
table/JSON/dashboard, across 5+ incompatible URL slug templates over the
years (verified by checking MOIT's own transparency mirror
`minhbach.moit.gov.vn` too — same prose format, yet another prefix).
Approved combination: **option 2 + option 3**.

- **Option 2 (free dataset, not a live API)**: Kaggle
  `suthcong/fuel-prices-in-vietnam` (`Petrolimex_oilprice.csv`), downloaded
  anonymously via `kagglehub` (no API key/account needed) — Petrolimex Zone
  1/2 retail prices per real cycle date, 2022-12-01 → 2026-04-16. Checked
  `github.com/TranQui004/vietfuel-api`'s claimed live API first — its
  documented endpoint (`vietfuel-api.tranqui.workers.dev`) does not resolve
  (DNS failure), not usable.
- **Option 3 (deep research)**: no dedicated "deep research" tool exists in
  this environment — WebSearch used iteratively, one query per few
  months, each returning several real bulletin URLs at once.
- **Kaggle's role is date discovery only, never a value source in the DB.**
  Its retail_price has no MOPS/world-price companion, so every row actually
  inserted into `fuel_price_cycle` still comes from fetching and regex-
  parsing the real MOIT bulletin for that confirmed-real date (same
  `be/fuel/moit_parser.py` pipeline as the live crawler) — Kaggle's number
  is used only as an **independent cross-check** against the MOIT-parsed
  value (>2% disagreement would flag for review; 0 flags across 22 rows
  checked this way).
- **Per-row provenance**: unchanged from every other row in this table —
  the `source` column stores the literal MOIT URL that was fetched. No new
  column added; this was judged sufficient granularity (anyone querying the
  table sees exactly which page each number came from).
- **Reusable script**: `crawl_tools/backfill_moit_fuel_kaggle_assisted.py`
  — run again if the Kaggle dataset gets a newer version with a longer
  date range, or if another free real-date-oracle dataset is found later.
- **Result (2026-09-16)**: `fuel_price_cycle` grew from 74 → **114** cycles
  (+40) in one pass: 22 via the scripted Kaggle-date pipeline, 20 via manual
  WebSearch rounds for dates Kaggle knew about but the script's fixed URL
  pattern list didn't reach. ~76 Kaggle-confirmed real dates still have no
  known MOIT URL — logged in the script's own output, not force-guessed;
  a future WebSearch pass (or a wider pattern list) can pick these up.

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
- [x] **Backfill 2024-03 → 2025-05** — xong 2026-09-15: 26/72 tuần tìm được
  (36% hit), dựa trên mốc thật "04/01/2024 bắt đầu chu kỳ tuần" (Vietstock).
  `fuel_price_cycle` từ 25 → 51 kỳ. Backtest + forecast đã chạy lại, deploy
  lên prod, verify qua API thật.
- [x] **Backfill 2022-01 → 2023-10** — xong 2026-09-15: **17/62 kỳ tìm được**
  (27%, thấp hơn 2024's 36% — slug MOIT giai đoạn này thiếu chuẩn hoá: có kỳ
  dùng tiêu đề tự do theo hướng giá lên/xuống, ví dụ
  `gia-xang-dau-tang-nhe-trong-ky-dieu-hanh-ngay-3-1-2022.html`, không đoán
  được bằng pattern cố định). Sửa 1 bug quan trọng giữa 2 lần chạy: slug thật
  zero-pad NGÀY nhưng KHÔNG zero-pad THÁNG (`ngay-01-3-2022`, không phải
  `ngay-01-03-2022`) — bug này khiến lần chạy đầu chỉ được 2/62. Tổng DB giờ
  **74 kỳ**, 2022-01-21 → 2026-08-27. Dừng ở đây theo quyết định chuyển sang
  bước 2 (không tiếp tục đào bằng WebSearch từng khoảng trống — có thể làm
  sau nếu cần thêm).
- [ ] webgia.com **không dùng được** cho fuel (link archive là link chết) —
  đã loại, không thử lại trừ khi có bằng chứng mới.

## 2. Data đầu vào clean + đúng validation

- [x] Bỏ 4 cột không dùng (`base_price`, `bog_contrib`, `bog_use`, `taxes`) —
  chỉ giữ `world_avg_price`, `retail_price` (2 biến model thực sự dùng).
  DROP COLUMN đã chạy thật trên DB (qua `psql`, không chỉ ALTER trong file).
- [x] Bỏ RON95 khỏi parser/DB/router/FE — chỉ còn E5RON92 + DO005S. Đã xoá
  sạch dữ liệu cũ (`fuel_price_cycle` -50, `fuel_forecast` -192,
  `fuel_backtest` -28), verify còn 0 dòng.
- [x] **Data quality check retrospective** — chạy 2026-09-15 trên toàn bộ
  148 dòng (74 kỳ × 2 fuel): range check (world 30-400 USD/bbl, retail
  10k-60k VND/L), duplicate `(fuel,period)`, orphan (kỳ thiếu 1 trong 2 fuel),
  bước nhảy giá đơn kỳ >25%. **0 lỗi thật.** 4 cảnh báo "jump" đều rơi vào
  khoảng cách 35-112 ngày (nhiều kỳ bị miss dồn thành 1 bước nhảy quan sát
  được, không phải lỗi parse) — 2 trong số đó khớp đúng sự kiện BOG-fund
  tháng 3/2026 đã ghi trong `CLAUDE.md`. Chưa có script cố định hoá thành
  `crawl_tools/`-style — nếu cần chạy định kỳ thì viết thành file riêng, hiện
  mới chạy ad-hoc.

## 3. Pipeline crawl vận hành ổn định

- [x] `fuel-pipeline.yml` — GitHub Actions, cron `'0 2 * * 4'` (09:00 VN
  thứ Năm), không chạy trên box.
- [x] Lỗi "MOIT đổi category không báo" (07/2026) đã fix cho crawl live.
- [x] **Verify pipeline hoạt động thật trên prod** — kích `workflow_dispatch`
  thật (run `34995482145`), cả 2 job xanh (`extract-land`, `model`). Verify
  bằng query DB thật (không chỉ tin log CI): `crawl_time` mới nhất nhảy đúng
  thời điểm chạy, `fuel_backtest`/`fuel_forecast` có `run_ts` mới, chỉ còn
  đúng E5RON92/DO005S (xác nhận code bỏ RON95 đã chạy đúng trên production
  pipeline, không chỉ local).
- [ ] Cân nhắc thêm các pattern URL mới phát hiện trong đợt backfill này
  (`/thong-bao/...`, `/thong-bao/...-tai-ky-dieu-hanh-...`,
  `/thi-truong-trong-nuoc/thong-tin-dieu-hanh-xang-dau-...` cho giai đoạn
  2022) vào `discover_latest()`/`MOIT_NEWS_INDEXES` nếu MOIT tiếp tục đổi
  cách đặt tên bài — hiện `discover_latest()` mới chỉ quét category, chưa thử
  đa pattern slug như bản backfill.
- [x] **Cron billing subscription live** — secret `KNOWLEDGE_MARKET_DB` đã
  thêm (2026-09-15, sau khi user tự thêm Bash permission rule). Chạy thật
  phát hiện **2 bug chưa từng lộ ra** (chưa từng chạy thật lần nào trước đó):
  (1) `be/services/email.py` che khuất module `email` chuẩn của Python khi
  script chạy trực tiếp (`python be/services/subscription.py`) — đổi tên
  thành `email_service.py`; (2) fix sys.path nằm trong `if __name__ ==
  "__main__"` nên chạy sau các import top-level, luôn quá muộn — chuyển lên
  đầu file. Verify xanh trên CI thật (không chỉ local) sau cả 2 fix.

## 4. Model performance tốt

- [x] `delta-world-v1` thắng random-walk có ý nghĩa thống kê (p<0.0001,
  Wilcoxon p<0.01) trên cả E5RON92 và DO005S.
- [x] Backtest cuối cùng (n=108, sau backfill Kaggle+WebSearch 2026-09-16,
  114 kỳ tổng): E5RON92 skill **0.745** (R² 0.88), DO005S skill **0.778**
  (R² 0.93) — cả 2 ổn định qua mọi lần refit từ n=17 đến n=108, không phải
  may mắn mẫu nhỏ. 2 cảnh báo "jump" trong DQ check (2026-02-26→03-07) là
  sự kiện BOG-fund thật đã biết, không phải lỗi.
- [x] **3 gate trước XGBoost đã xong (2026-09-15/16): backfill ✅ (114 kỳ),
  data quality check ✅ (0 lỗi thật), verify pipeline trên prod ✅
  (workflow_dispatch thật, DB query xác nhận).** XGBoost có thể bắt đầu —
  chờ user gật đầu vì đây là việc build mới, chưa triển khai gì ngoài 1 lần
  brainstorm sơ bộ.
- [ ] Xử lý residual tự tương quan âm (AR(1) hoặc bootstrap CI) — vẫn treo,
  ưu tiên thấp hơn, không ảnh hưởng production ngay.

## 5. Chart/visualize hoạt động

- [x] Fan chart (`fe/pages/fuel-forecast.html`) đã live — lịch sử + kịch bản
  low/base/high + lock overlay theo tier.
- [x] Đã bỏ tab RON95, mặc định E5RON92.
- [x] Cập nhật footer text + bảng skill/R² tĩnh trên FE sau backfill 2024 —
  đã deploy, verify qua API thật (`vietdataverse.online`).
- [ ] Cập nhật lại lần nữa sau khi backfill 2022-2023 xong (n sẽ đổi thêm).
