#!/usr/bin/env python3
"""
Database migration script for Neon user table
This script creates the users table on Neon console
"""

import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
import logging

# Add the back directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from neon_database import engine, Base
from neon_models import NeonUser

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_users_table():
    """Create the users table on Neon database"""
    try:
        # Create all tables defined in Base
        Base.metadata.create_all(bind=engine)
        logger.info("Users table created successfully on Neon database")
        
        # Verify table creation
        with engine.connect() as conn:
            result = conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'users'"))
            table_exists = result.fetchone()
            
            if table_exists:
                logger.info("✓ Users table verified in database")
                
                # Show table structure
                result = conn.execute(text("SELECT column_name, data_type, is_nullable FROM information_schema.columns WHERE table_name = 'users' ORDER BY ordinal_position"))
                columns = result.fetchall()
                logger.info("Table structure:")
                for col in columns:
                    logger.info(f"  - {col[0]}: {col[1]} (nullable: {col[2]})")
                
                return True
            else:
                logger.error("Users table not found after creation")
                return False
                
    except SQLAlchemyError as e:
        logger.error(f"Database error: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return False

def test_connection():
    """Test connection to Neon database"""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.fetchone()
            logger.info(f"Connected to PostgreSQL: {version[0]}")
            return True
    except Exception as e:
        logger.error(f"Connection test failed: {e}")
        return False

def main():
    """Main migration function"""
    logger.info("Starting Neon database migration...")
    
    # Test connection first
    if not test_connection():
        logger.error("Cannot connect to Neon database. Please check your NEON_DB_URL environment variable.")
        sys.exit(1)
    
    # Create table
    if create_users_table():
        logger.info("Migration completed successfully!")
        print("\n" + "="*50)
        print("NEON USER TABLE CREATED SUCCESSFULLY!")
        print("="*50)
        print("Table: users")
        print("Columns:")
        print("  - id (Integer, Primary Key, Auto Increment)")
        print("  - email (String, Unique, Not Null)")
        print("  - password_hash (String, Not Null)")
        print("  - phone (String, Nullable)")
        print("  - create_date (DateTime, Default: Now)")
        print("  - type (String, Default: 'basic')")
        print("  - membership_level (String, Default: 'free')")
        print("="*50)
    else:
        logger.error("Migration failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()
