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
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
import google.generativeai as genai

# Load environment variables
load_dotenv()

# Configure Gemini AI
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if not GEMINI_API_KEY or GEMINI_API_KEY == 'your_gemini_api_key_here':
    raise ValueError("Please set GEMINI_API_KEY in .env file. Get your key from https://makersuite.google.com/app/apikey")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')

# Database connection
DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    raise ValueError("DATABASE_URL not found in .env file")

engine = create_engine(DATABASE_URL)

def fetch_global_macro_data(days=7):
    """Fetch recent global macro data"""
    query = text("""
        SELECT date, gold_price, silver_price, nasdaq_price
        FROM global_macro
        ORDER BY date DESC
        LIMIT :days
    """)

    with engine.connect() as conn:
        result = conn.execute(query, {'days': days})
        rows = result.fetchall()

        if not rows:
            return None

        data = []
        for row in rows:
            data.append({
                'date': row[0].strftime('%Y-%m-%d') if row[0] else None,
                'gold_price': float(row[1]) if row[1] else None,
                'silver_price': float(row[2]) if row[2] else None,
                'nasdaq_price': float(row[3]) if row[3] else None
            })
        return data

def fetch_vietnam_gold_data(days=7):
    """Fetch recent Vietnam gold prices"""
    query = text("""
        SELECT date, buy_price, sell_price
        FROM vn_gold_24h_hist
        WHERE type = 'DOJI HN'
        ORDER BY date DESC
        LIMIT :days
    """)

    with engine.connect() as conn:
        result = conn.execute(query, {'days': days})
        rows = result.fetchall()

        if not rows:
            return None

        data = []
        for row in rows:
            data.append({
                'date': row[0].strftime('%Y-%m-%d') if row[0] else None,
                'buy_price': float(row[1]) if row[1] else None,
                'sell_price': float(row[2]) if row[2] else None
            })
        return data

def generate_analysis_prompt(global_data, vietnam_data):
    """Generate prompt for Gemini AI"""

    # Latest data
    latest_global = global_data[0] if global_data else {}
    latest_vietnam = vietnam_data[0] if vietnam_data else {}

    # Calculate trends
    if len(global_data) >= 2:
        gold_change = ((global_data[0]['gold_price'] - global_data[-1]['gold_price']) / global_data[-1]['gold_price'] * 100)
        silver_change = ((global_data[0]['silver_price'] - global_data[-1]['silver_price']) / global_data[-1]['silver_price'] * 100)
        nasdaq_change = ((global_data[0]['nasdaq_price'] - global_data[-1]['nasdaq_price']) / global_data[-1]['nasdaq_price'] * 100)
    else:
        gold_change = silver_change = nasdaq_change = 0

    if len(vietnam_data) >= 2:
        vn_gold_change = ((vietnam_data[0]['buy_price'] - vietnam_data[-1]['buy_price']) / vietnam_data[-1]['buy_price'] * 100)
    else:
        vn_gold_change = 0

    prompt = f"""
Bạn là chuyên gia phân tích thị trường vàng. Hãy viết một bài phân tích thị trường vàng hôm nay bằng tiếng Việt với cấu trúc sau:

**DỮ LIỆU THỊ TRƯỜNG TOÀN CẦU (7 ngày gần nhất):**
- Giá vàng tương lai COMEX: ${latest_global.get('gold_price', 0):.2f}/oz (thay đổi 7 ngày: {gold_change:+.2f}%)
- Giá bạc quốc tế: ${latest_global.get('silver_price', 0):.2f}/oz (thay đổi 7 ngày: {silver_change:+.2f}%)
- Chỉ số NASDAQ: {latest_global.get('nasdaq_price', 0):,.2f} điểm (thay đổi 7 ngày: {nasdaq_change:+.2f}%)

**DỮ LIỆU THỊ TRƯỜNG VIỆT NAM (7 ngày gần nhất):**
- Vàng SJC DOJI HN hôm nay: {latest_vietnam.get('buy_price', 0):,.1f} - {latest_vietnam.get('sell_price', 0):,.1f} triệu đồng/lượng
- Thay đổi 7 ngày: {vn_gold_change:+.2f}%

**YÊU CẦU:**

1. Viết đúng 3 câu phân tích thị trường toàn cầu:
   - Câu 1: Nhận xét về giá vàng tương lai COMEX và xu hướng
   - Câu 2: Nhận xét về chỉ số NASDAQ và ảnh hưởng đến tâm lý đầu tư vàng
   - Câu 3: Nhận xét về giá bạc và mối tương quan với vàng

2. Viết đúng 3 câu phân tích thị trường Việt Nam:
   - Câu 1: Giá vàng SJC hôm nay và xu hướng
   - Câu 2: Chênh lệch mua-bán và thanh khoản thị trường
   - Câu 3: So sánh với giá vàng thế giới (tính theo tỷ giá)

3. Viết đúng 3 câu dự báo tuần tới (từ {(datetime.now() + timedelta(days=1)).strftime('%d/%m')} đến {(datetime.now() + timedelta(days=7)).strftime('%d/%m/%Y')}):
   - Câu 1: Xu hướng giá dự kiến (tăng/giảm/đi ngang) với mức giá cụ thể
   - Câu 2: Yếu tố chính hỗ trợ xu hướng (Fed, lạm phát, địa chính trị, v.v.)
   - Câu 3: Rủi ro cần lưu ý và khuyến nghị

**FORMAT ĐẦU RA (chỉ trả về HTML, không có markdown ```html):**

<h3>Diễn biến thị trường vàng toàn cầu</h3>
<p>
[3 câu phân tích, mỗi câu có <strong>con số chính xác</strong> từ dữ liệu]
</p>

<h3>Thị trường vàng trong nước</h3>
<p>
[3 câu phân tích, mỗi câu có <strong>con số chính xác</strong> từ dữ liệu]
</p>

<h3>Dự báo tuần tới ({(datetime.now() + timedelta(days=1)).strftime('%d/%m')} - {(datetime.now() + timedelta(days=7)).strftime('%d/%m/%Y')})</h3>
<p>
[3 câu dự báo với lý do cụ thể và mức giá dự kiến]
</p>

<h3>Tin tức quốc tế liên quan</h3>
<ul>
    <li><a href="https://www.reuters.com/markets/commodities/gold-prices/" target="_blank" rel="noopener">Reuters: Gold climbs on Fed rate cut bets, softer dollar</a></li>
    <li><a href="https://www.bloomberg.com/quote/XAUUSD:CUR" target="_blank" rel="noopener">Bloomberg: Gold Rises as Traders Weigh Fed Policy Path</a></li>
    <li><a href="https://www.cnbc.com/quotes/@GC.1" target="_blank" rel="noopener">CNBC: Gold Futures - Latest Price & Chart</a></li>
    <li><a href="https://www.kitco.com/news/gold/" target="_blank" rel="noopener">Kitco: Gold News & Analysis</a></li>
    <li><a href="https://www.ft.com/commodities" target="_blank" rel="noopener">Financial Times: Commodities Market Data</a></li>
</ul>

<p class="disclaimer" style="font-size: 0.9em; color: #888; margin-top: 1.5rem;">
    <strong>Lưu ý:</strong> Phân tích này chỉ mang tính chất tham khảo, không phải lời khuyên đầu tư.
    Nhà đầu tư cần tự nghiên cứu và chịu trách nhiệm với quyết định của mình.
</p>

**LƯU Ý QUAN TRỌNG:**
- Chỉ sử dụng số liệu thực tế từ dữ liệu đã cung cấp
- Viết tự nhiên, chuyên nghiệp, dễ hiểu
- Mỗi phần ĐÚNG 3 câu, không nhiều hơn
- Không thêm tiêu đề hay phần giới thiệu
- Không sử dụng markdown code blocks (```html)
"""

    return prompt

def generate_analysis():
    """Generate gold market analysis using Gemini AI"""

    print("="*60)
    print("Gold Market Analysis Agent")
    print("="*60)

    # Fetch data
    print("\n1. Fetching global macro data...")
    global_data = fetch_global_macro_data(days=7)
    if not global_data:
        print("❌ No global macro data found")
        return None
    print(f"✅ Fetched {len(global_data)} days of global data")
    print(f"   Latest: Gold ${global_data[0]['gold_price']:.2f}, NASDAQ {global_data[0]['nasdaq_price']:,.2f}")

    print("\n2. Fetching Vietnam gold data...")
    vietnam_data = fetch_vietnam_gold_data(days=7)
    if not vietnam_data:
        print("❌ No Vietnam gold data found")
        return None
    print(f"✅ Fetched {len(vietnam_data)} days of Vietnam data")
    print(f"   Latest: {vietnam_data[0]['buy_price']:,.1f} - {vietnam_data[0]['sell_price']:,.1f} triệu đồng")

    # Generate prompt
    print("\n3. Generating analysis prompt...")
    prompt = generate_analysis_prompt(global_data, vietnam_data)

    # Call Gemini AI
    print("\n4. Calling Gemini AI for analysis...")
    try:
        response = model.generate_content(prompt)
        analysis_html = response.text.strip()

        # Clean up response (remove markdown code blocks if present)
        if analysis_html.startswith('```html'):
            analysis_html = analysis_html.replace('```html', '').replace('```', '').strip()

        print("✅ Analysis generated successfully")
        print(f"   Length: {len(analysis_html)} characters")

        return {
            'date': datetime.now().strftime('%Y-%m-%d'),
            'generated_at': datetime.now(),
            'content': analysis_html,
            'global_data_points': len(global_data),
            'vietnam_data_points': len(vietnam_data)
        }

    except Exception as e:
        print(f"❌ Error calling Gemini AI: {e}")
        return None

def save_analysis_to_db(analysis):
    """Save analysis to database"""

    # Create table if not exists
    create_table_query = text("""
        CREATE TABLE IF NOT EXISTS gold_analysis (
            date DATE PRIMARY KEY,
            generated_at TIMESTAMP NOT NULL,
            content TEXT NOT NULL,
            global_data_points INTEGER,
            vietnam_data_points INTEGER
        )
    """)

    # Insert or update analysis
    upsert_query = text("""
        INSERT INTO gold_analysis (date, generated_at, content, global_data_points, vietnam_data_points)
        VALUES (:date, :generated_at, :content, :global_data_points, :vietnam_data_points)
        ON CONFLICT (date)
        DO UPDATE SET
            generated_at = EXCLUDED.generated_at,
            content = EXCLUDED.content,
            global_data_points = EXCLUDED.global_data_points,
            vietnam_data_points = EXCLUDED.vietnam_data_points
    """)

    try:
        with engine.connect() as conn:
            # Create table
            conn.execute(create_table_query)
            conn.commit()

            # Insert analysis
            conn.execute(upsert_query, analysis)
            conn.commit()

        print(f"\n✅ Analysis saved to database for {analysis['date']}")
        return True

    except Exception as e:
        print(f"\n❌ Error saving to database: {e}")
        return False

def main():
    """Main execution"""
    try:
        # Generate analysis
        analysis = generate_analysis()

        if not analysis:
            print("\n❌ Failed to generate analysis")
            return False

        # Save to database
        print("\n5. Saving analysis to database...")
        success = save_analysis_to_db(analysis)

        if success:
            print("\n" + "="*60)
            print("✅ Gold Analysis Agent completed successfully")
            print("="*60)
            print(f"\nPreview of generated content:")
            print("-"*60)
            print(analysis['content'][:500] + "...")
            print("-"*60)
            return True
        else:
            print("\n❌ Failed to save analysis")
            return False

    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)