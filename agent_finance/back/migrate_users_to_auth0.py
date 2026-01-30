"""
One-time migration script: Import existing Neon DB users to Auth0

Prerequisites:
  1. Auth0 Management API token with these scopes:
     - create:users, read:users, update:users
  2. Auth0 Database Connection name (e.g., "Username-Password-Authentication")
  3. Environment variables set in .env:
     - CRAWLING_BOT_DB (Neon DB URL)
     - AUTH0_DOMAIN (e.g., "your-tenant.auth0.com")
     - AUTH0_MGMT_TOKEN (Management API access token)
     - AUTH0_DB_CONNECTION (Database Connection name)

Usage:
  cd agent_finance
  python -m back.migrate_users_to_auth0
"""

import os
import sys
import json
import logging
import requests
from pathlib import Path

# Load environment
from dotenv import load_dotenv
project_root = Path(__file__).resolve().parent.parent.parent
env_path = project_root / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    load_dotenv()

from back.database import SessionLocal
from back.models import User

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Auth0 config
AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN")
AUTH0_MGMT_TOKEN = os.getenv("AUTH0_MGMT_TOKEN")
AUTH0_DB_CONNECTION = os.getenv("AUTH0_DB_CONNECTION", "Username-Password-Authentication")

# Business unit mapping from old hardcoded assignment
LEGACY_BU_ASSIGNMENT = {
    "apac_gm@example.com": "APAC",
    "emea_gm@example.com": "EMEA",
    "americas_gm@example.com": "Americas",
}


def get_all_users():
    """Fetch all users from Neon DB"""
    db = SessionLocal()
    try:
        users = db.query(User).all()
        logger.info(f"Found {len(users)} users in Neon DB")
        return users
    finally:
        db.close()


def create_auth0_user(user):
    """Create a single user in Auth0 via Management API"""
    url = f"https://{AUTH0_DOMAIN}/api/v2/users"
    headers = {
        "Authorization": f"Bearer {AUTH0_MGMT_TOKEN}",
        "Content-Type": "application/json",
    }

    # Determine business_unit from DB field or legacy mapping
    business_unit = user.business_unit or LEGACY_BU_ASSIGNMENT.get(user.email)

    payload = {
        "connection": AUTH0_DB_CONNECTION,
        "email": user.email,
        "email_verified": True,  # Trust existing users
        "app_metadata": {
            "role": user.role or "user",
            "is_admin": user.is_admin or False,
        },
    }

    if business_unit:
        payload["app_metadata"]["business_unit"] = business_unit

    # If user has a bcrypt password hash, import it directly
    # Auth0 supports bcrypt hash import via custom_password_hash
    if user.password_hash and user.password_hash.startswith("$2"):
        payload["custom_password_hash"] = {
            "algorithm": "bcrypt",
            "hash": {
                "value": user.password_hash,
            },
        }
    else:
        # Auth0-only users (e.g., Google OAuth) — create without password
        # They'll use social login or password reset
        payload["password"] = os.urandom(32).hex()  # Random password, won't be used

    resp = requests.post(url, headers=headers, json=payload)

    if resp.status_code == 201:
        auth0_user = resp.json()
        logger.info(f"  Created: {user.email} → {auth0_user['user_id']}")
        return auth0_user["user_id"]
    elif resp.status_code == 409:
        logger.warning(f"  Already exists: {user.email}")
        # Try to find existing user and update app_metadata
        return update_existing_auth0_user(user, business_unit)
    else:
        logger.error(f"  FAILED: {user.email} — {resp.status_code}: {resp.text}")
        return None


def update_existing_auth0_user(user, business_unit):
    """Update app_metadata for an existing Auth0 user"""
    # Search for user by email
    search_url = f"https://{AUTH0_DOMAIN}/api/v2/users-by-email"
    headers = {
        "Authorization": f"Bearer {AUTH0_MGMT_TOKEN}",
    }
    resp = requests.get(search_url, headers=headers, params={"email": user.email})

    if resp.status_code != 200 or not resp.json():
        logger.error(f"  Could not find existing Auth0 user: {user.email}")
        return None

    auth0_user = resp.json()[0]
    auth0_id = auth0_user["user_id"]

    # Update app_metadata
    update_url = f"https://{AUTH0_DOMAIN}/api/v2/users/{auth0_id}"
    metadata = {
        "role": user.role or "user",
        "is_admin": user.is_admin or False,
    }
    if business_unit:
        metadata["business_unit"] = business_unit

    resp = requests.patch(
        update_url,
        headers={**headers, "Content-Type": "application/json"},
        json={"app_metadata": metadata},
    )

    if resp.status_code == 200:
        logger.info(f"  Updated metadata: {user.email} → {auth0_id}")
        return auth0_id
    else:
        logger.error(f"  Failed to update: {user.email} — {resp.status_code}: {resp.text}")
        return None


def update_neon_auth0_id(user_id, auth0_id):
    """Update Neon DB user with their Auth0 ID"""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.auth0_id = auth0_id
            db.commit()
            logger.info(f"  DB updated: user_id={user_id} → auth0_id={auth0_id}")
    except Exception as e:
        logger.error(f"  DB update failed: {e}")
        db.rollback()
    finally:
        db.close()


def migrate():
    """Main migration function"""
    if not AUTH0_DOMAIN:
        logger.error("AUTH0_DOMAIN not set. Add it to .env")
        sys.exit(1)
    if not AUTH0_MGMT_TOKEN:
        logger.error("AUTH0_MGMT_TOKEN not set. Get one from Auth0 Dashboard > APIs > Auth0 Management API > Test")
        sys.exit(1)

    logger.info("=" * 60)
    logger.info("MIGRATING USERS FROM NEON DB TO AUTH0")
    logger.info(f"Auth0 Domain: {AUTH0_DOMAIN}")
    logger.info(f"DB Connection: {AUTH0_DB_CONNECTION}")
    logger.info("=" * 60)

    users = get_all_users()
    if not users:
        logger.info("No users to migrate.")
        return

    success = 0
    failed = 0

    for user in users:
        logger.info(f"\nMigrating: {user.email} (role={user.role}, admin={user.is_admin})")

        # Skip if already has auth0_id
        if user.auth0_id:
            logger.info(f"  Skipped: already has auth0_id={user.auth0_id}")
            success += 1
            continue

        auth0_id = create_auth0_user(user)
        if auth0_id:
            update_neon_auth0_id(user.id, auth0_id)
            success += 1
        else:
            failed += 1

    logger.info("\n" + "=" * 60)
    logger.info(f"MIGRATION COMPLETE: {success} success, {failed} failed out of {len(users)} total")
    logger.info("=" * 60)

    if failed > 0:
        logger.warning("Some users failed to migrate. Check errors above and retry.")


if __name__ == "__main__":
    migrate()
