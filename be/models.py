# models.py
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, func
)
from database import Base


# ======================
# Users - Auth0 integrated with role-based access
# ======================
class User(Base):
    __tablename__ = "users"

    id = Column("user_id", Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=True)  # Nullable: Auth0 users don't have local passwords
    auth0_id = Column(String, unique=True, index=True, nullable=True)
    name = Column(String, nullable=True)
    picture = Column(String, nullable=True)
    is_admin = Column(Boolean, default=False, nullable=False)
    role = Column(String, default="user", nullable=False, index=True)  # user, gceo, bugm
    business_unit = Column(String, nullable=True)  # For BUGM role: APAC, EMEA, Americas
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=True)

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r} role={self.role} auth0_id={self.auth0_id}>"
