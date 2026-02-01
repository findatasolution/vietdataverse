# models.py
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, func, JSON
)
from database import Base


# ======================
# Users - Auth0 integrated with role-based access
# ======================
class User(Base):
    __tablename__ = "users"

    id = Column("user_id", Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    # Removed password_hash field - Auth0 users don't have local passwords
    auth0_id = Column(String, unique=True, index=True, nullable=True)
    name = Column(String, nullable=True)
    picture = Column(String, nullable=True)
    email_verified = Column(Boolean, default=False, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    role = Column(String, default="user", nullable=False, index=True)  # user, gceo, bugm
    business_unit = Column(String, nullable=True)  # For BUGM role: APAC, EMEA, Americas
    auth0_metadata = Column(JSON, nullable=True)  # Store additional Auth0 metadata
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=True)

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r} role={self.role} auth0_id={self.auth0_id}>"

    def is_auth0_user(self) -> bool:
        """Check if this user is authenticated via Auth0"""
        return self.auth0_id is not None

    def get_auth0_profile(self) -> dict:
        """Get Auth0 profile information"""
        return {
            "name": self.name,
            "picture": self.picture,
            "email_verified": self.email_verified,
            "auth0_metadata": self.auth0_metadata
        }

    def has_role(self, role: str) -> bool:
        """Check if user has specific role"""
        return self.role == role

    def has_business_unit(self, bu: str) -> bool:
        """Check if user has specific business unit"""
        return self.business_unit == bu
