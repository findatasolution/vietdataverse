import os
from sqlalchemy import create_engine
from fastapi import HTTPException

_engine_crawl = None
_engine_global = None
_engine_argus = None
_engine_user = None
_engine_finstock = None
_engine_corp = None

_POOL_KWARGS = dict(pool_pre_ping=True, pool_size=3, max_overflow=5, pool_recycle=300)


def get_engine_user():
    global _engine_user
    if _engine_user is None:
        db_url = os.getenv("USER_DB")
        if not db_url:
            raise ValueError("USER_DB is not set — refusing to fall back to another database")
        _engine_user = create_engine(db_url, **_POOL_KWARGS)
    return _engine_user


def get_engine_crawl():
    global _engine_crawl
    if _engine_crawl is None:
        db_url = os.getenv("CRAWLING_BOT_DB")
        if not db_url:
            raise HTTPException(status_code=500, detail="CRAWLING_BOT_DB not set")
        _engine_crawl = create_engine(db_url, **_POOL_KWARGS)
    return _engine_crawl


def get_engine_global():
    global _engine_global
    if _engine_global is None:
        db_url = os.getenv("GLOBAL_INDICATOR_DB")
        if not db_url:
            raise HTTPException(status_code=500, detail="GLOBAL_INDICATOR_DB not set")
        _engine_global = create_engine(db_url, **_POOL_KWARGS)
    return _engine_global


def get_engine_argus():
    global _engine_argus
    if _engine_argus is None:
        db_url = os.getenv("ARGUS_FINTEL_DB")
        if not db_url:
            raise HTTPException(status_code=500, detail="ARGUS_FINTEL_DB not set")
        _engine_argus = create_engine(db_url, **_POOL_KWARGS)
    return _engine_argus


def get_engine_finstock():
    global _engine_finstock
    if _engine_finstock is None:
        db_url = os.getenv("FINSTOCK_DB")
        if not db_url:
            raise HTTPException(status_code=500, detail="FINSTOCK_DB not set")
        _engine_finstock = create_engine(db_url, **_POOL_KWARGS)
    return _engine_finstock


def get_engine_corp():
    """CRAWLING_CORP_DB — VN30 stock data (price, financials, ratios)."""
    global _engine_corp
    if _engine_corp is None:
        db_url = os.getenv("CRAWLING_CORP_DB")
        if not db_url:
            raise HTTPException(status_code=500, detail="CRAWLING_CORP_DB not set")
        _engine_corp = create_engine(db_url, **_POOL_KWARGS)
    return _engine_corp


_engine_knowledge = None


def get_engine_knowledge():
    """KNOWLEDGE_MARKET_DB — Knowledge Marketplace (sellers, products, credits, purchases)."""
    global _engine_knowledge
    if _engine_knowledge is None:
        db_url = os.getenv("KNOWLEDGE_MARKET_DB")
        if not db_url:
            raise RuntimeError("KNOWLEDGE_MARKET_DB env var not set")
        _engine_knowledge = create_engine(db_url, **_POOL_KWARGS)
    return _engine_knowledge
