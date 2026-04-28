"""
Shared crawl logging helper.
All crawlers import this to log run results into crawl_run_log
and update data_catalog.last_crawl_at / last_value_at.
"""

import os
from datetime import datetime, date
from sqlalchemy import create_engine, text
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / 'be' / '.env')
except Exception:
    pass


def _get_engine():
    db_url = os.getenv('CRAWLING_BOT_DB')
    if not db_url:
        return None
    try:
        return create_engine(db_url, pool_pre_ping=True, pool_size=1, max_overflow=2)
    except Exception:
        return None


def log_crawl_run(
    series_id: str,
    status: str,                # 'success' | 'partial' | 'failed'
    records_in: int = 0,
    records_new: int = 0,
    duration_ms: int = 0,
    layer_used: str = None,     # 'api' | 'structured' | 'heuristic' | 'llm'
    error_msg: str = None,
    last_value_at: date = None,
):
    """
    Insert one row into crawl_run_log and update data_catalog timestamps.
    Silent on failure — never block the crawler.
    """
    engine = _get_engine()
    if not engine:
        return

    run_at = datetime.now()
    try:
        with engine.connect() as conn:
            # Insert log row
            conn.execute(text("""
                INSERT INTO crawl_run_log
                    (series_id, run_at, status, layer_used, records_in, records_new, duration_ms, error_msg)
                VALUES
                    (:series_id, :run_at, :status, :layer_used, :records_in, :records_new, :duration_ms, :error_msg)
            """), {
                'series_id': series_id,
                'run_at': run_at,
                'status': status,
                'layer_used': layer_used,
                'records_in': records_in,
                'records_new': records_new,
                'duration_ms': duration_ms,
                'error_msg': str(error_msg)[:500] if error_msg else None,
            })

            # Update catalog freshness
            conn.execute(text("""
                UPDATE data_catalog
                SET last_crawl_at = :run_at,
                    last_value_at = COALESCE(:last_value_at, last_value_at)
                WHERE series_id = :series_id
            """), {
                'series_id': series_id,
                'run_at': run_at,
                'last_value_at': last_value_at,
            })

            conn.commit()
    except Exception as e:
        # Silent — logging should never crash the crawler
        print(f"  [crawl_log] Warning: could not write log: {e}")
    finally:
        engine.dispose()
