from back.database import SessionLocal, engine, Base
from back.models import User
from auth import hash_password
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_default_users():
    """Create default users for GCEO and BUGM roles"""

    # Create tables if they don't exist
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()

    try:
        # Define default users
        default_users = [
            {
                "email": "gceo@example.com",
                "password": "gceo123",
                "role": "gceo",
                "is_admin": True
            },
            {
                "email": "apac_gm@example.com",
                "password": "apac123",
                "role": "bugm",
                "is_admin": False
            },
            {
                "email": "emea_gm@example.com",
                "password": "emea123",
                "role": "bugm",
                "is_admin": False
            },
            {
                "email": "americas_gm@example.com",
                "password": "americas123",
                "role": "bugm",
                "is_admin": False
            }
        ]

        for user_data in default_users:
            # Check if user already exists
            existing_user = db.query(User).filter(User.email == user_data["email"]).first()

            if existing_user:
                # Update existing user
                existing_user.role = user_data["role"]
                existing_user.is_admin = user_data["is_admin"]
                existing_user.password_hash = hash_password(user_data["password"])
                logger.info(f"✓ Updated user: {user_data['email']} (role: {user_data['role']})")
            else:
                # Create new user
                new_user = User(
                    email=user_data["email"],
                    password_hash=hash_password(user_data["password"]),
                    role=user_data["role"],
                    is_admin=user_data["is_admin"]
                )
                db.add(new_user)
                logger.info(f"✓ Created user: {user_data['email']} (role: {user_data['role']})")

        db.commit()

        logger.info("\n" + "="*60)
        logger.info("DEFAULT USERS CREATED/UPDATED")
        logger.info("="*60)
        logger.info("\nGroup CEO (Strategic View - All BUs):")
        logger.info("  Email: gceo@example.com")
        logger.info("  Password: gceo123")
        logger.info("  Role: GCEO")
        logger.info("  Access: Aggregated view of all business units\n")

        logger.info("BU General Managers (Detailed View - Assigned BU):")
        logger.info("  APAC GM:")
        logger.info("    Email: apac_gm@example.com")
        logger.info("    Password: apac123")
        logger.info("    Role: BUGM")
        logger.info("    BU: APAC\n")

        logger.info("  EMEA GM:")
        logger.info("    Email: emea_gm@example.com")
        logger.info("    Password: emea123")
        logger.info("    Role: BUGM")
        logger.info("    BU: EMEA\n")

        logger.info("  Americas GM:")
        logger.info("    Email: americas_gm@example.com")
        logger.info("    Password: americas123")
        logger.info("    Role: BUGM")
        logger.info("    BU: Americas\n")

        logger.info("="*60)
        logger.info("IMPORTANT: Change these passwords in production!")
        logger.info("="*60)

    except Exception as e:
        logger.error(f"Error creating users: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    create_default_users()
