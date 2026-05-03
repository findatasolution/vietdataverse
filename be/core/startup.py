import os
import logging
from sqlalchemy import create_engine, text

logger = logging.getLogger(__name__)


def migrate_crawl_db():
    """Ensure vn_macro_fxrate_daily has all required columns (idempotent).

    CRAWLING_BOT_DB không được quản lý bởi Alembic (do crawler tự maintain),
    nên ALTER TABLE vẫn cần chạy thủ công ở đây.
    """
    db_url = os.getenv("CRAWLING_BOT_DB")
    if not db_url:
        return
    try:
        eng = create_engine(db_url, pool_pre_ping=True)
        with eng.connect() as conn:
            for col, definition in [
                ("type",         "VARCHAR(20) NOT NULL DEFAULT 'USD'"),
                ("source",       "VARCHAR(20) NOT NULL DEFAULT 'Crawl'"),
                ("bank",         "VARCHAR(10) DEFAULT 'SBV'"),
                ("buy_transfer", "FLOAT"),
                ("buy_cash",     "FLOAT"),
                ("sell_rate",    "FLOAT"),
            ]:
                try:
                    conn.execute(text(f"ALTER TABLE vn_macro_fxrate_daily ADD COLUMN IF NOT EXISTS {col} {definition}"))
                    conn.commit()
                except Exception:
                    conn.rollback()
        eng.dispose()
    except Exception as e:
        logger.warning(f"[startup] crawl DB migration warning: {e}")

# migrate_user_db() đã được thay thế bởi Alembic migration 001_initial_schema.
# Schema của USER_DB (users, payment_orders, user_interest) được quản lý
# hoàn toàn bởi: alembic upgrade head (chạy trong buildCommand của render.yaml).
