"""
One-shot script: set a user as admin by email.
Usage: python be/migrations/run_set_admin.py findatasolution@gmail.com.vn
"""
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / ".env")

import os
from sqlalchemy import create_engine, text

EMAIL = sys.argv[1] if len(sys.argv) > 1 else "findatasolution@gmail.com.vn"

engine = create_engine(os.environ["USER_DB"])
with engine.begin() as conn:
    result = conn.execute(text("""
        UPDATE users
        SET is_admin = TRUE, user_level = 'admin', updated_at = NOW()
        WHERE email = :email
        RETURNING user_id, email, user_level, is_admin
    """), {"email": EMAIL}).fetchone()

    if result:
        print(f"OK — user_id={result[0]} email={result[1]} level={result[2]} is_admin={result[3]}")
    else:
        print(f"NOT FOUND — không tìm thấy user với email: {EMAIL}")
        print("User chưa đăng ký? Họ cần đăng nhập qua Auth0 ít nhất 1 lần trước.")
