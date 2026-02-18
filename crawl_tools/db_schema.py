"""
Crawling Bot Database Schema
Database: crawling_bot (PostgreSQL - Neon)

This file documents all tables used by the crawling tools.
Tables are auto-created via CREATE TABLE IF NOT EXISTS in individual crawlers,
but this file serves as the central schema reference.
"""

from sqlalchemy import (
    Column, Integer, String, Float, Date, DateTime, Text,
    UniqueConstraint, Index, create_engine, MetaData
)
from sqlalchemy.orm import declarative_base
import os
from dotenv import load_dotenv

load_dotenv()

Base = declarative_base()

# ======================
# SBV (State Bank of Vietnam) Tables
# ======================

class VnSbvInterbankRate(Base):
    """
    SBV Interbank Interest Rates
    Source: https://sbv.gov.vn API
    Crawler: crawl_sbv.py
    Schedule: Daily 9:30 AM VN
    """
    __tablename__ = 'vn_sbv_interbankrate'

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False, index=True)
    crawl_time = Column(DateTime, nullable=False)

    # Interest rates by term (% per annum)
    quadem = Column(Float)      # Overnight
    quadem_ds = Column(Float)   # Overnight - trading volume
    w1 = Column('1w', Float)    # 1 week
    w1_ds = Column('1w_ds', Float)
    w2 = Column('2w', Float)    # 2 weeks
    w2_ds = Column('2w_ds', Float)
    m1 = Column('1m', Float)    # 1 month
    m1_ds = Column('1m_ds', Float)
    m3 = Column('3m', Float)    # 3 months
    m3_ds = Column('3m_ds', Float)
    m6 = Column('6m', Float)    # 6 months
    m6_ds = Column('6m_ds', Float)
    m9 = Column('9m', Float)    # 9 months
    m9_ds = Column('9m_ds', Float)

    # Policy rates
    rediscount_rate = Column(Float)     # Lai suat tai chiet khau
    refinancing_rate = Column(Float)    # Lai suat tai cap von

    __table_args__ = (
        UniqueConstraint('date', name='uq_sbv_interbank_date'),
    )


class VnSbvCentralRate(Base):
    """
    Exchange Rates (multi-source, multi-currency)
    Sources:
    - SBV Crawl: Central rate from https://sbv.gov.vn/vi/ty-gia (type=USD, source=Crawl, bank=SBV)
      Crawler: crawl_sbv.py (3-layer adaptive parsing) | Schedule: Daily 9:30 AM VN
    - VNAppMob API: Commercial bank rates (source=API, bank=BID/TCB)
      Crawler: crawl_exchange_rate.py | Schedule: Daily 10:00 AM VN
      Currencies: USD, EUR, JPY, GBP, CNY, AUD, SGD, KRW, THB, CAD, CHF, HKD, NZD, TWD, MYR

    Prices are in VND per unit of foreign currency.
    Dedup: per (date, type, source, bank).
    """
    __tablename__ = 'vn_sbv_centralrate'

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False, index=True)
    crawl_time = Column(DateTime, nullable=False)
    type = Column(String(20), nullable=False, default='USD')     # Currency code (USD, EUR, JPY...)
    source = Column(String(20), nullable=False, default='Crawl') # 'Crawl' or 'API'
    bank = Column(String(10), default='SBV')                     # SBV, BID, TCB...
    usd_vnd_rate = Column(Float)        # Central rate / buy_transfer for USD
    buy_cash = Column(Float)            # Cash buy rate
    buy_transfer = Column(Float)        # Transfer buy rate
    sell_rate = Column(Float)           # Sell rate
    document_no = Column(String(50))    # SBV document number

    __table_args__ = (
        UniqueConstraint('date', 'type', 'source', 'bank', name='uq_centralrate_date_type_source_bank'),
        Index('idx_centralrate_date_type_bank', 'date', 'type', 'bank'),
    )


# ======================
# Bank Term Deposit Tables
# ======================

class VnBankTermDepo(Base):
    """
    Vietnamese Bank Term Deposit Interest Rates
    Sources: ACB, SHB, CTG (VietinBank), VCB (Vietcombank)
    Crawler: crawl_bank_termdepo.py (with 3-layer adaptive parsing)
    Schedule: Daily 8:30 AM VN

    Layers:
    - Layer 1: Structured Parser (bank-specific HTML patterns)
    - Layer 2: Heuristic Parser (score tables, extract best match)
    - Layer 3: LLM Parser (Gemini 2.5 Flash for fallback)
    """
    __tablename__ = 'vn_bank_termdepo'

    id = Column(Integer, primary_key=True)  # Manual ID generation (no autoincrement)
    bank = Column(String(10), nullable=False, index=True)  # ACB, SHB, CTG, VCB
    date = Column(Date, nullable=False, index=True)
    crawl_time = Column(DateTime, nullable=False)

    # Interest rates by term (% per annum)
    # Term naming: m1=1 month, m3=3 months, m6=6 months, etc.
    m1 = Column('1m', Float)
    m2 = Column('2m', Float)
    m3 = Column('3m', Float)
    m4 = Column('4m', Float)
    m5 = Column('5m', Float)
    m6 = Column('6m', Float)
    m7 = Column('7m', Float)
    m8 = Column('8m', Float)
    m9 = Column('9m', Float)
    m10 = Column('10m', Float)
    m11 = Column('11m', Float)
    m12 = Column('12m', Float)
    m13 = Column('13m', Float)
    m15 = Column('15m', Float)
    m18 = Column('18m', Float)
    m24 = Column('24m', Float)
    m36 = Column('36m', Float)

    __table_args__ = (
        UniqueConstraint('bank', 'date', name='uq_bank_termdepo_bank_date'),
        Index('idx_bank_termdepo_bank_date', 'bank', 'date'),
    )


# ======================
# Gold & Silver Price Tables
# ======================

class VnGold24hHist(Base):
    """
    Gold Prices (multi-source)
    Sources:
    - 24h.com.vn: types like "SJC HN", "DOJI HN", "PNJ HN" etc.
      Crawler: crawl_gold_silver.py | Schedule: 2x Daily (8:30 AM, 2:30 PM VN)
    - BTMC API: types prefixed "BTMC " (e.g. "BTMC SJC", "BTMC VRTL", "BTMC Nhẫn Trơn")
      Crawler: api_gold_btmc.py | Schedule: 2x Daily (9:00 AM, 3:00 PM VN)

    Prices are in VND per chỉ (1/10 lượng = 3.75g).
    Dedup: per (date, type, hour) — allows 2 intraday snapshots.
    """
    __tablename__ = 'vn_gold_24h_hist'

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False, index=True)
    type = Column(String(100), nullable=False)  # Gold type (SJC, DOJI, etc.)
    buy_price = Column(Float)   # Buy price (VND/tael)
    sell_price = Column(Float)  # Sell price (VND/tael)
    crawl_time = Column(DateTime, nullable=False)

    __table_args__ = (
        Index('idx_gold_24h_date_type', 'date', 'type'),
    )


class VnSilverPhuQuyHist(Base):
    """
    Silver Prices from Phu Quy
    Sources:
    - https://www.phuquy.com.vn/gia-bac-hom-nay
    - https://www.phuquy.com.vn/gia-vang-hom-nay
    Crawler: crawl_gold_silver.py
    Schedule: 2x Daily (8:30 AM, 2:30 PM VN)
    """
    __tablename__ = 'vn_silver_phuquy_hist'

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False, index=True)
    crawl_time = Column(DateTime, nullable=False)
    buy_price = Column(Float)   # Buy price (VND)
    sell_price = Column(Float)  # Sell price (VND)
    source = Column(String(50)) # Source identifier

    __table_args__ = (
        Index('idx_silver_phuquy_date', 'date'),
    )


# ======================
# Utility Functions
# ======================

def create_all_tables(engine):
    """Create all tables if they don't exist."""
    Base.metadata.create_all(engine)
    print("All tables created/verified.")


def get_engine():
    """Get database engine from environment."""
    db_url = os.getenv('CRAWLING_BOT_DB')
    if not db_url:
        raise ValueError("CRAWLING_BOT_DB environment variable not set")
    return create_engine(db_url)


if __name__ == '__main__':
    # When run directly, create all tables
    print("Crawling Bot Database Schema")
    print("=" * 50)

    try:
        engine = get_engine()
        create_all_tables(engine)

        # List all tables
        print("\nTables in schema:")
        for table in Base.metadata.sorted_tables:
            print(f"  - {table.name}")

    except ValueError as e:
        print(f"Error: {e}")
        print("\nTo create tables, set CRAWLING_BOT_DB environment variable.")
        print("\nSchema defined for the following tables:")
        for cls_name, cls in [
            ('VnSbvInterbankRate', VnSbvInterbankRate),
            ('VnSbvCentralRate', VnSbvCentralRate),
            ('VnBankTermDepo', VnBankTermDepo),
            ('VnGold24hHist', VnGold24hHist),
            ('VnSilverPhuQuyHist', VnSilverPhuQuyHist),
        ]:
            print(f"  - {cls.__tablename__} ({cls.__doc__.strip().split(chr(10))[0]})")
