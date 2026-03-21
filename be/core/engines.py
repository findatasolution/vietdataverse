import os
from sqlalchemy import create_engine
from fastapi import HTTPException

_engine_crawl = None
_engine_global = None
_engine_argus = None
_engine_user = None
_engine_finstock = None

_POOL_KWARGS = dict(pool_pre_ping=True, pool_size=3, max_overflow=5, pool_recycle=300)


def get_engine_user():
    global _engine_user
    if _engine_user is None:
        db_url = os.getenv("USER_DB") or os.getenv("ARGUS_FINTEL_DB")
        if not db_url:
            raise HTTPException(status_code=500, detail="USER_DB or ARGUS_FINTEL_DB not set")
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
