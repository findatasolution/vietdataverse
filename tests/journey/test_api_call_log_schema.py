"""api_call_log must accept a row with no user — the anonymous calls the admin
report is supposed to count.

This guards a schema DRIFT, not application code. Migration 011 declares
`api_call_log.user_id INT` (nullable), but the table predates that migration —
it was created by hand, and `CREATE TABLE IF NOT EXISTS` never alters an
existing table. Production carried `user_id INTEGER NOT NULL`, so every insert
for an anonymous caller raised NotNullViolation and `_log_api_call`'s
`except Exception` swallowed it. Result: zero anonymous rows ever recorded, and
two columns in the admin dashboard ("Public anonymous", "Anonymous / lỗi") that
were structurally always 0 — while the 401s they were meant to count were the
whole point of the report before going to sell.

No application code can detect this: the only symptom is a row that never
arrives. So the test asks the database directly.

Skipped when USER_DB is absent (CI without secrets); run locally or wherever
USER_DB is set. Writes nothing — the probe insert is always rolled back.
"""
import os
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

try:
    from dotenv import load_dotenv
    from sqlalchemy import create_engine, text
    load_dotenv(dotenv_path=ROOT / ".env")
    DB_URL = os.getenv("USER_DB")
except Exception:  # pragma: no cover - dependency missing in a bare env
    DB_URL = None


@unittest.skipUnless(DB_URL, "USER_DB not set — schema check needs the real database")
class ApiCallLogSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(DB_URL)

    def test_user_id_is_nullable(self):
        with self.engine.connect() as conn:
            nullable = conn.execute(text("""
                SELECT is_nullable FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'api_call_log'
                  AND column_name = 'user_id'
            """)).scalar()
        self.assertEqual(
            nullable, "YES",
            "api_call_log.user_id is NOT NULL, so anonymous API calls cannot be "
            "logged at all — see be/migrations/019_api_call_log_nullable_user.sql",
        )

    def test_anonymous_row_can_be_inserted(self):
        """The column check above is the cause; this is the behaviour it breaks.

        Rolled back unconditionally: this must never leave a probe row in a
        table the admin report reads.
        """
        with self.engine.connect() as conn:
            trans = conn.begin()
            try:
                conn.execute(text("""
                    INSERT INTO api_call_log (user_id, api_key_id, endpoint, status_code)
                    VALUES (NULL, NULL, '/__test__/anonymous', 401)
                """))
            finally:
                trans.rollback()


if __name__ == "__main__":
    unittest.main()
