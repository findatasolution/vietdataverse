"""
Gold Market Analysis Agent
Automatically generates daily gold market analysis using Gemini AI
Fetches data from Neon PostgreSQL and generates structured Vietnamese analysis
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
import google.generativeai as genai
from pathlib import Path

# =========================================================
# ENV
# =========================================================
root_dir = Path(__file__).resolve().parent.parent.parent
load_dotenv(dotenv_path=root_dir / '.env')

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if not GEMINI_API_KEY:
    raise ValueError("Missing GEMINI_API_KEY")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')

GLOBAL_INDICATOR_DB = os.getenv('GLOBAL_INDICATOR_DB')
ARGUS_FINTEL_DB = os.getenv('ARGUS_FINTEL_DB')
CRAWLING_BOT_DB = os.getenv('CRAWLING_BOT_DB')

global_indicator_engine = create_engine(GLOBAL_INDICATOR_DB)
argus_fintel_engine = create_engine(ARGUS_FINTEL_DB)
crawling_bot_engine = create_engine(CRAWLING_BOT_DB)

# =========================================================
# FETCH
# =========================================================
def fetch_global_macro_data(days=7):
    q = text("""
        SELECT date, gold_price, silver_price, nasdaq_price
        FROM global_macro
        ORDER BY date DESC
        LIMIT :days
    """)
    with global_indicator_engine.connect() as c:
        rows = c.execute(q, {"days": days}).fetchall()
    return [
        {
            "date": r[0],
            "gold_price": float(r[1]),
            "silver_price": float(r[2]),
            "nasdaq_price": float(r[3]),
        }
        for r in rows
    ] if rows else []

def fetch_vietnam_gold_data(days=7):
    q = text("""
        SELECT date, buy_price, sell_price
        FROM vn_gold_24h_hist
        WHERE type='DOJI HN'
        ORDER BY date DESC
        LIMIT :days
    """)
    with crawling_bot_engine.connect() as c:
        rows = c.execute(q, {"days": days}).fetchall()
    return [
        {"date": r[0], "buy_price": float(r[1]), "sell_price": float(r[2])}
        for r in rows
    ] if rows else []

def fetch_vietnam_silver_data(days=7):
    q = text("""
        SELECT date, buy_price, sell_price
        FROM vn_silver_phuquy_hist
        ORDER BY date DESC
        LIMIT :days
    """)
    with crawling_bot_engine.connect() as c:
        rows = c.execute(q, {"days": days}).fetchall()
    return [
        {"date": r[0], "buy_price": float(r[1]), "sell_price": float(r[2])}
        for r in rows
    ] if rows else []

# =========================================================
# PROMPT
# =========================================================
def generate_analysis_prompt(global_data, vietnam_data, vietnam_silver_data):
    vn_now = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh"))

    # ---- INIT SAFE DEFAULTS (QUAN TRỌNG) ----
    vn_gold_change = 0.0
    vn_silver_change = 0.0

    gold_change = silver_change = nasdaq_change = 0.0

    if len(global_data) >= 2:
        gold_change = (global_data[0]["gold_price"] - global_data[-1]["gold_price"]) / global_data[-1]["gold_price"] * 100
        silver_change = (global_data[0]["silver_price"] - global_data[-1]["silver_price"]) / global_data[-1]["silver_price"] * 100
        nasdaq_change = (global_data[0]["nasdaq_price"] - global_data[-1]["nasdaq_price"]) / global_data[-1]["nasdaq_price"] * 100

    if len(vietnam_data) >= 2:
        vn_gold_change = (vietnam_data[0]["buy_price"] - vietnam_data[-1]["buy_price"]) / vietnam_data[-1]["buy_price"] * 100

    if len(vietnam_silver_data) >= 2:
        vn_silver_change = (
            (vietnam_silver_data[0]["buy_price"] - vietnam_silver_data[-1]["buy_price"])
            / vietnam_silver_data[-1]["buy_price"] * 100
        )

    latest_global = global_data[0]
    latest_gold = vietnam_data[0]
    latest_silver = vietnam_silver_data[0]

    return f"""
**DỮ LIỆU THỊ TRƯỜNG VIỆT NAM (7 ngày):**
- Giá vàng thay đổi: {vn_gold_change:+.2f}%
- Giá bạc thay đổi: {vn_silver_change:+.2f}%
"""

# =========================================================
# MAIN
# =========================================================
def generate_analysis():
    global_data = fetch_global_macro_data()
    vietnam_data = fetch_vietnam_gold_data()
    vietnam_silver_data = fetch_vietnam_silver_data()

    if not global_data or not vietnam_data or not vietnam_silver_data:
        raise RuntimeError("Missing market data")

    prompt = generate_analysis_prompt(global_data, vietnam_data, vietnam_silver_data)
    response = model.generate_content(prompt)

    return response.text

def main():
    try:
        generate_analysis()
        print("✅ Gold analysis completed")
        return True
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        return False

if __name__ == "__main__":
    sys.exit(0 if main() else 1)
