"""API quota, audit log, call log, users.current_plan

Revision ID: 003
Revises: 002
Create Date: 2026-04-22

Thêm hạ tầng quota/billing-aware cho luồng bán API:
  - users.current_plan      : plan gần nhất được activate (dev_monthly, dev_yearly, ...)
  - api_usage_monthly       : bộ đếm request theo (user_id, quota_month='YYYY-MM' VN TZ)
  - admin_audit_log         : log mọi thay đổi tay từ admin panel
  - api_call_log            : log từng request API (endpoint, status) phục vụ dashboard
"""

from typing import Sequence, Union
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. users.current_plan — cache plan gần nhất để middleware biết quota monthly
    op.execute("""
        ALTER TABLE users
            ADD COLUMN IF NOT EXISTS current_plan VARCHAR(50)
    """)

    # 2. api_usage_monthly — counter reset theo tháng VN timezone
    op.execute("""
        CREATE TABLE IF NOT EXISTS api_usage_monthly (
            id             SERIAL      PRIMARY KEY,
            user_id        INT         NOT NULL,
            quota_month    VARCHAR(7)  NOT NULL,
            request_count  INT         NOT NULL DEFAULT 0,
            updated_at     TIMESTAMP   NOT NULL DEFAULT NOW(),
            UNIQUE (user_id, quota_month)
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_api_usage_month
            ON api_usage_monthly (quota_month)
    """)

    # 3. admin_audit_log — ai đã thay đổi gì ở user nào
    op.execute("""
        CREATE TABLE IF NOT EXISTS admin_audit_log (
            id              SERIAL      PRIMARY KEY,
            admin_user_id   INT         NOT NULL,
            target_user_id  INT,
            action          VARCHAR(80) NOT NULL,
            payload         JSON,
            at              TIMESTAMP   NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_admin_audit_at
            ON admin_audit_log (at DESC)
    """)

    # 4. api_call_log — mỗi request API key dùng endpoint nào (top-endpoints stat)
    op.execute("""
        CREATE TABLE IF NOT EXISTS api_call_log (
            id           SERIAL      PRIMARY KEY,
            user_id      INT         NOT NULL,
            api_key_id   INT,
            endpoint     VARCHAR(120) NOT NULL,
            status_code  SMALLINT    NOT NULL,
            at           TIMESTAMP   NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_api_call_log_at
            ON api_call_log (at DESC)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_api_call_log_user
            ON api_call_log (user_id, at DESC)
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS api_call_log")
    op.execute("DROP TABLE IF EXISTS admin_audit_log")
    op.execute("DROP TABLE IF EXISTS api_usage_monthly")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS current_plan")
