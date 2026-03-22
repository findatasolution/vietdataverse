"""Add user_level + registration_type, remove role + business_unit

Revision ID: 002
Revises: 001
Create Date: 2026-03-12

- Đổi tên cột role → user_level (values: free | premium | admin)
- Xóa cột business_unit (liên quan gceo/bugm logic đã bỏ)
- Thêm cột registration_type (google | anonymous | vdv_internal)
"""

from typing import Sequence, Union
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Thêm user_level (map từ role cũ nếu có data; USER_DB hiện đang empty)
    op.execute("""
        ALTER TABLE users
            ADD COLUMN IF NOT EXISTS user_level        VARCHAR(20) NOT NULL DEFAULT 'free',
            ADD COLUMN IF NOT EXISTS registration_type VARCHAR(30) NOT NULL DEFAULT 'google'
    """)

    # 2. Nếu có data cũ: map role → user_level (admin → admin, còn lại → free)
    op.execute("""
        UPDATE users
        SET user_level = CASE
            WHEN is_admin = TRUE THEN 'admin'
            ELSE 'free'
        END
        WHERE user_level = 'free'
    """)

    # 3. Xóa các cột liên quan đến role cũ
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS role")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS business_unit")


def downgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS role          VARCHAR(50) NOT NULL DEFAULT 'user'")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS business_unit VARCHAR(100)")
    op.execute("UPDATE users SET role = CASE WHEN is_admin = TRUE THEN 'admin' ELSE 'user' END")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS user_level")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS registration_type")
