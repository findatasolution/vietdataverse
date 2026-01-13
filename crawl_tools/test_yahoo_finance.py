"""
Test Yahoo Finance data crawling
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import yfinance as yf
from datetime import datetime

print("="*60)
print("Testing Yahoo Finance API")
print("="*60)

tickers = {
    'Gold Futures': 'GC=F',
    'Silver Futures': 'SI=F',
    'NASDAQ Composite': '^IXIC'
}

for name, ticker_symbol in tickers.items():
    try:
        print(f"\n{name} ({ticker_symbol}):")
        ticker = yf.Ticker(ticker_symbol)
        hist = ticker.history(period='1d')

        if not hist.empty:
            close_price = hist['Close'].iloc[-1]
            print(f"  Close Price: ${close_price:,.2f}")
            print(f"  Date: {hist.index[-1].strftime('%Y-%m-%d')}")
        else:
            print(f"  ⚠️  No data available")

    except Exception as e:
        print(f"  ❌ Error: {e}")

print("\n" + "="*60)
print("Test completed!")
print("="*60)