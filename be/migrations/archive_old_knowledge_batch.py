"""
Archive (unpublish) the old Vietnamese-titled knowledge batch (IDs 6-13).

These 8 records were inserted in an earlier batch with VN-language slugs and
are superseded by the English-slug packs in IDs 20-32. They are being
set to 'unpublished' so they stop appearing in the marketplace.

Slugs being archived:
  tt200-chart-of-accounts-vn
  vn-stock-trader-glossary
  vn-macro-indicators-context
  vn-banking-regulation-schema
  vn-finance-sentiment-lexicon
  vn-credit-risk-scoring-schema
  vn-esg-reporting-framework
  vn-crypto-regulation-protocols

Run with production env vars:
  USER_DB=<production_url> python be/migrations/archive_old_knowledge_batch.py
Or if you use .env:
  python be/migrations/archive_old_knowledge_batch.py
"""
import os, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / ".env")

import psycopg2

OLD_SLUGS = [
    "tt200-chart-of-accounts-vn",
    "vn-stock-trader-glossary",
    "vn-macro-indicators-context",
    "vn-banking-regulation-schema",
    "vn-finance-sentiment-lexicon",
    "vn-credit-risk-scoring-schema",
    "vn-esg-reporting-framework",
    "vn-crypto-regulation-protocols",
]

def main():
    url = os.getenv("USER_DB")
    if not url:
        sys.exit("USER_DB not set")

    conn = psycopg2.connect(url)
    conn.autocommit = False
    cur = conn.cursor()

    # Preview what will be changed
    placeholders = ",".join(["%s"] * len(OLD_SLUGS))
    cur.execute(
        f"SELECT id, slug, status FROM knowledge_products WHERE slug IN ({placeholders})",
        OLD_SLUGS
    )
    rows = cur.fetchall()

    if not rows:
        print("No matching products found — nothing to do.")
        conn.close()
        return

    print(f"Found {len(rows)} products to archive:")
    for r in rows:
        print(f"  id={r[0]:3}  slug={r[1]:<40}  current_status={r[2]}")

    confirm = input("\nArchive these? [y/N] ").strip().lower()
    if confirm != "y":
        print("Aborted.")
        conn.close()
        return

    cur.execute(
        f"""UPDATE knowledge_products
            SET status = 'unpublished', updated_at = NOW()
            WHERE slug IN ({placeholders})""",
        OLD_SLUGS
    )
    updated = cur.rowcount
    conn.commit()
    print(f"Done — {updated} products set to 'unpublished'.")
    conn.close()

if __name__ == "__main__":
    main()
