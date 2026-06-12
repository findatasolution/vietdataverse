"""
Re-upload 5 VD knowledge packs lên R2 và cập nhật DB (UPSERT by slug).
Chạy: python be/migrations/update_vd_knowledge_packs.py

Dùng khi nội dung pack thay đổi — tự động cập nhật file_r2_key, file_size, sha256, updated_at.
"""
import hashlib
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / ".env")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, text

PACKS_DIR = Path(__file__).resolve().parents[2] / "content" / "knowledge_packs"
VD_SELLER_ID = 6

PACKS = [
    {
        "file":          "01_vn_macro_decoder.md",
        "title":         "Vietnam Macro Decoder",
        "slug":          "vn-macro-decoder-v1",
        "description":   "Hướng dẫn đọc và giải mã các chỉ số kinh tế vĩ mô Việt Nam cho AI agent: CPI, lãi suất SBV, tỷ giá USD/VND, GDP. Kèm mối quan hệ giữa các chỉ số và prompt snippet sẵn dùng.",
        "category":      "macro",
        "format":        "md",
        "price_credits": 0,
        "preview_pct":   30,
        "frameworks":    "claude,cursor,n8n",
    },
    {
        "file":          "02_vn_gold_market_playbook.md",
        "title":         "Vietnam Gold Market Playbook",
        "slug":          "vn-gold-market-playbook-v1",
        "description":   "Phân tích thị trường vàng Việt Nam cho AI agent: chênh lệch premium SJC vs quốc tế, công thức quy đổi, tính mùa vụ, các yếu tố tác động. Dữ liệu từ Viet Dataverse API.",
        "category":      "trading",
        "format":        "md",
        "price_credits": 0,
        "preview_pct":   25,
        "frameworks":    "claude,cursor,openai",
    },
    {
        "file":          "03_vn_bank_termdepo_guide.md",
        "title":         "Vietnam Bank Term Deposit Guide",
        "slug":          "vn-termdepo-guide-v1",
        "description":   "Hướng dẫn toàn diện về lãi suất tiết kiệm ngân hàng VN: chu kỳ lãi suất, cách tính lãi suất thực, bảng so sánh danh nghĩa vs thực, bảo hiểm tiền gửi 125 triệu, chiến lược gửi theo từng pha SBV.",
        "category":      "macro",
        "format":        "md",
        "price_credits": 0,
        "preview_pct":   25,
        "frameworks":    "claude,n8n",
    },
    {
        "file":          "04_vn30_sector_rotation.md",
        "title":         "VN30 Sector Rotation Playbook",
        "slug":          "vn30-sector-rotation-v1",
        "description":   "Chiến lược rotation ngành theo chu kỳ kinh tế VN: tác động lãi suất SBV, tỷ giá, giá dầu lên từng nhóm ngành trong VN30. Kèm prompt snippet cho agent phân tích danh mục.",
        "category":      "trading",
        "format":        "md",
        "price_credits": 0,
        "preview_pct":   25,
        "frameworks":    "claude,cursor,openai",
    },
    {
        "file":          "05_vn_data_sources_for_agents.md",
        "title":         "Vietnam Financial Data Sources for AI Agents",
        "slug":          "vn-data-sources-agents-v1",
        "description":   "Bản đồ đầy đủ nguồn dữ liệu tài chính VN: Viet Dataverse API, SBV, GSO, TCBS, DNSE, Yahoo Finance, FRED. Kèm script Python sẵn chạy và kiến trúc agent nên dùng.",
        "category":      "macro",
        "format":        "md",
        "price_credits": 0,
        "preview_pct":   30,
        "frameworks":    "claude,cursor,n8n,openai",
    },
    {
        "file":          "06_vn_fx_rate_playbook.md",
        "title":         "Vietnam FX Rate Playbook",
        "slug":          "vn-fx-rate-playbook-v1",
        "description":   "Cơ chế tỷ giá thả nổi có quản lý của VN, biên ±5%, ngưỡng can thiệp SBV, tác động ngành xuất nhập khẩu. Dữ liệu từ VCB và SBV qua Viet Dataverse API.",
        "category":      "macro",
        "format":        "md",
        "price_credits": 0,
        "preview_pct":   25,
        "frameworks":    "claude,cursor,openai",
    },
    {
        "file":          "07_sbv_monetary_policy.md",
        "title":         "SBV Monetary Policy Intelligence",
        "slug":          "sbv-monetary-policy-v1",
        "description":   "Tín hiệu chu kỳ lãi suất NHNN, timeline truyền dẫn chính sách tiền tệ, lịch sử chu kỳ 2022-2024. Hướng dẫn đọc tín hiệu cắt/tăng lãi suất sớm.",
        "category":      "macro",
        "format":        "md",
        "price_credits": 0,
        "preview_pct":   25,
        "frameworks":    "claude,n8n",
    },
    {
        "file":          "08_vn_real_estate_macro.md",
        "title":         "Vietnam Real Estate Macro Cycle",
        "slug":          "vn-real-estate-macro-v1",
        "description":   "4 pha chu kỳ BĐS VN, proxy indicators thay thế chỉ số giá chính thức, đặc thù VAS kế toán doanh thu BĐS. Phân tích VHM, NVL, VIC trong VN30.",
        "category":      "trading",
        "format":        "md",
        "price_credits": 0,
        "preview_pct":   25,
        "frameworks":    "claude,cursor",
    },
    {
        "file":          "09_vn30_stock_valuation.md",
        "title":         "VN30 Stock Valuation Framework",
        "slug":          "vn30-stock-valuation-v1",
        "description":   "Khung định giá cổ phiếu VN30: khoảng P/E thị trường, P/B, P/S theo ngành. Bẫy định giá phổ biến tại thị trường VN, NIM/NPL cho ngân hàng, NAV cho BĐS.",
        "category":      "trading",
        "format":        "md",
        "price_credits": 0,
        "preview_pct":   25,
        "frameworks":    "claude,cursor,openai",
    },
    {
        "file":          "10_commodity_impact_vn.md",
        "title":         "Commodity Markets & Vietnam Economy",
        "slug":          "commodity-impact-vn-v1",
        "description":   "Tác động hàng hóa quốc tế (dầu, thép, vàng, gạo, cà phê) lên kinh tế VN. Ma trận commodity × VN30: cổ phiếu nào hưởng lợi khi nào. Proxy tracking với Viet Dataverse API.",
        "category":      "macro",
        "format":        "md",
        "price_credits": 0,
        "preview_pct":   30,
        "frameworks":    "claude,cursor,openai",
    },
    {
        "file":          "11_vn_trade_fdi_data.md",
        "title":         "Vietnam Trade & FDI Data for Agents",
        "slug":          "vn-trade-fdi-data-v1",
        "description":   "Cấu trúc xuất nhập khẩu VN, Samsung = 35-40% tổng XK, FDI giải ngân 18-22 tỷ USD/năm. Proxy indicators thay thế API GSO/Hải quan chưa có.",
        "category":      "macro",
        "format":        "md",
        "price_credits": 0,
        "preview_pct":   25,
        "frameworks":    "claude,n8n,openai",
    },
    {
        "file":          "12_vn_corporate_financials.md",
        "title":         "Reading Vietnamese Corporate Financial Statements",
        "slug":          "vn-corporate-financials-v1",
        "description":   "Đọc BCTC VN theo VAS: khác biệt vs IFRS, NIM/NPL/CAR cho ngân hàng, D/E/NAV cho BĐS, red flags CFO âm. Hướng dẫn phân tích theo ngành.",
        "category":      "trading",
        "format":        "md",
        "price_credits": 0,
        "preview_pct":   25,
        "frameworks":    "claude,cursor",
    },
    {
        "file":          "13_vn_agri_commodities.md",
        "title":         "Vietnam Agricultural Commodities",
        "slug":          "vn-agri-commodities-v1",
        "description":   "VN = cường quốc cà phê Robusta (40% thế giới), top 3 gạo, top 1 điều nhân. Ngưỡng sinh lời nông dân, rủi ro El Niño, mùa vụ và giá quốc tế.",
        "category":      "macro",
        "format":        "md",
        "price_credits": 0,
        "preview_pct":   25,
        "frameworks":    "claude,openai",
    },
]

KM_DB_URL = os.getenv("KNOWLEDGE_MARKET_DB") or os.getenv("USER_DB")
if not KM_DB_URL:
    sys.exit("ERROR: KNOWLEDGE_MARKET_DB (or USER_DB) not set in .env")

engine = create_engine(KM_DB_URL)


def upload_to_r2(file_bytes: bytes, slug: str, fmt: str, file_hash: str) -> str | None:
    try:
        from core.r2 import upload_file
        key = f"knowledge/vd-official/{slug}-{file_hash[:8]}.{fmt}"
        upload_file(file_bytes, key, "text/markdown; charset=utf-8")
        return key
    except ValueError as e:
        print(f"  ⚠️  R2 not configured ({e}) — skipping upload")
        return None
    except Exception as e:
        print(f"  ❌ R2 upload failed: {e}")
        return None


def run():
    for pack in PACKS:
        path = PACKS_DIR / pack["file"]
        if not path.exists():
            print(f"SKIP — file not found: {path}")
            continue

        file_bytes = path.read_bytes()
        file_hash  = hashlib.sha256(file_bytes).hexdigest()
        file_size  = len(file_bytes)

        print(f"\n→ {pack['title']} ({file_size} bytes)")

        r2_key = upload_to_r2(file_bytes, pack["slug"], pack["format"], file_hash)
        print(f"  R2 key: {r2_key or 'NULL (skipped)'}")

        with engine.begin() as conn:
            existing = conn.execute(
                text("SELECT id FROM knowledge_products WHERE slug = :slug"),
                {"slug": pack["slug"]}
            ).fetchone()

            if existing:
                conn.execute(text("""
                    UPDATE knowledge_products SET
                        title             = :title,
                        description       = :description,
                        file_r2_key       = COALESCE(:r2_key, file_r2_key),
                        file_size_bytes   = :file_size,
                        file_sha256  = :file_hash,
                        updated_at        = NOW()
                    WHERE slug = :slug
                """), {
                    "title":       pack["title"],
                    "description": pack["description"],
                    "r2_key":      r2_key,
                    "file_size":   file_size,
                    "file_hash":   file_hash,
                    "slug":        pack["slug"],
                })
                print(f"  ✅ Updated id={existing[0]}")
            else:
                row = conn.execute(text("""
                    INSERT INTO knowledge_products
                        (slug, seller_id, title, description, category, format, frameworks,
                         price_credits, preview_pct, file_r2_key, file_size_bytes,
                         file_sha256, is_vd_owned, status, created_at, updated_at)
                    VALUES
                        (:slug, :seller_id, :title, :description, :category, :fmt, :frameworks,
                         :price_credits, :preview_pct, :r2_key, :file_size,
                         :file_hash, TRUE, 'approved', NOW(), NOW())
                    RETURNING id
                """), {
                    "slug":          pack["slug"],
                    "seller_id":     VD_SELLER_ID,
                    "title":         pack["title"],
                    "description":   pack["description"],
                    "category":      pack["category"],
                    "fmt":           pack["format"],
                    "frameworks":    pack["frameworks"],
                    "price_credits": pack["price_credits"],
                    "preview_pct":   pack["preview_pct"],
                    "r2_key":        r2_key,
                    "file_size":     file_size,
                    "file_hash":     file_hash,
                }).fetchone()
                print(f"  ✅ Inserted id={row[0]}")

    print("\nDone.")


if __name__ == "__main__":
    run()
