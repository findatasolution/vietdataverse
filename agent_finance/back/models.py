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
    password_hash = Column(String, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    role = Column(String, default="bugm", nullable=False, index=True)  # gceo or bugm
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r} role={self.role}>"
