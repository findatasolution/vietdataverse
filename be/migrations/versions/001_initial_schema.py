"""Initial schema: users, payment_orders, user_interest

Revision ID: 001
Revises:
Create Date: 2026-03-12

Dùng IF NOT EXISTS để an toàn với DB đã tồn tại (brownfield).
"""

from typing import Sequence, Union
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id        SERIAL          PRIMARY KEY,
            email          VARCHAR(255)    UNIQUE NOT NULL,
            auth0_id       VARCHAR(255)    UNIQUE,
            name           VARCHAR(255),
            picture        TEXT,
            email_verified BOOLEAN         NOT NULL DEFAULT FALSE,
            is_admin       BOOLEAN         NOT NULL DEFAULT FALSE,
            role           VARCHAR(50)     NOT NULL DEFAULT 'user',
            business_unit  VARCHAR(100),
            auth0_metadata JSONB,
            is_premium     BOOLEAN         NOT NULL DEFAULT FALSE,
            premium_expiry TIMESTAMP,
            created_at     TIMESTAMP       NOT NULL DEFAULT NOW(),
            updated_at     TIMESTAMP                DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS payment_orders (
            order_code  BIGINT      PRIMARY KEY,
            user_id     INT         NOT NULL,
            plan        VARCHAR(50) NOT NULL,
            amount      INT         NOT NULL,
            status      VARCHAR(20) NOT NULL DEFAULT 'pending',
            gateway     VARCHAR(20) NOT NULL DEFAULT 'payos',
            created_at  TIMESTAMP   NOT NULL DEFAULT NOW(),
            updated_at  TIMESTAMP            DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS user_interest (
            id            SERIAL       PRIMARY KEY,
            fingerprint   VARCHAR(64)  NOT NULL,
            interest_type VARCHAR(64)  NOT NULL,
            source        VARCHAR(32),
            user_agent    VARCHAR(512),
            language      VARCHAR(16),
            created_at    TIMESTAMP    DEFAULT NOW()
        )
    """)

    # Ensure columns added later via hotfix migrations also exist
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_premium     BOOLEAN   NOT NULL DEFAULT FALSE")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS premium_expiry TIMESTAMP")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS user_interest")
    op.execute("DROP TABLE IF EXISTS payment_orders")
    op.execute("DROP TABLE IF EXISTS users")
