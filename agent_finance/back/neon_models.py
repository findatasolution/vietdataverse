from sqlalchemy import Column, Integer, String, Boolean, DateTime, text
from sqlalchemy.sql import func
from neon_database import Base

class NeonUser(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    phone = Column(String, nullable=True)
    create_date = Column(DateTime, server_default=func.now(), nullable=False)
    type = Column(String, default="basic", nullable=False)
    membership_level = Column(String, default="free", nullable=False)

    def __repr__(self) -> str:
        return f"<NeonUser id={self.id} email={self.email!r} type={self.type} membership={self.membership_level}>"
