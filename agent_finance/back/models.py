# models.py
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, func
)
from database import Base


# ======================
# Users - Simplified Structure with Role-Based Access
# ======================
class User(Base):
    __tablename__ = "users"

    id = Column("user_id", Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=True)  # Optional for Auth0 users
    auth0_id = Column(String, unique=True, index=True, nullable=True)  # Auth0 user ID
    name = Column(String, nullable=True)  # User's display name
    picture = Column(String, nullable=True)  # Avatar URL
    is_admin = Column(Boolean, default=False, nullable=False)
    role = Column(String, default="user", nullable=False, index=True)  # user, admin, etc.
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r} auth0_id={self.auth0_id!r} role={self.role}>"
