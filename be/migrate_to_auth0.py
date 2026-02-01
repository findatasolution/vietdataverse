#!/usr/bin/env python3
"""
Migration script to transition from local authentication to Auth0
This script helps migrate existing users to Auth0 integration
"""

import os
import sys
import json
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models import User, Base
from database import engine

def backup_existing_users():
    """Backup existing users before migration"""
    print("🔍 Backing up existing users...")
    
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        users = session.query(User).all()
        backup_data = []
        
        for user in users:
            backup_data.append({
                'id': user.id,
                'email': user.email,
                'password_hash': user.password_hash,
                'auth0_id': user.auth0_id,
                'name': user.name,
                'picture': user.picture,
                'is_admin': user.is_admin,
                'role': user.role,
                'business_unit': user.business_unit,
                'created_at': user.created_at.isoformat(),
                'updated_at': user.updated_at.isoformat() if user.updated_at else None
            })
        
        # Save backup to file
        backup_file = f"user_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(backup_file, 'w') as f:
            json.dump(backup_data, f, indent=2)
        
        print(f"✅ Backup saved to: {backup_file}")
        print(f"📊 Found {len(users)} existing users")
        
        return backup_data
        
    except Exception as e:
        print(f"❌ Error during backup: {e}")
        return []
    finally:
        session.close()

def migrate_users_to_auth0_format():
    """Migrate users to Auth0-only format"""
    print("🔄 Migrating users to Auth0 format...")
    
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Get all users
        users = session.query(User).all()
        migrated_count = 0
        
        for user in users:
            # For users without auth0_id, mark them as needing migration
            if not user.auth0_id:
                print(f"⚠️  User {user.email} needs Auth0 migration - no auth0_id found")
                # Keep password_hash for now, will be removed in next step
            else:
                print(f"✅ User {user.email} already has Auth0 integration")
            
            # Ensure email_verified is set
            if user.email_verified is None:
                user.email_verified = False
            
            migrated_count += 1
        
        session.commit()
        print(f"✅ Migration completed for {migrated_count} users")
        
    except Exception as e:
        print(f"❌ Error during migration: {e}")
        session.rollback()
    finally:
        session.close()

def remove_password_hashes():
    """Remove password hashes from all users (Auth0-only)"""
    print("🔐 Removing password hashes...")
    
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Update all users to remove password_hash
        result = session.execute(
            text("UPDATE users SET password_hash = NULL WHERE password_hash IS NOT NULL")
        )
        
        session.commit()
        print(f"✅ Removed password hashes from {result.rowcount} users")
        
    except Exception as e:
        print(f"❌ Error removing password hashes: {e}")
        session.rollback()
    finally:
        session.close()

def create_migration_report():
    """Create a report of the migration status"""
    print("📋 Creating migration report...")
    
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Count users by type
        total_users = session.query(User).count()
        auth0_users = session.query(User).filter(User.auth0_id.isnot(None)).count()
        local_users = session.query(User).filter(User.auth0_id.is_(None)).count()
        users_with_password = session.query(User).filter(User.password_hash.isnot(None)).count()
        
        report = {
            'migration_date': datetime.now().isoformat(),
            'total_users': total_users,
            'auth0_users': auth0_users,
            'local_users_needing_migration': local_users,
            'users_with_password_hashes': users_with_password,
            'status': 'Auth0 migration in progress'
        }
        
        # Save report
        report_file = f"migration_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"📊 Migration Report:")
        print(f"   Total users: {total_users}")
        print(f"   Auth0 users: {auth0_users}")
        print(f"   Local users needing migration: {local_users}")
        print(f"   Users with password hashes: {users_with_password}")
        print(f"✅ Report saved to: {report_file}")
        
        return report
        
    except Exception as e:
        print(f"❌ Error creating report: {e}")
        return {}
    finally:
        session.close()

def main():
    """Main migration function"""
    print("🚀 Starting Auth0 migration process...")
    print("=" * 50)
    
    # Step 1: Backup existing data
    backup_data = backup_existing_users()
    
    if not backup_data:
        print("❌ No users found or backup failed. Exiting.")
        return
    
    print()
    
    # Step 2: Migrate to Auth0 format
    migrate_users_to_auth0_format()
    print()
    
    # Step 3: Remove password hashes (optional - can be done later)
    remove_password_hashes()
    print()
    
    # Step 4: Create migration report
    report = create_migration_report()
    print()
    
    print("=" * 50)
    print("🎉 Migration process completed!")
    print()
    print("📋 Next steps:")
    print("1. Test the application with Auth0 authentication")
    print("2. Migrate existing users to Auth0 (they'll need to register via Auth0)")
    print("3. Optionally remove password_hash column from database schema")
    print("4. Update frontend to use Auth0 login instead of local login")
    print()
    print("⚠️  Important notes:")
    print("- Existing users will need to register via Auth0")
    print("- You may want to implement a user linking system")
    print("- Consider implementing email verification via Auth0")
    print("- Monitor logs for any authentication issues")

if __name__ == "__main__":
    main()