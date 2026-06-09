"""Seed 8 mock listings for Knowledge Marketplace launch.

One product per category: accounting, trading, macro, policy,
sentiment, risk-management, esg, crypto.

Idempotent — safe to run multiple times.
R2 upload is attempted; if env vars are missing the file_r2_key is stored
as NULL and a warning is printed. Download will not work until R2 vars are set.

Usage (from repo root):
    cd be && python scripts/seed_mock_listings.py
"""

import hashlib
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent.parent / ".env")

DB_URL = os.getenv("KNOWLEDGE_MARKET_DB")
if not DB_URL:
    sys.exit("KNOWLEDGE_MARKET_DB env var not set — aborting.")

# Add be/ to path so core.r2 is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.r2 import upload_file, compute_sha256  # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VND_SELLER_USER_ID = 0  # Reserved slot — Viet Dataverse first-party team
VND_SELLER_EMAIL = "team@vietdataverse.online"
VND_SELLER_DISPLAY_NAME = "Viet Dataverse Team"
VND_SELLER_BIO = (
    "First-party content team. High-quality datasets, schemas, and context packs "
    "for Vietnam financial AI agents."
)

# ---------------------------------------------------------------------------
# File content for each product
# ---------------------------------------------------------------------------

CONTENT_ACCOUNTING = json.dumps(
    {
        "schema_name": "vn_tt200_chart_of_accounts",
        "version": "1.0",
        "regulation": "Circular 200/2014/TT-BTC",
        "issued_by": "Ministry of Finance — Vietnam",
        "effective_date": "2015-01-01",
        "accounts": [
            {"code": "111",  "name": "Tiền mặt",                                      "type": "asset",     "level": 2, "description": "Cash on hand"},
            {"code": "1111", "name": "Tiền Việt Nam",                                  "type": "asset",     "level": 3, "description": "VND cash"},
            {"code": "1112", "name": "Ngoại tệ",                                       "type": "asset",     "level": 3, "description": "Foreign currency cash"},
            {"code": "112",  "name": "Tiền gửi ngân hàng",                             "type": "asset",     "level": 2, "description": "Bank deposits"},
            {"code": "1121", "name": "Tiền Việt Nam gửi ngân hàng",                    "type": "asset",     "level": 3, "description": "VND bank deposits"},
            {"code": "1122", "name": "Ngoại tệ gửi ngân hàng",                         "type": "asset",     "level": 3, "description": "Foreign currency bank deposits"},
            {"code": "121",  "name": "Chứng khoán kinh doanh",                         "type": "asset",     "level": 2, "description": "Trading securities"},
            {"code": "128",  "name": "Đầu tư nắm giữ đến ngày đáo hạn",               "type": "asset",     "level": 2, "description": "Held-to-maturity investments"},
            {"code": "131",  "name": "Phải thu của khách hàng",                        "type": "asset",     "level": 2, "description": "Trade receivables"},
            {"code": "133",  "name": "Thuế GTGT được khấu trừ",                        "type": "asset",     "level": 2, "description": "Deductible VAT"},
            {"code": "141",  "name": "Tạm ứng",                                        "type": "asset",     "level": 2, "description": "Advances to employees"},
            {"code": "152",  "name": "Nguyên liệu, vật liệu",                          "type": "asset",     "level": 2, "description": "Raw materials"},
            {"code": "153",  "name": "Công cụ, dụng cụ",                               "type": "asset",     "level": 2, "description": "Tools and instruments"},
            {"code": "155",  "name": "Thành phẩm",                                     "type": "asset",     "level": 2, "description": "Finished goods"},
            {"code": "156",  "name": "Hàng hoá",                                       "type": "asset",     "level": 2, "description": "Merchandise inventory"},
            {"code": "211",  "name": "Tài sản cố định hữu hình",                       "type": "asset",     "level": 2, "description": "Tangible fixed assets"},
            {"code": "213",  "name": "Tài sản cố định vô hình",                        "type": "asset",     "level": 2, "description": "Intangible fixed assets"},
            {"code": "214",  "name": "Hao mòn tài sản cố định",                        "type": "asset",     "level": 2, "description": "Accumulated depreciation (contra)"},
            {"code": "217",  "name": "Bất động sản đầu tư",                            "type": "asset",     "level": 2, "description": "Investment property"},
            {"code": "241",  "name": "Xây dựng cơ bản dở dang",                        "type": "asset",     "level": 2, "description": "Construction in progress"},
            {"code": "311",  "name": "Vay và nợ thuê tài chính ngắn hạn",              "type": "liability", "level": 2, "description": "Short-term borrowings"},
            {"code": "331",  "name": "Phải trả cho người bán",                         "type": "liability", "level": 2, "description": "Trade payables"},
            {"code": "333",  "name": "Thuế và các khoản phải nộp Nhà nước",            "type": "liability", "level": 2, "description": "Taxes payable to State"},
            {"code": "334",  "name": "Phải trả người lao động",                        "type": "liability", "level": 2, "description": "Payroll payable"},
            {"code": "338",  "name": "Phải trả, phải nộp khác",                        "type": "liability", "level": 2, "description": "Other payables"},
            {"code": "341",  "name": "Vay và nợ thuê tài chính dài hạn",               "type": "liability", "level": 2, "description": "Long-term borrowings"},
            {"code": "411",  "name": "Vốn đầu tư của chủ sở hữu",                     "type": "equity",    "level": 2, "description": "Paid-in capital"},
            {"code": "419",  "name": "Cổ phiếu quỹ",                                  "type": "equity",    "level": 2, "description": "Treasury stock (contra equity)"},
            {"code": "421",  "name": "Lợi nhuận sau thuế chưa phân phối",              "type": "equity",    "level": 2, "description": "Retained earnings"},
            {"code": "511",  "name": "Doanh thu bán hàng và cung cấp dịch vụ",        "type": "revenue",   "level": 2, "description": "Revenue from sales and services"},
            {"code": "515",  "name": "Doanh thu hoạt động tài chính",                  "type": "revenue",   "level": 2, "description": "Financial income"},
            {"code": "521",  "name": "Các khoản giảm trừ doanh thu",                  "type": "revenue",   "level": 2, "description": "Revenue deductions (returns, discounts)"},
            {"code": "611",  "name": "Mua hàng",                                       "type": "expense",   "level": 2, "description": "Purchases (periodic inventory)"},
            {"code": "621",  "name": "Chi phí nguyên liệu, vật liệu trực tiếp",       "type": "expense",   "level": 2, "description": "Direct material costs"},
            {"code": "622",  "name": "Chi phí nhân công trực tiếp",                   "type": "expense",   "level": 2, "description": "Direct labour costs"},
            {"code": "627",  "name": "Chi phí sản xuất chung",                        "type": "expense",   "level": 2, "description": "Manufacturing overhead"},
            {"code": "632",  "name": "Giá vốn hàng bán",                              "type": "expense",   "level": 2, "description": "Cost of goods sold"},
            {"code": "635",  "name": "Chi phí tài chính",                             "type": "expense",   "level": 2, "description": "Financial expenses (interest, FX loss)"},
            {"code": "641",  "name": "Chi phí bán hàng",                              "type": "expense",   "level": 2, "description": "Selling expenses"},
            {"code": "642",  "name": "Chi phí quản lý doanh nghiệp",                 "type": "expense",   "level": 2, "description": "General & administrative expenses"},
            {"code": "811",  "name": "Chi phí khác",                                  "type": "expense",   "level": 2, "description": "Other expenses"},
            {"code": "821",  "name": "Chi phí thuế thu nhập doanh nghiệp",            "type": "expense",   "level": 2, "description": "Corporate income tax expense"},
        ],
    },
    ensure_ascii=False,
    indent=2,
)

CONTENT_TRADING = """\
# Từ điển Trader Chứng khoán Việt Nam — Vietnam Stock Trading Glossary

> Version 1.0 — Viet Dataverse Team
> Dùng làm context cho AI agent phân tích kỹ thuật, cơ bản và giao dịch tại thị trường chứng khoán Việt Nam.

---

## 1. Sàn giao dịch (Exchanges)

| Ký hiệu | Tên đầy đủ | Ghi chú |
|---------|-----------|---------|
| HOSE | Ho Chi Minh Stock Exchange — Sở GDCK TP.HCM | Cổ phiếu vốn hoá lớn |
| HNX  | Hanoi Stock Exchange — Sở GDCK Hà Nội | Cổ phiếu và trái phiếu |
| UPCoM | Unlisted Public Company Market | Doanh nghiệp đại chúng chưa niêm yết |

## 2. Chỉ số thị trường (Indices)

- **VN-Index** — Chỉ số tổng hợp HOSE (tất cả cổ phiếu niêm yết)
- **VN30** — Top 30 cổ phiếu vốn hoá lớn nhất, thanh khoản cao nhất HOSE
- **HNX30** — Top 30 cổ phiếu HNX
- **HNX-Index** — Chỉ số tổng hợp HNX
- **UPCOM-Index** — Chỉ số UPCoM

## 3. Loại lệnh (Order Types)

| Lệnh | Tiếng Anh | Mô tả |
|------|-----------|-------|
| LO | Limit Order | Lệnh giới hạn — khớp tại giá chỉ định hoặc tốt hơn |
| ATO | At The Opening | Lệnh khớp đầu phiên (9:00–9:15) theo giá mở cửa |
| ATC | At The Closing | Lệnh khớp cuối phiên (14:30–14:45) theo giá đóng cửa |
| MP | Market Price | Lệnh thị trường (HNX) — khớp ngay theo giá tốt nhất |
| MTL | Market To Limit | Lệnh chuyển sang LO sau khi khớp một phần (HNX) |
| MOK | Match Or Kill | Khớp toàn bộ hoặc huỷ (HNX) |
| MAK | Match And Kill | Khớp một phần, huỷ phần còn lại (HNX) |
| PLO | Put Through Limit Order | Lệnh thoả thuận |

## 4. Phiên giao dịch (Trading Sessions — HOSE)

| Phiên | Giờ | Loại lệnh |
|-------|-----|-----------|
| Mở cửa (Opening) | 9:00–9:15 | ATO + LO |
| Liên tục sáng | 9:15–11:30 | LO |
| Nghỉ trưa | 11:30–13:00 | — |
| Liên tục chiều | 13:00–14:30 | LO |
| Đóng cửa (Closing) | 14:30–14:45 | ATC + LO |
| Thoả thuận | 15:00–15:30 | PLO |

## 5. Biên độ dao động giá (Price Limits)

| Sàn | Biên độ cổ phiếu | Biên độ chứng chỉ quỹ ETF |
|-----|-----------------|--------------------------|
| HOSE | ±7% | ±7% |
| HNX  | ±10% | ±10% |
| UPCoM | ±15% | ±15% |

- **Giá trần (ceiling)** — giá cao nhất có thể khớp trong phiên
- **Giá sàn (floor)** — giá thấp nhất có thể khớp trong phiên
- **Giá tham chiếu (reference price)** — giá đóng cửa phiên trước

## 6. Phân tích kỹ thuật — Chỉ báo (Technical Indicators)

### Đường trung bình động
- **MA (Moving Average)** — Trung bình cộng giá đóng cửa N phiên (MA5, MA10, MA20, MA50, MA100, MA200)
- **EMA (Exponential Moving Average)** — Trung bình động hàm mũ, nhạy hơn với giá gần nhất
- **WMA (Weighted Moving Average)** — Trung bình động có trọng số

### Momentum & Oscillators
- **RSI (Relative Strength Index)** — Chỉ số sức mạnh tương đối (0–100). >70 = overbought, <30 = oversold
- **MACD** — Moving Average Convergence Divergence. MACD line = EMA12 − EMA26. Signal = EMA9 của MACD
- **Stochastic %K/%D** — So sánh giá đóng cửa với vùng giá trong N phiên. >80 = overbought, <20 = oversold
- **CCI (Commodity Channel Index)** — Đo độ lệch giá so với trung bình thống kê
- **Williams %R** — Tương tự Stochastic nhưng âm

### Volatility
- **Bollinger Bands** — Upper/Middle/Lower bands = MA20 ± 2σ. Giá chạm upper = quá mua; lower = quá bán
- **ATR (Average True Range)** — Đo biên độ biến động trung bình N phiên
- **Keltner Channel** — Kênh dựa trên EMA và ATR

### Volume
- **OBV (On-Balance Volume)** — Tích luỹ khối lượng theo chiều giá
- **VWAP (Volume-Weighted Average Price)** — Giá trung bình theo khối lượng
- **MFI (Money Flow Index)** — RSI tính theo giá × khối lượng

## 7. Mô hình nến Nhật (Candlestick Patterns)

### Đảo chiều tăng (Bullish Reversal)
- **Hammer** — Nến búa: thân nhỏ trên, bóng dưới dài ≥2× thân
- **Inverted Hammer** — Búa ngược: thân nhỏ dưới, bóng trên dài
- **Bullish Engulfing** — Nến tăng nhấn chìm toàn bộ nến giảm trước
- **Morning Star** — 3 nến: giảm → doji/pin → tăng mạnh
- **Three White Soldiers** — Ba nến tăng liên tiếp, mỗi nến mở trong thân nến trước
- **Piercing Line** — Nến tăng đóng trên 50% thân nến giảm trước

### Đảo chiều giảm (Bearish Reversal)
- **Shooting Star** — Sao băng: thân nhỏ dưới, bóng trên dài ≥2× thân
- **Hanging Man** — Nến treo: giống Hammer nhưng ở đỉnh xu hướng tăng
- **Bearish Engulfing** — Nến giảm nhấn chìm nến tăng trước
- **Evening Star** — 3 nến: tăng → doji/pin → giảm mạnh
- **Three Black Crows** — Ba nến giảm liên tiếp
- **Dark Cloud Cover** — Nến giảm mở trên đỉnh, đóng dưới 50% thân nến tăng

### Trung lập / Do dự
- **Doji** — Mở ≈ Đóng; thể hiện do dự, cân bằng cung cầu
- **Spinning Top** — Thân nhỏ, bóng hai đầu xấp xỉ nhau
- **Marubozu** — Không có bóng; nến tăng/giảm mạnh thuần tuý

## 8. Phân tích cơ bản — Chỉ số tài chính (Fundamental Ratios)

| Chỉ số | Công thức | Ý nghĩa |
|--------|-----------|---------|
| P/E | Giá / EPS | Số năm thu hồi vốn theo lợi nhuận |
| P/B | Giá / Book value per share | So giá thị trường với giá trị sổ sách |
| EPS | LNST / Số CP lưu hành | Lợi nhuận trên mỗi cổ phiếu |
| ROE | LNST / VCSH bình quân | Hiệu quả sử dụng vốn chủ |
| ROA | LNST / Tổng tài sản bình quân | Hiệu quả sử dụng tài sản |
| EBITDA | Lợi nhuận trước lãi vay, thuế, khấu hao | Dòng tiền hoạt động |
| Dividend Yield | Cổ tức / Giá | Tỷ suất cổ tức |
| Debt/Equity | Nợ dài hạn / VCSH | Đòn bẩy tài chính |

## 9. Thuật ngữ thị trường tổng hợp

- **Room ngoại** (Foreign Ownership Limit — FOL) — Tỷ lệ sở hữu nước ngoài tối đa (thường 49–100%)
- **Khối ngoại mua/bán ròng** (Foreign Net Buy/Sell) — Giá trị mua trừ bán của nhà đầu tư nước ngoài
- **Breakout** — Giá vượt ngưỡng kháng cự hoặc hỗ trợ quan trọng
- **Support / Resistance** — Ngưỡng hỗ trợ / kháng cự
- **Sideways** — Thị trường đi ngang, không xu hướng rõ
- **Gap** — Khoảng trống giá giữa hai phiên
- **Block Trade** — Giao dịch thoả thuận khối lượng lớn ngoài sàn
- **Treasury Stock** (Cổ phiếu quỹ) — CP công ty mua lại, không có quyền biểu quyết
- **Margin** — Đòn bẩy ký quỹ; tỷ lệ tối đa 50% theo quy định UBCK
- **T+2** — Ngày thanh toán: khớp hôm nay, nhận CP sau 2 ngày giao dịch
- **Circuit Breaker** — Ngưỡng tạm dừng giao dịch khi VN-Index giảm quá 5% trong phiên
- **ETF** (Exchange-Traded Fund) — Quỹ ETF niêm yết (E1VFVN30, FUEVFVND...)
- **Covered Warrant (CW)** — Chứng quyền có bảo đảm (HOSE)
- **IPO** — Lần đầu phát hành cổ phiếu ra công chúng
- **Rights Issue** — Phát hành thêm cổ phiếu cho cổ đông hiện hữu
- **ESOP** — Cổ phiếu phát hành cho cán bộ nhân viên
"""

CONTENT_MACRO = """\
# Context Vĩ mô Việt Nam cho AI Agent — Vietnam Macro Context Pack

> Version 1.0 — Viet Dataverse Team
> System prompt context cho Claude/GPT agent phân tích kinh tế vĩ mô Việt Nam.
> Nguồn chính thống: Tổng cục Thống kê (GSO/NSO), Ngân hàng Nhà nước (SBV), Bộ Tài chính (MOF).

---

## 1. Chỉ số Giá tiêu dùng — CPI (Consumer Price Index)

**Định nghĩa:** Chỉ số đo biến động giá của rổ hàng hoá và dịch vụ tiêu dùng điển hình.
**Nguồn:** Tổng cục Thống kê — nso.gov.vn (trước là gso.gov.vn)
**Tần suất:** Hàng tháng (công bố tuần đầu tháng tiếp theo)
**Đơn vị:** % thay đổi so với tháng trước (MoM) hoặc cùng kỳ năm trước (YoY)
**Rổ tính (11 nhóm hàng hoá):**
  - Hàng ăn và dịch vụ ăn uống (trọng số ~36%)
  - Nhà ở, điện, nước, chất đốt (~18%)
  - Giao thông (~9%)
  - Giáo dục (~6%)
  - Thuốc và dịch vụ y tế (~6%)
  - Các nhóm khác (~25%)

**Ngưỡng mục tiêu:** SBV mục tiêu CPI bình quân dưới 4.5%/năm.
**Cách đọc cho AI agent:**
- CPI YoY > 4%: cảnh báo lạm phát, SBV có thể thắt chặt tiền tệ
- CPI YoY 2–4%: ổn định, thuận lợi cho tăng trưởng
- CPI YoY < 1%: rủi ro giảm phát, SBV có thể nới lỏng

---

## 2. Tổng sản phẩm quốc nội — GDP

**Định nghĩa:** Giá trị thị trường tổng sản phẩm và dịch vụ cuối cùng sản xuất trong lãnh thổ.
**Nguồn:** Tổng cục Thống kê
**Tần suất:** Hàng quý (Q1: tháng 4, Q2: tháng 7, Q3: tháng 10, Q4: tháng 1 năm sau)
**Cách phân loại:**
  - Theo ngành: Nông lâm nghiệp & thuỷ sản | Công nghiệp & xây dựng | Dịch vụ
  - Theo chi tiêu: Tiêu dùng cuối cùng + GFCF + Thay đổi tồn kho + Xuất khẩu ròng

**Tốc độ tăng trưởng lịch sử:**
  - 2019: 7.02% | 2020: 2.91% (COVID) | 2021: 2.58% (lockdown)
  - 2022: 8.02% | 2023: 5.05% | 2024: 7.09%

**Ngưỡng tham chiếu:**
- GDP tăng trưởng >6.5%: cao — tích cực cho tâm lý thị trường cổ phiếu
- GDP 5–6.5%: trung bình — ổn định
- GDP <4%: thấp — rủi ro suy giảm kinh tế

---

## 3. Chỉ số Sản xuất Công nghiệp — IIP (Industrial Production Index)

**Định nghĩa:** Đo biến động sản lượng sản xuất của ngành công nghiệp (khai khoáng, chế biến, điện nước).
**Nguồn:** Tổng cục Thống kê
**Tần suất:** Hàng tháng
**Ngành chủ chốt theo dõi:**
  - Điện tử, máy tính (chiếm ~30% sản xuất)
  - Dệt may, da giầy
  - Ô tô, xe máy
  - Thép, xi măng

**Cách đọc:** IIP YoY > 8% = sản xuất mạnh; <3% = chậm lại; âm = suy giảm

---

## 4. Chỉ số Giá sản xuất — PPI (Producer Price Index)

**Định nghĩa:** Chỉ số giá tại cửa nhà máy, trước khi đến người tiêu dùng. Dự báo xu hướng CPI tương lai.
**Nguồn:** Tổng cục Thống kê
**Tần suất:** Hàng tháng
**Ý nghĩa:** PPI tăng trước CPI 1–3 tháng — dùng để dự báo lạm phát tương lai cho AI agent

---

## 5. Cán cân Thương mại (Trade Balance)

**Định nghĩa:** Giá trị xuất khẩu trừ nhập khẩu hàng hoá.
**Nguồn:** Tổng cục Thống kê / Tổng cục Hải quan
**Tần suất:** Hàng tháng (ước tính) + điều chỉnh hàng quý

**Thị trường xuất khẩu chính (2024):**
  - Mỹ: ~30% tổng kim ngạch XK
  - Trung Quốc: ~16%
  - EU: ~12%
  - ASEAN: ~10%

**Hàng xuất khẩu chính:** Điện thoại, máy tính, máy móc, dệt may, da giầy, thuỷ sản
**Hàng nhập khẩu chính:** Máy móc, điện tử, nguyên liệu sản xuất, xăng dầu

**Cách đọc:** Thặng dư thương mại dương → hỗ trợ VND và dự trữ ngoại hối

---

## 6. Lãi suất Ngân hàng Nhà nước — SBV Interest Rates

**Các loại lãi suất điều hành:**

| Loại | Mô tả | Giá trị tham chiếu (2024) |
|------|-------|--------------------------|
| Lãi suất tái cấp vốn | SBV cho NHTM vay ngắn hạn | 4.50%/năm |
| Lãi suất tái chiết khấu | SBV chiết khấu giấy tờ có giá | 3.00%/năm |
| Lãi suất cho vay qua đêm (O/N) | Liên ngân hàng qua đêm | biến động |
| Lãi suất OMO | Nghiệp vụ thị trường mở | biến động |

**Cách đọc cho AI agent:**
- SBV cắt giảm lãi suất → nới lỏng tiền tệ → kích thích tăng trưởng → tích cực cổ phiếu, BĐS
- SBV tăng lãi suất → thắt chặt → kiềm chế lạm phát → tiêu cực ngắn hạn cổ phiếu
- Xu hướng 2023–2024: SBV cắt giảm 4 lần liên tiếp từ 6% xuống 4.5%

---

## 7. Tỷ giá Hối đoái (Exchange Rate — USD/VND)

**Nguồn:** SBV công bố tỷ giá trung tâm hàng ngày
**Cơ chế:** Tỷ giá trung tâm ± biên độ 5% (NHTM có thể giao dịch trong biên độ này)
**Cặp tỷ giá chính:** USD/VND (tham chiếu thị trường); EUR/VND, CNY/VND
**Dự trữ ngoại hối:** ~90–100 tỷ USD (Q4 2024) — SBV can thiệp khi VND biến động mạnh

**Cách đọc:**
- USD/VND tăng (VND mất giá) > 3%/năm: SBV can thiệp bán USD, hoặc tăng lãi suất OMO
- Dự trữ giảm mạnh: áp lực tỷ giá cao, có thể điều chỉnh chính sách
- Tác động xuất khẩu: VND yếu → lợi thế xuất khẩu ngắn hạn, bất lợi nhập khẩu nguyên liệu

---

## 8. Chỉ số Niềm tin Kinh doanh (Business Confidence / PMI)

**PMI (Purchasing Managers Index):** S&P Global/IHS Markit công bố hàng tháng
  - > 50: mở rộng (expansion)
  - < 50: thu hẹp (contraction)
  - Lịch sử: VN PMI dao động 48–52 giai đoạn 2022–2024

---

## 9. Prompt Engineering Tips cho AI Agent

```
SYSTEM CONTEXT:
Bạn là AI agent phân tích kinh tế vĩ mô Việt Nam.
- CPI nguồn từ nso.gov.vn, tần suất tháng, target <4.5%/năm
- GDP nguồn từ GSO, tần suất quý, tăng trưởng mục tiêu 6.5–7%
- Lãi suất điều hành từ SBV (sbv.gov.vn), hiện tại 4.5% tái cấp vốn
- Khi phân tích lạm phát: xem PPI trước (leading indicator), rồi CPI
- Khi phân tích thị trường cổ phiếu: kết hợp GDP, CPI, lãi suất SBV, tỷ giá
```
"""

CONTENT_POLICY = json.dumps(
    {
        "schema_name": "vn_banking_regulation_compliance",
        "version": "1.0",
        "description": "Schema for AI compliance agent checking Vietnam banking regulations",
        "regulations": [
            {
                "id": "TT02_2023",
                "name": "Thông tư 02/2023/TT-NHNN",
                "topic": "Loan Classification & Provisioning",
                "effective_date": "2023-04-24",
                "source": "https://vbpl.vn/nganhangnhanuoc/Pages/vbpq-van-ban-goc.aspx?ItemID=156742",
                "debt_groups": [
                    {
                        "group": 1,
                        "name": "Nợ đủ tiêu chuẩn (Standard)",
                        "overdue_days": "0–10",
                        "provision_rate_pct": 0,
                        "risk_weight_pct": 100,
                    },
                    {
                        "group": 2,
                        "name": "Nợ cần chú ý (Special Mention)",
                        "overdue_days": "10–90",
                        "provision_rate_pct": 5,
                        "risk_weight_pct": 100,
                    },
                    {
                        "group": 3,
                        "name": "Nợ dưới tiêu chuẩn (Substandard)",
                        "overdue_days": "90–180",
                        "provision_rate_pct": 20,
                        "risk_weight_pct": 150,
                    },
                    {
                        "group": 4,
                        "name": "Nợ nghi ngờ (Doubtful)",
                        "overdue_days": "180–360",
                        "provision_rate_pct": 50,
                        "risk_weight_pct": 150,
                    },
                    {
                        "group": 5,
                        "name": "Nợ có khả năng mất vốn (Loss)",
                        "overdue_days": ">360",
                        "provision_rate_pct": 100,
                        "risk_weight_pct": 150,
                    },
                ],
                "npl_threshold_pct": 3.0,
                "agent_rule": "If group >= 3 → flag as NPL. If portfolio NPL > 3% → trigger escalation.",
            },
            {
                "id": "TT13_2018",
                "name": "Thông tư 13/2018/TT-NHNN (amended by TT22/2023)",
                "topic": "Capital Adequacy Ratio — CAR (Basel II)",
                "source": "https://sbv.gov.vn",
                "ratios": {
                    "CAR_minimum_pct": 8.0,
                    "Tier1_CAR_minimum_pct": 6.0,
                    "conservation_buffer_pct": 2.5,
                    "total_minimum_with_buffer_pct": 10.5,
                },
                "formula": "CAR = (Tier 1 Capital + Tier 2 Capital) / Risk-Weighted Assets",
                "agent_rule": "If CAR < 8% → critical violation. If CAR 8–10% → monitor closely.",
                "risk_weights": {
                    "cash_and_sbv": 0,
                    "government_bonds": 0,
                    "residential_mortgage": 50,
                    "corporate_loans": 100,
                    "consumer_loans": 100,
                    "real_estate_investment": 150,
                    "equity": 150,
                },
            },
            {
                "id": "TT22_2019",
                "name": "Thông tư 22/2019/TT-NHNN",
                "topic": "Credit Growth Limits & Real Estate Exposure",
                "source": "https://sbv.gov.vn",
                "limits": {
                    "credit_growth_annual_guidance_pct": 14,
                    "real_estate_loan_to_total_credit_max_pct": 70,
                    "short_term_funds_for_medium_long_term_loans_max_pct": 30,
                    "single_borrower_exposure_max_pct_of_equity": 15,
                    "group_borrower_exposure_max_pct_of_equity": 25,
                },
                "agent_rule": "If real_estate_ratio > 70% → flag overexposure. Check single-borrower limit against equity.",
            },
            {
                "id": "TT41_2016",
                "name": "Thông tư 41/2016/TT-NHNN",
                "topic": "Liquidity Coverage Ratio — LCR",
                "source": "https://sbv.gov.vn",
                "ratios": {
                    "LCR_minimum_pct": 100,
                    "NSFR_minimum_pct": 100,
                },
                "formula": "LCR = High-Quality Liquid Assets / Total Net Cash Outflows over 30 days",
                "agent_rule": "If LCR < 100% → liquidity breach. If LCR 100–110% → heightened monitoring.",
            },
        ],
        "decision_tree": {
            "step_1": "Check CAR >= 8% (TT13). If not → CRITICAL.",
            "step_2": "Check NPL ratio <= 3% (TT02). If not → ELEVATED RISK.",
            "step_3": "Check LCR >= 100% (TT41). If not → LIQUIDITY RISK.",
            "step_4": "Check real-estate exposure <= 70% (TT22). If not → CONCENTRATION RISK.",
            "step_5": "All pass → COMPLIANT.",
        },
        "agent_prompt_template": (
            "You are a Vietnam banking compliance AI. "
            "Given a bank's metrics (CAR, NPL ratio, LCR, real-estate exposure), "
            "check each threshold in this schema and return a JSON compliance report "
            "with fields: {compliant: bool, violations: [], risk_level: 'low'|'medium'|'high'|'critical'}."
        ),
    },
    ensure_ascii=False,
    indent=2,
)

CONTENT_SENTIMENT = json.dumps(
    {
        "lexicon_version": "1.0",
        "domain": "vietnam_finance",
        "language": "vi",
        "description": "Vietnam finance sentiment lexicon for NLP and LLM-based analysis",
        "positive": [
            "tăng trưởng", "hồi phục", "lãi", "khởi sắc", "bứt phá", "đột phá",
            "kỷ lục", "vượt kỳ vọng", "vững", "ổn định", "tích cực", "cải thiện",
            "tăng mạnh", "tăng vọt", "tăng tốt", "tăng cao", "đỉnh mới",
            "lợi nhuận tăng", "doanh thu tăng", "tăng trưởng mạnh", "phục hồi",
            "khả quan", "triển vọng tốt", "sáng sủa", "lạc quan", "tin tưởng",
            "nâng dự báo", "nâng mục tiêu", "đánh giá tích cực", "mua vào",
            "tích luỹ", "khuyến nghị mua", "outperform", "vượt trội",
            "cổ tức cao", "chia cổ tức", "thưởng cổ phiếu", "mua lại cổ phiếu quỹ",
            "dòng vốn vào", "khối ngoại mua ròng", "thanh khoản tốt",
            "lãi suất giảm", "nới lỏng tiền tệ", "hỗ trợ thị trường",
            "tín dụng tăng", "PMI tăng", "IIP tăng", "xuất khẩu tăng",
            "GDP tăng", "CPI thấp", "lạm phát kiểm soát",
            "giải ngân FDI tăng", "FDI vào", "vốn ngoại tăng",
            "đơn hàng tăng", "sản xuất mở rộng", "công suất tăng",
        ],
        "negative": [
            "sụp đổ", "suy thoái", "lỗ", "giảm sốc", "khủng hoảng", "vỡ nợ",
            "thua lỗ", "đáy", "sụt giảm", "giảm mạnh", "giảm sâu", "giảm đột biến",
            "cảnh báo", "rủi ro cao", "lo ngại", "tiêu cực", "bi quan",
            "áp lực giảm", "bán tháo", "hoảng loạn", "panic sell",
            "lợi nhuận giảm", "doanh thu giảm", "thua lỗ tăng", "nợ xấu tăng",
            "vi phạm", "phạt", "điều tra", "thanh tra", "cưỡng chế",
            "hạ dự báo", "hạ mục tiêu", "đánh giá tiêu cực", "bán ra",
            "khuyến nghị bán", "underperform", "thoái vốn",
            "khối ngoại bán ròng", "rút vốn", "dòng vốn ra",
            "lãi suất tăng", "thắt chặt tiền tệ", "tăng lãi suất",
            "tín dụng giảm", "PMI giảm dưới 50", "IIP giảm", "xuất khẩu giảm",
            "GDP giảm", "CPI cao", "lạm phát tăng", "lạm phát vượt mục tiêu",
            "đình lạm", "stagflation", "suy giảm kinh tế",
            "phá sản", "giải thể", "mất khả năng thanh toán",
            "nợ xấu", "nhóm nợ 5", "trích lập dự phòng lớn",
            "mất thanh khoản", "rủi ro hệ thống", "domino",
        ],
        "neutral": [
            "dao động", "biến động", "thay đổi", "điều chỉnh", "ổn định",
            "ngang", "đi ngang", "sideway", "không đổi", "duy trì",
            "giữ nguyên", "chờ đợi", "theo dõi", "quan sát",
            "phân kỳ", "hội tụ", "cân bằng", "trung lập",
            "tham khảo", "ghi nhận", "công bố", "thông báo",
            "dự kiến", "kế hoạch", "mục tiêu", "định hướng",
        ],
        "intensifiers": [
            "rất", "cực", "siêu", "mạnh", "đột ngột", "nhanh", "đáng kể",
            "đột biến", "bất ngờ", "ấn tượng",
        ],
        "negators": [
            "không", "chưa", "chẳng", "không còn", "không thể", "khó",
        ],
        "usage_note": (
            "For LLM prompts: prepend this lexicon as system context. "
            "Score = count(positive hits) - count(negative hits). "
            "Apply intensifier multiplier 1.5x. Apply negator flip. "
            "Normalize by token count for comparable scores."
        ),
    },
    ensure_ascii=False,
    indent=2,
)

CONTENT_RISK = """\
# Schema Chấm điểm Tín dụng Việt Nam — Vietnam Credit Risk Scoring Schema

schema_name: vn_credit_risk_scoring
version: "1.0"
regulation_references:
  - "TT 02/2023/TT-NHNN — Loan classification"
  - "TT 13/2018/TT-NHNN — CAR / Basel II"
  - "Basel II standardised approach"
applicable_to: "Corporate borrowers — Vietnamese entities"

---

## Scoring Model Overview

Total score range: 0 – 100
Rating bands:
  - A  (85–100): Excellent — low risk, standard terms
  - B  (70–84):  Good — acceptable risk, normal monitoring
  - C  (55–69):  Moderate — elevated risk, enhanced monitoring
  - D  (40–54):  Poor — high risk, restrictive covenants
  - E  (0–39):   Critical — decline or special management

---

## Scoring Dimensions (5 pillars)

### Pillar 1: Financial Health (35 points)

dimension: financial_health
max_score: 35
metrics:
  - name: debt_to_equity
    weight: 10
    thresholds:
      excellent:  { operator: "<=", value: 1.0, score: 10 }
      good:       { operator: "<=", value: 2.0, score: 7  }
      moderate:   { operator: "<=", value: 3.0, score: 4  }
      poor:       { operator: ">",  value: 3.0, score: 1  }
    note: "Higher D/E = more leveraged. >3x is high for VN corporate"

  - name: current_ratio
    weight: 8
    thresholds:
      excellent:  { operator: ">=", value: 2.0, score: 8 }
      good:       { operator: ">=", value: 1.5, score: 6 }
      moderate:   { operator: ">=", value: 1.0, score: 3 }
      poor:       { operator: "<",  value: 1.0, score: 0 }
    note: "CR < 1 = current liabilities exceed current assets"

  - name: interest_coverage_ratio
    weight: 9
    formula: "EBIT / Interest Expense"
    thresholds:
      excellent:  { operator: ">=", value: 5.0, score: 9 }
      good:       { operator: ">=", value: 3.0, score: 6 }
      moderate:   { operator: ">=", value: 1.5, score: 3 }
      poor:       { operator: "<",  value: 1.5, score: 0 }

  - name: net_profit_margin
    weight: 8
    formula: "Net Profit / Revenue"
    thresholds:
      excellent:  { operator: ">=", value: 0.10, score: 8 }
      good:       { operator: ">=", value: 0.05, score: 5 }
      moderate:   { operator: ">=", value: 0.02, score: 2 }
      poor:       { operator: "<",  value: 0.02, score: 0 }

---

### Pillar 2: Cash Flow Quality (25 points)

dimension: cash_flow
max_score: 25
metrics:
  - name: operating_cash_flow_to_debt
    weight: 15
    formula: "Operating Cash Flow / Total Debt"
    thresholds:
      excellent:  { operator: ">=", value: 0.30, score: 15 }
      good:       { operator: ">=", value: 0.15, score: 10 }
      moderate:   { operator: ">=", value: 0.05, score: 5  }
      poor:       { operator: "<",  value: 0.05, score: 0  }
    note: "Primary repayment source; most important metric"

  - name: cash_conversion_cycle_days
    weight: 10
    formula: "DIO + DSO - DPO"
    thresholds:
      excellent:  { operator: "<=", value: 30,  score: 10 }
      good:       { operator: "<=", value: 60,  score: 7  }
      moderate:   { operator: "<=", value: 90,  score: 4  }
      poor:       { operator: ">",  value: 90,  score: 1  }

---

### Pillar 3: Industry & Macro Risk (20 points)

dimension: industry_risk
max_score: 20
industry_risk_table:
  - industry: "Technology/Software"
    risk_level: low
    score: 18
  - industry: "Consumer Staples"
    risk_level: low
    score: 17
  - industry: "Banking/Financial Services"
    risk_level: medium
    score: 14
  - industry: "Manufacturing/Industrial"
    risk_level: medium
    score: 13
  - industry: "Retail/Trade"
    risk_level: medium
    score: 12
  - industry: "Construction"
    risk_level: high
    score: 8
  - industry: "Real Estate Development"
    risk_level: high
    score: 7
  - industry: "Mining/Resources"
    risk_level: high
    score: 6

macro_adjustment:
  - condition: "CPI YoY > 5%"
    adjustment: -2
  - condition: "USD/VND change > 3% in 3 months (VND depreciation)"
    adjustment: -2
  - condition: "Industry PMI < 48 for 3+ months"
    adjustment: -3

---

### Pillar 4: Credit History (10 points)

dimension: credit_history
max_score: 10
source: "Vietnam CIC (Credit Information Center) — cic.org.vn"
metrics:
  - name: cic_classification
    thresholds:
      group_1: { score: 10, description: "No overdue history" }
      group_2: { score: 6,  description: "1–90 days overdue in past 2 years" }
      group_3: { score: 3,  description: "90–180 days overdue in past 2 years" }
      group_4_5: { score: 0, description: "180+ days overdue or written off" }

---

### Pillar 5: Business Fundamentals (10 points)

dimension: business_fundamentals
max_score: 10
metrics:
  - name: years_in_operation
    weight: 4
    thresholds:
      excellent:  { operator: ">=", value: 10, score: 4 }
      good:       { operator: ">=", value: 5,  score: 3 }
      moderate:   { operator: ">=", value: 2,  score: 1 }
      poor:       { operator: "<",  value: 2,  score: 0 }

  - name: ownership_structure
    weight: 3
    values:
      state_owned_enterprise: 3
      joint_stock_listed: 3
      joint_stock_unlisted: 2
      private_limited: 1
      foreign_owned: 2

  - name: audited_financials_available
    weight: 3
    values:
      big4_audited: 3
      other_licensed_auditor: 2
      unaudited: 0

---

## Aggregate Scoring Formula

total_score = pillar1 + pillar2 + pillar3 + pillar4 + pillar5

rating:
  - score >= 85: "A"
  - score >= 70: "B"
  - score >= 55: "C"
  - score >= 40: "D"
  - score <  40: "E"

## Automatic Decline Rules (override score)

override_decline_if_any:
  - "CIC group 4 or 5 on any active loan"
  - "Operating cash flow negative for 2 consecutive years"
  - "Debt/Equity > 5x for non-financial companies"
  - "Regulatory sanctions or criminal investigation pending"

## AI Agent Prompt Template

system_prompt: |
  You are a Vietnam credit risk scoring AI.
  Given a company's financial data (D/E ratio, current ratio, ICR, net margin,
  operating cash flow/debt, CCC, industry, CIC group, years in operation,
  ownership type, audit status), compute the 5-pillar score and return:
  {
    "total_score": <int 0-100>,
    "rating": "<A|B|C|D|E>",
    "pillar_scores": { "financial_health": int, "cash_flow": int,
                       "industry_risk": int, "credit_history": int,
                       "business_fundamentals": int },
    "override_decline": <bool>,
    "override_reason": "<string if override>",
    "recommendation": "<approve|approve_with_conditions|decline>"
  }
"""

CONTENT_ESG = """\
# Framework Báo cáo ESG Việt Nam — Vietnam ESG Reporting Framework

> Version 1.0 — Viet Dataverse Team
> Dành cho AI agent hỗ trợ doanh nghiệp Việt Nam lập báo cáo ESG.
> Chuẩn áp dụng: SSC Vietnam Guideline 2023, GRI Standards 2021, TCFD 2017.

---

## 1. Tổng quan Chuẩn Báo cáo ESG tại Việt Nam

| Chuẩn | Cơ quan | Bắt buộc/Tự nguyện | Áp dụng |
|-------|---------|-------------------|---------|
| SSC Guideline 2023 | UBCK Nhà nước (SSC) | Bắt buộc với công ty niêm yết | Từ niên độ 2024 |
| GRI Standards 2021 | Global Reporting Initiative | Tự nguyện (best practice) | Toàn cầu |
| TCFD | Task Force on Climate-related Financial Disclosures | Khuyến nghị | Toàn cầu |
| SASB | Sustainability Accounting Standards Board | Tự nguyện | Theo ngành |
| SDG Mapping | UN Sustainable Development Goals | Tự nguyện | Toàn cầu |

---

## 2. Pillar E — Environmental (Môi trường)

### E1: Khí nhà kính (Greenhouse Gas Emissions)

| KPI | Định nghĩa | Đơn vị | Nguồn dữ liệu | GRI Ref |
|-----|-----------|--------|--------------|---------|
| E1.1 Scope 1 Emissions | Phát thải trực tiếp từ nguồn doanh nghiệp sở hữu/kiểm soát | tCO2e/năm | Hóa đơn nhiên liệu, kiểm kê nội bộ | GRI 305-1 |
| E1.2 Scope 2 Emissions | Phát thải gián tiếp từ điện/nhiệt mua ngoài | tCO2e/năm | Hóa đơn điện EVN | GRI 305-2 |
| E1.3 Scope 3 Emissions | Phát thải toàn chuỗi giá trị (di chuyển, chuỗi cung ứng...) | tCO2e/năm | Ước tính, supplier data | GRI 305-3 |
| E1.4 Emissions Intensity | Phát thải / doanh thu hoặc sản lượng | tCO2e/tỷ VND | Tính từ E1.1+E1.2 | GRI 305-4 |
| E1.5 Emissions Reduction Target | % giảm phát thải so với base year | % | Cam kết quản trị | GRI 305-5 |

### E2: Năng lượng (Energy)

| KPI | Định nghĩa | Đơn vị | GRI Ref |
|-----|-----------|--------|---------|
| E2.1 Total Energy Consumption | Tổng tiêu thụ năng lượng (điện + nhiên liệu) | GJ/năm | GRI 302-1 |
| E2.2 Renewable Energy Share | Tỷ lệ năng lượng tái tạo / tổng năng lượng | % | GRI 302-1 |
| E2.3 Energy Intensity | Năng lượng / doanh thu | GJ/tỷ VND | GRI 302-3 |
| E2.4 Energy Reduction Target | % tiết kiệm năng lượng mục tiêu | % | GRI 302-4 |

### E3: Nước (Water)

| KPI | Định nghĩa | Đơn vị | GRI Ref |
|-----|-----------|--------|---------|
| E3.1 Water Withdrawal | Lượng nước khai thác (nước máy, nước ngầm, nước mưa) | m³/năm | GRI 303-3 |
| E3.2 Water Recycled | Lượng nước tái sử dụng / tuần hoàn | m³/năm | GRI 303-3 |
| E3.3 Water Intensity | Nước / doanh thu | m³/tỷ VND | — |

### E4: Chất thải (Waste)

| KPI | Định nghĩa | Đơn vị | GRI Ref |
|-----|-----------|--------|---------|
| E4.1 Total Waste Generated | Tổng chất thải phát sinh | tấn/năm | GRI 306-3 |
| E4.2 Hazardous Waste | Chất thải nguy hại | tấn/năm | GRI 306-3 |
| E4.3 Waste Diversion Rate | % chất thải tái chế/tái sử dụng / tổng | % | GRI 306-4/5 |

---

## 3. Pillar S — Social (Xã hội)

### S1: Lao động và Nhân quyền

| KPI | Định nghĩa | Đơn vị | GRI Ref |
|-----|-----------|--------|---------|
| S1.1 Total Employees | Tổng số nhân viên | người | GRI 2-7 |
| S1.2 Gender Ratio | Tỷ lệ nữ / tổng nhân viên | % | GRI 405-1 |
| S1.3 Women in Management | Tỷ lệ phụ nữ trong ban lãnh đạo | % | GRI 405-1 |
| S1.4 Employee Turnover Rate | Tỷ lệ nghỉ việc hàng năm | % | GRI 401-1 |
| S1.5 Training Hours per Employee | Số giờ đào tạo trung bình / nhân viên / năm | giờ | GRI 404-1 |
| S1.6 Lost Time Injury Rate (LTIR) | Tần suất tai nạn gây mất thời gian lao động | per 200,000 hrs | GRI 403-9 |
| S1.7 Fatalities | Số ca tử vong liên quan công việc | ca | GRI 403-9 |
| S1.8 Living Wage Compliance | Tỷ lệ nhân viên nhận lương >= mức lương đủ sống tối thiểu | % | GRI 202-1 |

### S2: Cộng đồng và Chuỗi cung ứng

| KPI | Định nghĩa | Đơn vị | GRI Ref |
|-----|-----------|--------|---------|
| S2.1 Community Investment | Tổng chi CSR / đầu tư cộng đồng | tỷ VND/năm | GRI 413-1 |
| S2.2 Suppliers ESG Screened | % nhà cung cấp được đánh giá ESG | % | GRI 308-1 |
| S2.3 Human Rights Incidents | Số sự kiện vi phạm nhân quyền được ghi nhận | ca | GRI 411-1 |

### S3: Sản phẩm và Khách hàng

| KPI | Định nghĩa | Đơn vị | GRI Ref |
|-----|-----------|--------|---------|
| S3.1 Customer Complaints | Số khiếu nại khách hàng / 1000 KH | ca/1000KH | GRI 417 |
| S3.2 Data Privacy Incidents | Số sự kiện rò rỉ dữ liệu khách hàng | ca | GRI 418-1 |
| S3.3 Product Safety Recalls | Số lần thu hồi sản phẩm | lần | — |

---

## 4. Pillar G — Governance (Quản trị)

### G1: Cấu trúc Hội đồng Quản trị

| KPI | Định nghĩa | Đơn vị | GRI Ref |
|-----|-----------|--------|---------|
| G1.1 Board Independence | Tỷ lệ thành viên HĐQT độc lập | % | GRI 2-9 |
| G1.2 Board Gender Diversity | Tỷ lệ phụ nữ trong HĐQT | % | GRI 405-1 |
| G1.3 Avg Board Tenure | Nhiệm kỳ trung bình thành viên HĐQT | năm | GRI 2-9 |
| G1.4 Board Meeting Frequency | Số cuộc họp HĐQT / năm | cuộc | GRI 2-9 |
| G1.5 CEO-Chair Separation | CEO và Chủ tịch HĐQT có phải 2 người khác nhau | bool | GRI 2-9 |

### G2: Kiểm soát và Tuân thủ

| KPI | Định nghĩa | Đơn vị | GRI Ref |
|-----|-----------|--------|---------|
| G2.1 Anti-Corruption Training | % nhân viên được đào tạo phòng chống tham nhũng | % | GRI 205-2 |
| G2.2 Confirmed Corruption Incidents | Số vụ tham nhũng được xác nhận | vụ | GRI 205-3 |
| G2.3 Whistleblower Cases | Số vụ báo cáo qua kênh tố giác | vụ/năm | GRI 2-26 |
| G2.4 External Audit Independence | Kiểm toán viên độc lập không phải công ty liên quan | bool | — |
| G2.5 ESG Report Assurance | Báo cáo ESG có kiểm định độc lập (assurance) | bool | GRI 2-5 |

### G3: Thù lao và Cổ đông

| KPI | Định nghĩa | Đơn vị | GRI Ref |
|-----|-----------|--------|---------|
| G3.1 CEO Pay Ratio | Lương CEO / lương trung bình nhân viên | lần | GRI 2-21 |
| G3.2 ESG-Linked Executive Pay | % thù lao Ban điều hành gắn với mục tiêu ESG | % | — |
| G3.3 AGM Attendance Rate | Tỷ lệ cổ phần tham dự ĐHCĐ thường niên | % | — |

---

## 5. TCFD Disclosure Framework

categories:
  governance:
    - "HĐQT giám sát rủi ro và cơ hội liên quan khí hậu như thế nào?"
    - "Ban điều hành quản lý rủi ro khí hậu như thế nào?"
  strategy:
    - "Rủi ro và cơ hội khí hậu tác động đến chiến lược kinh doanh?"
    - "Kịch bản khí hậu 2°C và 4°C ảnh hưởng gì đến doanh nghiệp?"
  risk_management:
    - "Quy trình xác định, đánh giá rủi ro khí hậu?"
    - "Rủi ro khí hậu được tích hợp vào quản lý rủi ro tổng thể?"
  metrics_and_targets:
    - "Chỉ số đo rủi ro khí hậu (Scope 1/2/3 emissions)?"
    - "Mục tiêu giảm phát thải và tiến độ thực hiện?"

---

## 6. AI Agent Prompt Template

```
SYSTEM:
Bạn là AI agent hỗ trợ lập báo cáo ESG cho doanh nghiệp Việt Nam.
Áp dụng chuẩn: SSC Guideline 2023 (bắt buộc niêm yết), GRI Standards 2021, TCFD.
Khi nhận dữ liệu doanh nghiệp, hãy:
1. Xác định KPI nào đã có data, KPI nào còn thiếu
2. Tính toán các chỉ số phái sinh (intensity = absolute/revenue)
3. So sánh với benchmark ngành (nếu có)
4. Xác định gap theo yêu cầu SSC mandatory vs optional
5. Gợi ý cải thiện cho năm tiếp theo
Output JSON: { "pillar_scores": {E,S,G}, "missing_kpis": [], "ssc_compliance": bool, "recommendations": [] }
```
"""

CONTENT_CRYPTO = """\
# Quy định & Protocols Crypto Việt Nam — Vietnam Crypto Regulation & DeFi Protocols

> Version 1.0 — Viet Dataverse Team
> Context cho AI agent tư vấn về crypto tại Việt Nam: pháp lý, DeFi protocols phổ biến,
> rủi ro, và yêu cầu AML/KYC cho sàn giao dịch.

---

## 1. Khung Pháp lý Crypto tại Việt Nam (2024–2025)

### Tình trạng pháp lý hiện tại

| Khía cạnh | Quy định | Ghi chú |
|-----------|---------|---------|
| Tài sản kỹ thuật số là tiền tệ? | KHÔNG | NHNN cấm dùng crypto làm phương tiện thanh toán |
| Tài sản kỹ thuật số là hàng hoá? | CHƯA RÕ RÀNG | Đang dự thảo khung pháp lý |
| Sàn giao dịch crypto được phép? | CHƯA CÓ GIẤY PHÉP CHÍNH THỨC | Không bị cấm nhưng chưa được cấp phép |
| Thuế thu nhập từ crypto? | CÓ | Theo Luật Thuế TNCN; khai báo tự nguyện |
| Sở hữu cá nhân? | ĐƯỢC PHÉP | Không bị cấm |
| Mining? | ĐƯỢC PHÉP | Điện tiêu thụ lớn — không được khuyến khích |

### Văn bản pháp lý liên quan

- **Nghị định 52/2024/NĐ-CP** (thay thế 101/2012): Quản lý hoạt động thanh toán — khẳng định crypto KHÔNG phải phương tiện thanh toán hợp pháp
- **Luật Các tổ chức tín dụng 2024**: Không đề cập tài sản số
- **Dự thảo Luật Tài sản số** (2024–2025): Đang soạn thảo, dự kiến trình Quốc hội 2025
  - Phân loại: tài sản mã hoá (crypto-asset) vs token chứng khoán (security token)
  - Yêu cầu: đăng ký sàn, AML/KYC, báo cáo giao dịch lớn
- **Thông tư 09/2023/TT-NHNN**: Quản lý ngoại hối — chuyển tiền qua crypto ra nước ngoài vi phạm quy định ngoại hối

### Ngưỡng giao dịch đáng chú ý (AML)

- Giao dịch tiền mặt > 100 triệu VND: báo cáo theo Nghị định 19/2023/NĐ-CP về phòng chống rửa tiền
- Giao dịch đáng ngờ: sàn có trách nhiệm báo cáo NHNN (nếu được cấp phép)
- Crypto-to-fiat chuyển đổi > tương đương 300 triệu VND: best practice báo cáo

---

## 2. Top 5 DeFi Protocols Phổ biến tại Việt Nam

### Protocol 1: PancakeSwap (BSC)

```
Chain: BNB Smart Chain (BSC)
Type: DEX (Decentralized Exchange) — Automated Market Maker
TVL (2024): ~$1.2B
Token: CAKE
Fee: 0.25% per swap (0.17% LP, 0.08% buyback)
Vietnam usage: Phổ biến nhất — BSC gas fee thấp, quen thuộc với retail
Risk indicators:
  - Smart contract risk: audit by CertiK
  - Rug pull risk: low (established protocol)
  - Impermanent loss: medium-high on volatile pairs
  - Regulatory: DEX — no KYC required, AML exposure
```

### Protocol 2: GMX (Arbitrum/Avalanche)

```
Chain: Arbitrum, Avalanche
Type: Decentralized Perpetual Exchange
TVL (2024): ~$500M
Token: GMX
Feature: Zero-price-impact trades, up to 50x leverage
Vietnam usage: Trader cá nhân ưa đòn bẩy cao
Risk indicators:
  - Smart contract risk: multiple audits
  - Liquidation risk: HIGH — leverage trading
  - Oracle manipulation risk: uses Chainlink + custom oracle
  - Regulatory: high-risk product (leverage) — no KYC
```

### Protocol 3: Curve Finance (Ethereum/Multi-chain)

```
Chain: Ethereum, Arbitrum, Optimism, Polygon, BNB Chain
Type: DEX optimised for stablecoin swaps
TVL (2024): ~$1.8B
Token: CRV
Fee: 0.04% for stablecoin pools
Vietnam usage: Institutional và treasury management
Risk indicators:
  - Smart contract risk: battle-tested, audited
  - Depeg risk: if stablecoin in pool loses peg
  - veTokenomics complexity: lockup risk
```

### Protocol 4: Aave (Multi-chain)

```
Chain: Ethereum, Polygon, Arbitrum, Avalanche, Optimism, BNB Chain
Type: Lending/Borrowing Protocol
TVL (2024): ~$15B
Token: AAVE
Feature: Supply assets to earn interest; borrow against collateral
Vietnam usage: Yield farming, stablecoin borrowing
Key parameters (v3):
  - LTV (Loan-to-Value): 50–80% depending on asset
  - Liquidation threshold: 65–85%
  - Health Factor < 1 → liquidation triggered
Risk indicators:
  - Smart contract risk: high audit coverage
  - Liquidation risk: cascading if collateral crashes
  - Governance risk: protocol parameter changes via AAVE token vote
```

### Protocol 5: Lido Finance (Ethereum)

```
Chain: Ethereum
Type: Liquid Staking
TVL (2024): ~$30B (largest DeFi protocol)
Token: stETH (liquid representation of staked ETH)
APR: ~3.5–4% ETH staking reward
Vietnam usage: ETH holders muốn vừa earn yield vừa giữ thanh khoản
Risk indicators:
  - Smart contract risk: audited, battle-tested
  - Slashing risk: validator misbehaviour
  - Depeg risk: stETH/ETH peg has held but not guaranteed
  - Concentration risk: Lido controls ~30% ETH stake
```

---

## 3. Rủi ro Chính trong Thị trường Crypto (Risk Indicators)

### Market Risks

| Chỉ báo | Mô tả | Ngưỡng cảnh báo |
|---------|-------|----------------|
| Crypto Fear & Greed Index | Tâm lý thị trường 0–100 | <20: Extreme Fear (cơ hội mua); >80: Extreme Greed (cẩn thận) |
| BTC Dominance | % vốn hoá BTC / tổng crypto | >60%: altcoin risk off; <40%: altseason |
| Stablecoin Market Cap | Tổng vốn hoá stablecoin | Tăng nhanh = dòng tiền vào chờ mua |
| Exchange Net Flow | Dòng tiền vào/ra sàn tập trung | Vào nhiều = áp lực bán; Ra nhiều = hodl |
| Open Interest (Futures) | Tổng hợp đồng tương lai mở | OI tăng + giá tăng = momentum; OI tăng + giá giảm = shorts |

### On-chain Risk Metrics

| Chỉ báo | Ý nghĩa | Ngưỡng |
|---------|---------|--------|
| NUPL (Net Unrealized P&L) | Lợi nhuận chưa thực hiện toàn thị trường | >0.75: euphoria/sell; <0: capitulation/buy |
| MVRV Ratio | Market Cap / Realized Cap | >3.5: overvalued; <1: undervalued |
| Puell Multiple | Daily issuance USD / 365MA | >4: sell zone; <0.5: buy zone (BTC) |
| Stablecoin Supply Ratio | Stablecoin / BTC Market Cap | Cao = dry powder available |

### DeFi-Specific Risks

- **Rug Pull:** Developer rút thanh khoản đột ngột
  - Dấu hiệu: anonymous team, no audit, locked LP dưới 6 tháng
- **Flash Loan Attack:** Vay không tài sản thế chấp để thao túng price oracle
- **Re-entrancy:** Lỗ hổng smart contract cho phép gọi hàm lặp
- **Bridge Hack:** Tấn công cross-chain bridge (TVL cao = mục tiêu lớn)

---

## 4. AML/KYC Compliance cho Sàn Crypto VN (Best Practice)

### KYC Tiers (theo quy mô giao dịch)

| Tier | Hạn mức | Yêu cầu KYC |
|------|---------|-------------|
| Tier 1 | < 10 triệu VND/ngày | Số điện thoại, email verified |
| Tier 2 | 10–100 triệu VND/ngày | CMND/CCCD + selfie |
| Tier 3 | > 100 triệu VND/ngày | CCCD + proof of income + địa chỉ |
| VIP | > 1 tỷ VND/tháng | Enhanced Due Diligence (EDD) |

### Transaction Monitoring Rules

```
RULE 1: Flag giao dịch > 300 triệu VND trong 24h từ 1 địa chỉ
RULE 2: Layering pattern: N giao dịch nhỏ <10M trong 1h → aggregated flag
RULE 3: Mixer/Tumbler interaction: Tornado Cash, Chipmixer → auto block
RULE 4: High-risk jurisdiction: địa chỉ liên kết Iran, CHDCND Triều Tiên, Cuba → block
RULE 5: Politically Exposed Persons (PEP) list check khi onboard Tier 3+
```

### Báo cáo giao dịch đáng ngờ (Suspicious Transaction Report — STR)

- Gửi tới: Cục Phòng chống rửa tiền — NHNN (amlcft.sbv.gov.vn)
- Thời hạn: trong vòng 3 ngày làm việc kể từ khi phát hiện
- Nội dung: tên/CCCD người dùng, hash giao dịch, ví address, số tiền, mô tả hành vi

---

## 5. AI Agent Prompt Template

```
SYSTEM:
Bạn là AI agent tư vấn crypto tuân thủ pháp lý VN và quản lý rủi ro DeFi.
Quy tắc:
1. Luôn nhắc nhở: crypto KHÔNG phải phương tiện thanh toán hợp pháp tại VN (Nghị định 52/2024)
2. Khi phân tích DeFi protocol: kiểm tra TVL, audit status, team reputation, lock period
3. Khi đánh giá rủi ro: tính toán NUPL, MVRV, BTC dominance trước khi đưa khuyến nghị
4. Với giao dịch lớn (>300M VND): nhắc nghĩa vụ khai báo thuế TNCN và rủi ro pháp lý ngoại hối
5. KHÔNG tư vấn cách né thuế hoặc rửa tiền — từ chối và ghi log yêu cầu này
Output format: { "legal_status": str, "risk_level": "low|medium|high|critical",
                 "key_risks": [], "recommendations": [], "compliance_notes": [] }
```
"""

# ---------------------------------------------------------------------------
# Product definitions
# ---------------------------------------------------------------------------

MIME_TYPES = {
    "json": "application/json",
    "md":   "text/markdown",
    "yaml": "application/yaml",
}

PRODUCTS = [
    {
        "slug":          "tt200-chart-of-accounts-vn",
        "title":         "Hệ thống Tài khoản Kế toán theo TT 200/2014/TT-BTC",
        "description":   (
            "Chart of accounts đầy đủ theo Thông tư 200/2014/TT-BTC của Việt Nam, "
            "format JSON ready cho AI agent. Bao gồm 9 loại tài khoản: tài sản, "
            "nợ phải trả, vốn chủ sở hữu, doanh thu, chi phí... "
            "Tích hợp dễ dàng với LangChain, Claude SDK cho agent kế toán doanh nghiệp."
        ),
        "category":      "accounting",
        "format":        "json",
        "frameworks":    "claude, langchain, crewai",
        "price_credits": 0,
        "preview_pct":   25,
        "version":       "1.0.0",
        "content":       CONTENT_ACCOUNTING,
        "filename":      "tt200-chart-of-accounts.json",
    },
    {
        "slug":          "vn-stock-trader-glossary",
        "title":         "Từ điển Trader Chứng khoán Việt Nam",
        "description":   (
            "Từ điển 200+ thuật ngữ trading VN/EN dành cho AI agent phân tích kỹ thuật "
            "và cơ bản. Bao gồm thuật ngữ VN30, HNX30, biểu đồ nến, các chỉ báo "
            "MACD/RSI/Bollinger. Tối ưu cho prompt engineering với Claude và LangChain."
        ),
        "category":      "trading",
        "format":        "md",
        "frameworks":    "claude, langchain",
        "price_credits": 0,
        "preview_pct":   25,
        "version":       "1.0.0",
        "content":       CONTENT_TRADING,
        "filename":      "vn-stock-trader-glossary.md",
    },
    {
        "slug":          "vn-macro-indicators-context",
        "title":         "Context Vĩ mô Việt Nam cho AI Agent",
        "description":   (
            "Tổng hợp 30+ chỉ số vĩ mô Việt Nam (CPI, GDP, IIP, PPI, FX, lãi suất SBV) "
            "với giải thích cách đọc, nguồn dữ liệu chính thống (GSO, SBV), tần suất "
            "cập nhật, và ý nghĩa kinh tế. Dùng làm system prompt cho Claude/GPT agent "
            "phân tích thị trường VN."
        ),
        "category":      "macro",
        "format":        "md",
        "frameworks":    "claude, langchain, crewai",
        "price_credits": 50,
        "preview_pct":   25,
        "version":       "1.0.0",
        "content":       CONTENT_MACRO,
        "filename":      "vn-macro-indicators-context.md",
    },
    {
        "slug":          "vn-banking-regulation-schema",
        "title":         "Schema Tuân thủ Quy định Ngân hàng VN",
        "description":   (
            "Schema JSON cho AI compliance agent kiểm tra tuân thủ quy định ngân hàng "
            "Việt Nam: Thông tư 02/2023 phân loại nợ, TT 13/2018 tỷ lệ an toàn vốn (CAR), "
            "TT 22/2019 quản lý rủi ro. Bao gồm decision tree và threshold values."
        ),
        "category":      "policy",
        "format":        "json",
        "frameworks":    "claude, langchain, crewai",
        "price_credits": 100,
        "preview_pct":   25,
        "version":       "1.0.0",
        "content":       CONTENT_POLICY,
        "filename":      "vn-banking-regulation-schema.json",
    },
    {
        "slug":          "vn-finance-sentiment-lexicon",
        "title":         "Lexicon Sentiment Tài chính Tiếng Việt",
        "description":   (
            "Bộ từ vựng 500+ từ tiếng Việt phân loại sentiment cho tài chính: "
            "positive (tăng trưởng, lãi, hồi phục...), negative (sụp đổ, lỗ, suy thoái...), "
            "neutral. Optimized cho NLP và LLM-based sentiment analysis trên dữ liệu "
            "social media VN."
        ),
        "category":      "sentiment",
        "format":        "json",
        "frameworks":    "claude, langchain",
        "price_credits": 0,
        "preview_pct":   25,
        "version":       "1.0.0",
        "content":       CONTENT_SENTIMENT,
        "filename":      "vn-finance-sentiment-lexicon.json",
    },
    {
        "slug":          "vn-credit-risk-scoring-schema",
        "title":         "Schema Chấm điểm Tín dụng Việt Nam",
        "description":   (
            "Schema YAML cho AI agent đánh giá rủi ro tín dụng khách hàng doanh nghiệp VN. "
            "Tích hợp các yếu tố: ngành nghề, dòng tiền, đòn bẩy, lịch sử tín dụng CIC. "
            "Output: rating A–E với weights và thresholds rõ ràng."
        ),
        "category":      "risk-management",
        "format":        "yaml",
        "frameworks":    "claude, langchain, crewai",
        "price_credits": 150,
        "preview_pct":   25,
        "version":       "1.0.0",
        "content":       CONTENT_RISK,
        "filename":      "vn-credit-risk-scoring-schema.yaml",
    },
    {
        "slug":          "vn-esg-reporting-framework",
        "title":         "Framework Báo cáo ESG Việt Nam",
        "description":   (
            "Framework báo cáo ESG cho doanh nghiệp Việt Nam theo SSC Vietnam Guideline 2023, "
            "GRI Standards, TCFD. Bao gồm 60+ KPI environmental/social/governance với "
            "metric definitions, data sources, và compliance mapping."
        ),
        "category":      "esg",
        "format":        "md",
        "frameworks":    "claude, langchain",
        "price_credits": 80,
        "preview_pct":   25,
        "version":       "1.0.0",
        "content":       CONTENT_ESG,
        "filename":      "vn-esg-reporting-framework.md",
    },
    {
        "slug":          "vn-crypto-regulation-protocols",
        "title":         "Quy định & Protocols Crypto Việt Nam",
        "description":   (
            "Tổng hợp quy định pháp lý crypto VN (chưa được công nhận như tiền tệ, "
            "status as commodity), top 5 protocols DeFi phổ biến tại VN "
            "(PancakeSwap, GMX, Curve, Aave, Lido), risk indicators, "
            "AML/KYC compliance cho exchange VN."
        ),
        "category":      "crypto",
        "format":        "md",
        "frameworks":    "claude, langchain, crewai",
        "price_credits": 200,
        "preview_pct":   25,
        "version":       "1.0.0",
        "content":       CONTENT_CRYPTO,
        "filename":      "vn-crypto-regulation-protocols.md",
    },
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _r2_upload(content_bytes: bytes, r2_key: str, fmt: str) -> str | None:
    """
    Upload content_bytes to R2.  Returns the r2_key on success, None on failure.
    Prints a clear warning if R2 env vars are not configured.
    """
    content_type = MIME_TYPES.get(fmt, "application/octet-stream")
    try:
        upload_file(content_bytes, r2_key, content_type)
        return r2_key
    except ValueError as exc:
        # R2 env vars missing — non-fatal for seeding
        print(f"  [warn] R2 not configured: {exc}")
        print("         Set R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY,")
        print("         R2_BUCKET_KNOWLEDGE to enable file uploads.")
        return None
    except Exception as exc:
        print(f"  [warn] R2 upload failed: {exc}")
        return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    engine = create_engine(DB_URL)

    # ------------------------------------------------------------------
    # Step 1: ensure Viet Dataverse team seller profile exists
    # ------------------------------------------------------------------
    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT id FROM seller_profiles WHERE user_id = :u"),
            {"u": VND_SELLER_USER_ID},
        ).first()

        if row:
            seller_id = row[0]
            print(f"Found existing VND team seller: id={seller_id}")
        else:
            seller_id = conn.execute(
                text("""
                    INSERT INTO seller_profiles (
                        user_id, user_email_snapshot, display_name, bio,
                        apply_status, email_verified, trust_tier,
                        tos_accepted_at, tos_version, created_at, updated_at
                    ) VALUES (
                        :u, :e, :n, :b,
                        'auto_approved', true, 'trusted',
                        NOW(), '1.0', NOW(), NOW()
                    ) RETURNING id
                """),
                {
                    "u": VND_SELLER_USER_ID,
                    "e": VND_SELLER_EMAIL,
                    "n": VND_SELLER_DISPLAY_NAME,
                    "b": VND_SELLER_BIO,
                },
            ).scalar()
            print(f"Created VND team seller profile: id={seller_id}")

    # ------------------------------------------------------------------
    # Step 2: seed each product
    # ------------------------------------------------------------------
    seeded = 0
    skipped = 0
    scan_json = json.dumps({"passed": True, "checks": 4, "scanner": "seed_mock"})

    for p in PRODUCTS:
        slug = p["slug"]

        # Idempotency check
        with engine.connect() as conn:
            existing = conn.execute(
                text("SELECT id FROM knowledge_products WHERE slug = :s"),
                {"s": slug},
            ).first()

        if existing:
            print(f"  [skip] {slug} already exists (id={existing[0]})")
            skipped += 1
            continue

        # Prepare bytes and hashes
        content_bytes = p["content"].encode("utf-8")
        sha256 = compute_sha256(content_bytes)
        size_bytes = len(content_bytes)

        # Upload to R2 (non-fatal if R2 not configured)
        r2_key = f"products/{slug}/v{p['version']}/{p['filename']}"
        stored_r2_key = _r2_upload(content_bytes, r2_key, p["format"])

        # Insert product row
        with engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO knowledge_products (
                        seller_id, slug, title, description,
                        category, format, frameworks,
                        price_credits, preview_pct, version,
                        file_r2_key, file_size_bytes, file_sha256,
                        scan_status, scan_result_json,
                        status, is_vd_owned,
                        download_count, report_count,
                        published_at, created_at, updated_at
                    ) VALUES (
                        :seller_id, :slug, :title, :desc,
                        :category, :fmt, :frameworks,
                        :price, :preview, :version,
                        :r2_key, :size, :sha,
                        'clean', CAST(:scan AS JSONB),
                        'published', true,
                        0, 0,
                        NOW(), NOW(), NOW()
                    )
                """),
                {
                    "seller_id": seller_id,
                    "slug":      slug,
                    "title":     p["title"],
                    "desc":      p["description"],
                    "category":  p["category"],
                    "fmt":       p["format"],
                    "frameworks": p["frameworks"],
                    "price":     p["price_credits"],
                    "preview":   p["preview_pct"],
                    "version":   p["version"],
                    "r2_key":    stored_r2_key,
                    "size":      size_bytes,
                    "sha":       sha256,
                    "scan":      scan_json,
                },
            )

        r2_status = "R2 uploaded" if stored_r2_key else "R2 skipped (NULL)"
        print(
            f"  [ok] {slug}"
            f" — {p['category']}, {p['price_credits']} credits"
            f" — {size_bytes:,} bytes, {r2_status}"
        )
        seeded += 1

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print(f"\nDone. Seeded {seeded}/{len(PRODUCTS)} products, skipped {skipped}.")
    if skipped == len(PRODUCTS):
        print("All products already present — database unchanged.")
    if seeded > 0:
        print("\nVerify:")
        print("  SELECT slug, category, price_credits, status")
        print("  FROM knowledge_products WHERE is_vd_owned=true ORDER BY id;")


if __name__ == "__main__":
    main()
