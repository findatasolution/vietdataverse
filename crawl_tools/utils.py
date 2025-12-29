# Crawl gold prices from 24h.com.vn
from bs4 import BeautifulSoup
import requests

def crawl_gold_price_24h(date_str):
    """
    Crawl DOJI HN gold prices from 24h.com.vn for a specific date
    date_str format: 'YYYY-MM-DD'
    Returns: dict with buy and sell prices for DOJI HN gold, or None if not found
    """
    url = f'https://www.24h.com.vn/gia-vang-hom-nay-c425.html?ngaythang={date_str}'

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        # Find the gold price table
        tables = soup.find_all('table')

        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                cols = row.find_all('td')
                if len(cols) >= 4:
                    brand = cols[0].get_text(strip=True)

                    # Look for DOJI HN brand only
                    if 'DOJI' in brand and 'HN' in brand:
                        try:
                            buy_price_text = cols[1].get_text(strip=True)
                            sell_price_text = cols[3].get_text(strip=True)

                            # Skip if prices are empty or contain non-numeric data
                            if not buy_price_text or not sell_price_text:
                                continue

                            # Remove thousand separators (dots and commas) and convert
                            # Website shows prices in thousands VND (e.g., "157.700" = 157,700 thousand VND)
                            buy_price = buy_price_text.replace('.', '').replace(',', '')
                            sell_price = sell_price_text.replace('.', '').replace(',', '')

                            # Convert to float and multiply by 1000 to get full VND
                            # Example: "157.700" → "157700" → 157700 * 1000 = 157,700,000 VND
                            buy_price = float(buy_price) * 1000
                            sell_price = float(sell_price) * 1000

                            return {
                                'date': date_str,
                                'buy_price': buy_price,
                                'sell_price': sell_price
                            }
                        except (ValueError, IndexError) as e:
                            print(f"Parse error for {brand}: {e}")
                            continue

        return None

    except Exception as e:
        print(f"Error crawling {date_str}: {e}")
        return None