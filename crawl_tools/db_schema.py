"""
Crawling Bot Database Schema
Database: crawling_bot (PostgreSQL - Neon)

This file documents all tables used by the crawling tools.
Tables are auto-created via CREATE TABLE IF NOT EXISTS in individual crawlers,
but this file serves as the central schema reference.

Databases:
  CRAWLING_BOT_DB  — macro data (gold, FX, SBV, CPI, GSO)
  CRAWLING_CORP_DB — corporate/equity data (VN30 price, profile, financials, ratios)

━━━ MANDATORY COLUMNS (all tables) ━━━━━━━━━━━━━━━━━━━━━
  id          SERIAL PRIMARY KEY
  period      DATE (daily) or VARCHAR(7) YYYY-MM (monthly)
  crawl_time  TIMESTAMP NOT NULL   — UTC
  source      TEXT                 — source URL or org name
  group_name  VARCHAR(20) NOT NULL — see GROUP TAXONOMY below

━━━ GROUP TAXONOMY ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  macro     — VN macro indicators (CPI, GDP, trade, IIP, PPI)
  finance   — Financial rates (term deposit, SBV interbank, FX)
  commodity — Commodity prices (gold, silver, oil, global)
  stock     — Equity & corporate (VN30 OHLCV, financials, ratios)
  sentiment — Market sentiment (news, social, retail flow)  [future]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

from sqlalchemy import (
    Column, Integer, String, Float, Date, DateTime, Text, Boolean,
    UniqueConstraint, Index, create_engine, MetaData
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base, sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

Base = declarative_base()

# CorpBase / CorpSession — used by VN30 crawlers targeting CRAWLING_CORP_DB
CorpBase = declarative_base()
_corp_db_url = os.getenv('CRAWLING_CORP_DB')
if _corp_db_url:
    corp_engine = create_engine(_corp_db_url)
    CorpSession = sessionmaker(bind=corp_engine)
else:
    corp_engine = None
    CorpSession = None

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
    __tablename__ = 'vn_macro_sbv_rate_daily'

    id         = Column(Integer, primary_key=True, autoincrement=True)
    date       = Column(Date, nullable=False, index=True)
    crawl_time = Column(DateTime, nullable=False)
    source     = Column(Text, nullable=False, default='sbv.gov.vn')   # sbv.gov.vn
    group_name = Column(String(20), nullable=False, default='finance') # finance

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
    __tablename__ = 'vn_macro_fxrate_daily'

    id         = Column(Integer, primary_key=True, autoincrement=True)
    date       = Column(Date, nullable=False, index=True)
    crawl_time = Column(DateTime, nullable=False)
    # NOTE: 'source' here = data provider ('Crawl'/'API') — satisfies mandatory source field
    source     = Column(String(20), nullable=False, default='Crawl') # 'Crawl' or 'API' (sbv.gov.vn / api.vnappmob.com)
    group_name = Column(String(20), nullable=False, default='finance') # finance
    type = Column(String(20), nullable=False, default='USD')  # Currency code (USD, EUR, JPY...)
    bank = Column(String(10), default='SBV')                  # SBV, BID, TCB...
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
    Source: ACB (acb.com.vn)
    Crawler: crawl_bank_termdepo.py
    Schedule: Daily 8:30 AM VN
    """
    __tablename__ = 'vn_macro_termdepo_daily'

    id         = Column(Integer, primary_key=True, autoincrement=True)
    bank_code  = Column(String(10), nullable=False, index=True)  # ACB
    date       = Column(Date, nullable=False, index=True)
    crawl_time = Column(DateTime, nullable=False)
    source     = Column(Text, nullable=False, default='acb.com.vn')    # acb.com.vn
    group_name = Column(String(20), nullable=False, default='finance')  # finance

    # Interest rates by term (% per annum)
    m1  = Column('term_1m',  Float)
    m2  = Column('term_2m',  Float)
    m3  = Column('term_3m',  Float)
    m4  = Column('term_4m',  Float)
    m5  = Column('term_5m',  Float)
    m6  = Column('term_6m',  Float)
    m7  = Column('term_7m',  Float)
    m8  = Column('term_8m',  Float)
    m9  = Column('term_9m',  Float)
    m10 = Column('term_10m', Float)
    m11 = Column('term_11m', Float)
    m12 = Column('term_12m', Float)
    m13 = Column('term_13m', Float)
    m15 = Column('term_15m', Float)
    m18 = Column('term_18m', Float)
    m24 = Column('term_24m', Float)
    m36 = Column('term_36m', Float)

    __table_args__ = (
        UniqueConstraint('bank_code', 'date', name='uq_bank_termdepo_bank_date'),
        Index('idx_bank_termdepo_bank_date', 'bank_code', 'date'),
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
    __tablename__ = 'vn_macro_gold_daily'

    id         = Column(Integer, primary_key=True, autoincrement=True)
    date       = Column(Date, nullable=False, index=True)
    type       = Column(String(100), nullable=False)       # Gold type (SJC, DOJI, etc.)
    buy_price  = Column(Float)                             # Buy price (VND/chỉ)
    sell_price = Column(Float)                             # Sell price (VND/chỉ)
    crawl_time = Column(DateTime, nullable=False)
    source     = Column(Text, nullable=False, default='24h.com.vn')      # 24h.com.vn / api.btmc.vn
    group_name = Column(String(20), nullable=False, default='commodity')  # commodity

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
    __tablename__ = 'vn_macro_silver_daily'

    id         = Column(Integer, primary_key=True, autoincrement=True)
    date       = Column(Date, nullable=False, index=True)
    crawl_time = Column(DateTime, nullable=False)
    buy_price  = Column(Float)                             # Buy price (VND)
    sell_price = Column(Float)                             # Sell price (VND)
    source     = Column(Text, nullable=False, default='phuquy.com.vn')     # phuquy.com.vn
    group_name = Column(String(20), nullable=False, default='commodity')  # commodity

    __table_args__ = (
        Index('idx_silver_phuquy_date', 'date'),
    )


# ======================
# VN30 Stock Data Tables
# ======================

class Vn30OhlcvHist(Base):
    """
    VN30 Stock Daily OHLCV Prices
    Source: vnstock3 (SSI/TCBS data)
    Crawler: crawl_vn30_price.py
    Schedule: Daily 17:15 VN (after HSX close)
    """
    __tablename__ = 'vn30_ohlcv_daily'

    id         = Column(Integer, primary_key=True, autoincrement=True)
    ticker     = Column(String(10), nullable=False, index=True)
    date       = Column(Date, nullable=False, index=True)
    open       = Column(Float)
    high       = Column(Float)
    low        = Column(Float)
    close      = Column(Float)
    volume     = Column(Float)
    value      = Column(Float)                             # Trading value (VND)
    crawl_time = Column(DateTime, nullable=False)
    source     = Column(Text, nullable=False, default='vnstock3')        # vnstock3 / SSI / TCBS
    group_name = Column(String(20), nullable=False, default='stock')     # stock

    __table_args__ = (
        UniqueConstraint('ticker', 'date', name='uq_vn30_ohlcv_ticker_date'),
        Index('idx_vn30_ohlcv_ticker_date', 'ticker', 'date'),
    )


class Vn30CompanyProfile(Base):
    """
    VN30 Company Demographics & ICB Sector Classification
    Source: vnstock3 listing API
    Crawler: crawl_vn30_profile.py
    Schedule: Monthly (1st of each month)
    """
    __tablename__ = 'vn30_company_profile'

    id               = Column(Integer, primary_key=True, autoincrement=True)
    ticker           = Column(String(10), nullable=False, unique=True, index=True)
    company_name     = Column(String(200))
    company_name_en  = Column(String(200))
    exchange         = Column(String(10))          # HOSE, HNX
    icb_code         = Column(String(20))          # ICB industry code
    icb_sector       = Column(String(100))         # Top-level sector (e.g. Financials)
    icb_industry     = Column(String(100))         # Industry (e.g. Banking)
    icb_supersector  = Column(String(100))         # Supersector
    market_cap_billion = Column(Float)             # Billion VND
    listed_date      = Column(Date)
    updated_at       = Column(DateTime, nullable=False)
    source           = Column(Text, nullable=False, default='vnstock3')        # vnstock3
    group_name       = Column(String(20), nullable=False, default='stock')     # stock


class Vn30IncomeStmt(Base):
    """
    VN30 Quarterly Income Statement
    Source: vnstock3 financial statements
    Crawler: crawl_vn30_financials.py
    Schedule: Quarterly (15th of Jan/Apr/Jul/Oct)
    """
    __tablename__ = 'vn30_income_stmt_quarterly'

    id           = Column(Integer, primary_key=True, autoincrement=True)
    ticker       = Column(String(10), nullable=False, index=True)
    year         = Column(Integer, nullable=False)
    quarter      = Column(Integer, nullable=False)   # 1-4
    revenue      = Column(Float)
    gross_profit = Column(Float)
    ebit         = Column(Float)
    net_income   = Column(Float)
    eps          = Column(Float)                     # Earnings per share (VND)
    crawl_time   = Column(DateTime, nullable=False)
    source       = Column(Text, nullable=False, default='vnstock3')        # vnstock3
    group_name   = Column(String(20), nullable=False, default='stock')    # stock

    __table_args__ = (
        UniqueConstraint('ticker', 'year', 'quarter', name='uq_vn30_income_ticker_year_q'),
        Index('idx_vn30_income_ticker_year_q', 'ticker', 'year', 'quarter'),
    )


class Vn30BalanceSheet(Base):
    """
    VN30 Quarterly Balance Sheet
    Source: vnstock3
    Crawler: crawl_vn30_financials.py
    """
    __tablename__ = 'vn30_balance_sheet_quarterly'

    id                = Column(Integer, primary_key=True, autoincrement=True)
    ticker            = Column(String(10), nullable=False, index=True)
    year              = Column(Integer, nullable=False)
    quarter           = Column(Integer, nullable=False)
    total_assets      = Column(Float)
    total_liabilities = Column(Float)
    equity            = Column(Float)
    cash              = Column(Float)
    crawl_time        = Column(DateTime, nullable=False)
    source            = Column(Text, nullable=False, default='vnstock3')        # vnstock3
    group_name        = Column(String(20), nullable=False, default='stock')     # stock

    __table_args__ = (
        UniqueConstraint('ticker', 'year', 'quarter', name='uq_vn30_bs_ticker_year_q'),
    )


class Vn30CashFlow(Base):
    """
    VN30 Quarterly Cash Flow Statement
    Source: vnstock3
    Crawler: crawl_vn30_financials.py
    """
    __tablename__ = 'vn30_cashflow_quarterly'

    id            = Column(Integer, primary_key=True, autoincrement=True)
    ticker        = Column(String(10), nullable=False, index=True)
    year          = Column(Integer, nullable=False)
    quarter       = Column(Integer, nullable=False)
    cfo           = Column(Float)                    # Cash from operations
    cfi           = Column(Float)                    # Cash from investing
    cff           = Column(Float)                    # Cash from financing
    free_cashflow = Column(Float)
    crawl_time    = Column(DateTime, nullable=False)
    source        = Column(Text, nullable=False, default='vnstock3')        # vnstock3
    group_name    = Column(String(20), nullable=False, default='stock')    # stock

    __table_args__ = (
        UniqueConstraint('ticker', 'year', 'quarter', name='uq_vn30_cf_ticker_year_q'),
    )


class Vn30FinancialRatios(Base):
    """
    VN30 Daily Financial Ratios
    Source: vnstock3 financial ratios API
    Crawler: crawl_vn30_ratios.py
    Schedule: Daily 17:30 VN
    """
    __tablename__ = 'vn30_ratio_daily'

    id                 = Column(Integer, primary_key=True, autoincrement=True)
    ticker             = Column(String(10), nullable=False, index=True)
    date               = Column(Date, nullable=False, index=True)
    pe                 = Column(Float)
    pb                 = Column(Float)
    ps                 = Column(Float)
    roe                = Column(Float)                # Return on equity (%)
    roa                = Column(Float)                # Return on assets (%)
    eps                = Column(Float)                # Earnings per share (VND)
    dividend_yield     = Column(Float)                # %
    market_cap_billion = Column(Float)
    crawl_time         = Column(DateTime, nullable=False)
    source             = Column(Text, nullable=False, default='vnstock3')        # vnstock3
    group_name         = Column(String(20), nullable=False, default='stock')    # stock

    __table_args__ = (
        UniqueConstraint('ticker', 'date', name='uq_vn30_ratios_ticker_date'),
        Index('idx_vn30_ratios_ticker_date', 'ticker', 'date'),
    )


# ======================
# GSO Macro Indicator Tables
# ======================

class VnCpiMonthly(Base):
    """
    Vietnam Consumer Price Index (CPI) - Monthly
    Source: gso.gov.vn
    Crawler: crawl_gso_cpi.py
    Schedule: Monthly ~28th (after GSO release)
    Categories: overall, food, housing, transport, education, health, etc.
    """
    __tablename__ = 'vn_gso_cpi_monthly'

    id         = Column(Integer, primary_key=True, autoincrement=True)
    period     = Column(String(7), nullable=False, index=True)   # YYYY-MM
    category   = Column(String(100), nullable=False)             # 'overall', 'food', 'housing', ...
    cpi_index  = Column(Float)     # Index value (base=100)
    cpi_mom_pct = Column(Float)    # Month-over-month change (%)
    cpi_yoy_pct = Column(Float)    # Year-over-year change (%, compound from MoM)
    crawl_time = Column(DateTime, nullable=False)
    source     = Column(Text, nullable=False, default='gso.gov.vn')      # gso.gov.vn / nso.gov.vn
    group_name = Column(String(20), nullable=False, default='macro')    # macro

    __table_args__ = (
        UniqueConstraint('period', 'category', name='uq_vn_cpi_period_category'),
        Index('idx_vn_cpi_period', 'period'),
    )


class VnPpiMonthly(Base):
    """
    Vietnam Producer Price Index (PPI) - Monthly
    Source: gso.gov.vn
    Crawler: crawl_gso_cpi.py (same script as CPI)
    """
    __tablename__ = 'vn_gso_ppi_monthly'

    id         = Column(Integer, primary_key=True, autoincrement=True)
    period     = Column(String(7), nullable=False, index=True)  # YYYY-MM
    sector     = Column(String(100), nullable=False)
    ppi_index  = Column(Float)
    ppi_mom_pct = Column(Float)
    ppi_yoy_pct = Column(Float)
    crawl_time = Column(DateTime, nullable=False)
    source     = Column(Text, nullable=False, default='gso.gov.vn')      # gso.gov.vn
    group_name = Column(String(20), nullable=False, default='macro')    # macro

    __table_args__ = (
        UniqueConstraint('period', 'sector', name='uq_vn_ppi_period_sector'),
    )


class VnGdpQuarterly(Base):
    """
    Vietnam GDP - Quarterly
    Source: gso.gov.vn
    Crawler: crawl_gso_gdp.py
    Schedule: Quarterly (end of each quarter month)
    """
    __tablename__ = 'vn_gso_gdp_quarterly'

    id              = Column(Integer, primary_key=True, autoincrement=True)
    year            = Column(Integer, nullable=False)
    quarter         = Column(Integer, nullable=False)    # 1-4
    sector          = Column(String(50), nullable=False) # 'total', 'agriculture', 'industry', 'services'
    gdp_billion_vnd = Column(Float)
    growth_yoy_pct  = Column(Float)
    crawl_time      = Column(DateTime, nullable=False)
    source          = Column(Text, nullable=False, default='gso.gov.vn')      # gso.gov.vn
    group_name      = Column(String(20), nullable=False, default='macro')    # macro

    __table_args__ = (
        UniqueConstraint('year', 'quarter', 'sector', name='uq_vn_gdp_year_q_sector'),
    )


class VnTradeMonthly(Base):
    """
    Vietnam Import/Export Trade Data - Monthly
    Source: gso.gov.vn / customs.gov.vn
    Crawler: crawl_gso_trade.py
    Schedule: Monthly ~28th
    """
    __tablename__ = 'vn_gso_trade_monthly'

    id                 = Column(Integer, primary_key=True, autoincrement=True)
    period             = Column(String(7), nullable=False, unique=True, index=True)  # YYYY-MM
    export_billion_usd = Column(Float)
    import_billion_usd = Column(Float)
    trade_balance      = Column(Float)          # export - import
    top_export_markets = Column(JSONB)          # {"US": 12.5, "China": 8.3, ...}
    yoy_export_pct     = Column(Float)
    yoy_import_pct     = Column(Float)
    crawl_time         = Column(DateTime, nullable=False)
    source             = Column(Text, nullable=False, default='gso.gov.vn')      # gso.gov.vn / customs.gov.vn
    group_name         = Column(String(20), nullable=False, default='macro')    # macro


class VnGsoIndustry(Base):
    """
    Vietnam Industrial Production Index (IIP) by Sector - Monthly
    Source: gso.gov.vn - Chỉ số Sản xuất Công nghiệp
    Crawler: crawl_gso_industry.py
    Schedule: Monthly ~25th-28th (after GSO release)
    """
    __tablename__ = 'vn_gso_iip_monthly'

    id          = Column(Integer, primary_key=True, autoincrement=True)
    period      = Column(String(7), nullable=False, index=True)  # YYYY-MM
    sector_name = Column(String(200), nullable=False)
    iip_index   = Column(Float)                                  # Index value
    iip_yoy_pct = Column(Float)                                  # YoY change (%)
    crawl_time  = Column(DateTime, nullable=False)
    source      = Column(Text, nullable=False, default='gso.gov.vn')      # gso.gov.vn
    group_name  = Column(String(20), nullable=False, default='macro')    # macro

    __table_args__ = (
        UniqueConstraint('period', 'sector_name', name='uq_vn_gso_industry_period_sector'),
    )


# ======================
# Data Catalog & Quality Tables
# ======================

class DataCatalog(Base):
    """
    Central registry of all data series in the pipeline.
    Tracks freshness, source, schedule, and lineage.
    """
    __tablename__ = 'data_catalog'

    series_id         = Column(String(80), primary_key=True)
    group_name        = Column(String(50), nullable=False)   # 'macro', 'gso', 'vn30'
    subgroup          = Column(String(50))
    series_name       = Column(String(200), nullable=False)
    source_url        = Column(Text)
    source_file       = Column(String(100))
    target_table      = Column(String(100))
    target_db         = Column(String(50), default='CRAWLING_BOT_DB')
    frequency         = Column(String(20))   # 'daily', 'twice_daily', 'monthly', 'quarterly'
    last_crawl_at     = Column(DateTime)
    last_value_at     = Column(Date)
    expected_lag_days = Column(Integer, default=1)
    is_active         = Column(Boolean, default=True)
    notes             = Column(Text)
    created_at        = Column(DateTime)


class CrawlRunLog(Base):
    """
    Audit log for every crawler run.
    Tracks status, layer used, records processed, errors.
    """
    __tablename__ = 'crawl_run_log'

    id          = Column(Integer, primary_key=True, autoincrement=True)
    series_id   = Column(String(80), index=True)   # FK to data_catalog (not enforced for speed)
    run_at      = Column(DateTime, nullable=False)
    status      = Column(String(20), nullable=False)  # 'success', 'partial', 'failed'
    layer_used  = Column(String(20))                  # 'structured', 'heuristic', 'llm', 'api'
    records_in  = Column(Integer, default=0)
    records_new = Column(Integer, default=0)
    duration_ms = Column(Integer)
    error_msg   = Column(Text)

    __table_args__ = (
        Index('idx_crawl_run_log_run_at', 'run_at'),
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
            ('Vn30OhlcvHist', Vn30OhlcvHist),
            ('Vn30CompanyProfile', Vn30CompanyProfile),
            ('Vn30IncomeStmt', Vn30IncomeStmt),
            ('Vn30BalanceSheet', Vn30BalanceSheet),
            ('Vn30CashFlow', Vn30CashFlow),
            ('Vn30FinancialRatios', Vn30FinancialRatios),
            ('VnCpiMonthly', VnCpiMonthly),
            ('VnPpiMonthly', VnPpiMonthly),
            ('VnGdpQuarterly', VnGdpQuarterly),
            ('VnTradeMonthly', VnTradeMonthly),
            ('VnGsoIndustry', VnGsoIndustry),
            ('DataCatalog', DataCatalog),
            ('CrawlRunLog', CrawlRunLog),
        ]:
            print(f"  - {cls.__tablename__} ({cls.__doc__.strip().split(chr(10))[0]})")
