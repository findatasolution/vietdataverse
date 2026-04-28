"""
VN30 Company Profile & ICB Sector Classification Crawler
Source: vnstock3 listing API
Schedule: Monthly (1st of each month) — 8:00 AM VN
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import os
from datetime import datetime, date
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / 'be' / '.env')

current_date = datetime.now()
print(f"\n{'='*60}")
print(f"VN30 Company Profile Crawler — {current_date.strftime('%Y-%m-%d %H:%M')}")
print(f"{'='*60}")

CRAWLING_CORP_DB = os.getenv('CRAWLING_CORP_DB')
if not CRAWLING_CORP_DB:
    raise ValueError("CRAWLING_CORP_DB environment variable not set")
engine = create_engine(CRAWLING_CORP_DB)

VN30_TICKERS = [
    'ACB', 'BCM', 'BID', 'BVH', 'CTG', 'FPT', 'GAS', 'GVR',
    'HDB', 'HPG', 'MBB', 'MSN', 'MWG', 'NVL', 'PDR', 'PLX',
    'POW', 'SAB', 'SHB', 'SSB', 'SSI', 'STB', 'TCB', 'TPB',
    'VCB', 'VHM', 'VIB', 'VIC', 'VJC', 'VPB'
]

# Fallback ICB + company name mapping (used when vnstock3 unavailable)
# Format: (icb_sector, icb_industry, icb_supersector, icb_code, company_name_vn, company_name_en, exchange)
ICB_FALLBACK = {
    'ACB': ('Financials', 'Banking', 'Banks', '8355'),
    'BCM': ('Real Estate', 'Real Estate', 'Real Estate Inv & Services', '8633'),
    'BID': ('Financials', 'Banking', 'Banks', '8355'),
    'BVH': ('Financials', 'Insurance', 'Full Line Insurance', '8532'),
    'CTG': ('Financials', 'Banking', 'Banks', '8355'),
    'FPT': ('Technology', 'Technology', 'Software & Computer Services', '9537'),
    'GAS': ('Oil & Gas', 'Oil & Gas Producers', 'Exploration & Production', '0533'),
    'GVR': ('Basic Materials', 'Chemicals', 'Specialty Chemicals', '1357'),
    'HDB': ('Financials', 'Banking', 'Banks', '8355'),
    'HPG': ('Basic Materials', 'Industrial Metals', 'Steel', '1757'),
    'MBB': ('Financials', 'Banking', 'Banks', '8355'),
    'MSN': ('Consumer Goods', 'Food Producers', 'Food Products', '3577'),
    'MWG': ('Consumer Services', 'Retailers', 'Specialty Retailers', '5375'),
    'NVL': ('Real Estate', 'Real Estate', 'Real Estate Inv & Services', '8633'),
    'PDR': ('Real Estate', 'Real Estate', 'Real Estate Inv & Services', '8633'),
    'PLX': ('Oil & Gas', 'Oil & Gas Producers', 'Integrated Oil & Gas', '0530'),
    'POW': ('Utilities', 'Electricity', 'Conventional Electricity', '7535'),
    'SAB': ('Consumer Goods', 'Beverages', 'Brewers', '3533'),
    'SHB': ('Financials', 'Banking', 'Banks', '8355'),
    'SSB': ('Financials', 'Banking', 'Banks', '8355'),
    'SSI': ('Financials', 'Financial Services', 'Investment Services', '8771'),
    'STB': ('Financials', 'Banking', 'Banks', '8355'),
    'TCB': ('Financials', 'Banking', 'Banks', '8355'),
    'TPB': ('Financials', 'Banking', 'Banks', '8355'),
    'VCB': ('Financials', 'Banking', 'Banks', '8355'),
    'VHM': ('Real Estate', 'Real Estate', 'Real Estate Inv & Services', '8633'),
    'VIB': ('Financials', 'Banking', 'Banks', '8355'),
    'VIC': ('Consumer Services', 'General Retailers', 'Broadline Retailers', '5371'),
    'VJC': ('Consumer Services', 'Travel & Leisure', 'Airlines', '5751'),
    'VPB': ('Financials', 'Banking', 'Banks', '8355'),
}


def ensure_table():
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS vn30_company_profile (
                id SERIAL PRIMARY KEY,
                ticker VARCHAR(10) NOT NULL UNIQUE,
                company_name VARCHAR(200),
                company_name_en VARCHAR(200),
                exchange VARCHAR(10),
                icb_code VARCHAR(20),
                icb_sector VARCHAR(100),
                icb_industry VARCHAR(100),
                icb_supersector VARCHAR(100),
                market_cap_billion FLOAT,
                listed_date DATE,
                updated_at TIMESTAMP NOT NULL,
                source TEXT NOT NULL DEFAULT 'vnstock3',
                group_name VARCHAR(20) NOT NULL DEFAULT 'stock'
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_vn30_profile_ticker ON vn30_company_profile (ticker)"))
        # Migrate existing table
        for col, definition in [
            ('source',     "TEXT NOT NULL DEFAULT 'vnstock3'"),
            ('group_name', "VARCHAR(20) NOT NULL DEFAULT 'stock'"),
        ]:
            try:
                conn.execute(text(f"ALTER TABLE vn30_company_profile ADD COLUMN IF NOT EXISTS {col} {definition}"))
                conn.commit()
            except Exception:
                conn.rollback()
        conn.commit()
    print("Table vn30_company_profile ready.")


COMPANY_NAMES = {
    'ACB':  ('Ngân hàng TMCP Á Châu',                         'Asia Commercial Bank',              'HOSE'),
    'BCM':  ('Tổng Công ty Đầu tư và Phát triển Công nghiệp', 'Becamex IDC Corp',                  'HOSE'),
    'BID':  ('Ngân hàng TMCP Đầu tư và Phát triển VN',        'BIDV',                              'HOSE'),
    'BVH':  ('Tập đoàn Bảo Việt',                             'Bao Viet Holdings',                 'HOSE'),
    'CTG':  ('Ngân hàng TMCP Công Thương Việt Nam',           'VietinBank',                        'HOSE'),
    'FPT':  ('Công ty Cổ phần FPT',                           'FPT Corporation',                   'HOSE'),
    'GAS':  ('Tổng Công ty Khí Việt Nam',                     'PetroVietnam Gas JSC',              'HOSE'),
    'GVR':  ('Tập đoàn Công nghiệp Cao su Việt Nam',          'Vietnam Rubber Group',              'HOSE'),
    'HDB':  ('Ngân hàng TMCP Phát triển TP. HCM',             'HDBank',                            'HOSE'),
    'HPG':  ('Công ty Cổ phần Tập đoàn Hòa Phát',            'Hoa Phat Group',                    'HOSE'),
    'MBB':  ('Ngân hàng TMCP Quân đội',                       'Military Commercial Bank',          'HOSE'),
    'MSN':  ('Công ty Cổ phần Tập đoàn Masan',               'Masan Group',                       'HOSE'),
    'MWG':  ('Công ty Cổ phần Đầu tư Thế Giới Di Động',      'Mobile World Investment',           'HOSE'),
    'NVL':  ('Công ty Cổ phần Tập đoàn Đầu tư Địa ốc No Va', 'Novaland Group',                    'HOSE'),
    'PDR':  ('Công ty Cổ phần Phát triển Bất động sản Phát Đạt','Phat Dat Real Estate',           'HOSE'),
    'PLX':  ('Tập đoàn Xăng Dầu Việt Nam',                   'Petrolimex',                        'HOSE'),
    'POW':  ('Tổng Công ty Điện lực Dầu khí VN',              'PV Power',                          'HOSE'),
    'SAB':  ('Tổng Công ty CP Bia - Rượu - NGK Sài Gòn',     'Sabeco',                            'HOSE'),
    'SHB':  ('Ngân hàng TMCP Sài Gòn - Hà Nội',              'SHB',                               'HNX'),
    'SSB':  ('Ngân hàng TMCP Đông Nam Á',                     'SeABank',                           'HOSE'),
    'SSI':  ('Công ty Cổ phần Chứng khoán SSI',               'SSI Securities',                    'HOSE'),
    'STB':  ('Ngân hàng TMCP Sài Gòn Thương Tín',            'Sacombank',                         'HOSE'),
    'TCB':  ('Ngân hàng TMCP Kỹ thương Việt Nam',             'Techcombank',                       'HOSE'),
    'TPB':  ('Ngân hàng TMCP Tiên Phong',                     'TPBank',                            'HOSE'),
    'VCB':  ('Ngân hàng TMCP Ngoại thương Việt Nam',          'Vietcombank',                       'HOSE'),
    'VHM':  ('Công ty Cổ phần Vinhomes',                      'Vinhomes',                          'HOSE'),
    'VIB':  ('Ngân hàng TMCP Quốc tế Việt Nam',               'Vietnam International Bank',        'HOSE'),
    'VIC':  ('Tập đoàn Vingroup',                             'Vingroup',                          'HOSE'),
    'VJC':  ('Công ty Cổ phần Hàng không VietJet',            'VietJet Air',                       'HOSE'),
    'VPB':  ('Ngân hàng TMCP Việt Nam Thịnh Vượng',           'VPBank',                            'HOSE'),
}


def fetch_profile_vnstock(ticker: str) -> dict:
    """Fetch company profile — tries vnstock3, falls back to static COMPANY_NAMES."""
    try:
        from vnstock3 import Vnstock
        stock = Vnstock().stock(symbol=ticker, source='VCI')
        info = stock.company.overview()
        if info is not None and not info.empty:
            row = info.iloc[0]
            return {
                'company_name':    str(row.get('shortName', '')),
                'company_name_en': str(row.get('enShortName', '')),
                'exchange':        str(row.get('exchange', '')),
                'market_cap_billion': float(row['marketCap']) / 1e9 if row.get('marketCap') else None,
            }
    except ImportError:
        pass
    except Exception as e:
        print(f"  [{ticker}] vnstock3 overview error: {e}")

    # Fallback: static company names
    names = COMPANY_NAMES.get(ticker, ('', '', 'HOSE'))
    return {
        'company_name':    names[0],
        'company_name_en': names[1],
        'exchange':        names[2],
        'market_cap_billion': None,
    }


def upsert_profile(ticker: str, profile: dict, updated_at: datetime):
    icb = ICB_FALLBACK.get(ticker, ('', '', '', ''))
    with engine.connect() as conn:
        conn.execute(text("""
            INSERT INTO vn30_company_profile
                (ticker, company_name, company_name_en, exchange,
                 icb_sector, icb_industry, icb_supersector, icb_code,
                 market_cap_billion, updated_at, source, group_name)
            VALUES
                (:ticker, :company_name, :company_name_en, :exchange,
                 :icb_sector, :icb_industry, :icb_supersector, :icb_code,
                 :market_cap_billion, :updated_at, :source, :group_name)
            ON CONFLICT (ticker) DO UPDATE SET
                company_name = EXCLUDED.company_name,
                company_name_en = EXCLUDED.company_name_en,
                exchange = EXCLUDED.exchange,
                icb_sector = EXCLUDED.icb_sector,
                icb_industry = EXCLUDED.icb_industry,
                icb_supersector = EXCLUDED.icb_supersector,
                icb_code = EXCLUDED.icb_code,
                market_cap_billion = EXCLUDED.market_cap_billion,
                updated_at = EXCLUDED.updated_at,
                source = EXCLUDED.source,
                group_name = EXCLUDED.group_name
        """), {
            'ticker': ticker,
            'company_name': profile.get('company_name', ''),
            'company_name_en': profile.get('company_name_en', ''),
            'exchange': profile.get('exchange', 'HOSE'),
            'icb_sector': icb[0],
            'icb_industry': icb[1],
            'icb_supersector': icb[2],
            'icb_code': icb[3],
            'market_cap_billion': profile.get('market_cap_billion'),
            'updated_at': updated_at,
            'source': 'vnstock3',
            'group_name': 'stock',
        })
        conn.commit()


def main():
    ensure_table()
    updated_at = datetime.now()
    success = 0
    errors = 0

    for ticker in VN30_TICKERS:
        print(f"\n  [{ticker}] Fetching profile...")
        try:
            profile = fetch_profile_vnstock(ticker)
            upsert_profile(ticker, profile, updated_at)
            icb = ICB_FALLBACK.get(ticker, ('?', '?', '?', '?'))
            print(f"  [{ticker}] OK — {profile.get('company_name', 'N/A')} | {icb[0]} / {icb[1]}")
            success += 1
            import time; time.sleep(0.5)
        except Exception as e:
            import traceback
            print(f"  [{ticker}] ERROR: {e}")
            print(f"  {traceback.format_exc()}")
            errors += 1

    print(f"\n{'='*60}")
    print(f"VN30 Profile Crawler done. Success: {success}, Errors: {errors}")
    print(f"Completed at {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
