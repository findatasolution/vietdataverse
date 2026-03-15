# models.py
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, func, JSON, BigInteger
)
from database import Base


# ======================
# Users
# ======================
class User(Base):
    __tablename__ = "users"

    id = Column("user_id", Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    auth0_id = Column(String, unique=True, index=True, nullable=True)
    name = Column(String, nullable=True)
    picture = Column(String, nullable=True)
    email_verified = Column(Boolean, default=False, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    user_level = Column(String(30), default="free", nullable=False, index=True)  # free | premium | premium_developer | admin
    registration_type = Column(String(30), default="google", nullable=False)     # google | anonymous | vdv_internal
    auth0_metadata = Column(JSON, nullable=True)
    is_premium = Column(Boolean, default=False, nullable=False)
    premium_expiry = Column(DateTime, nullable=True)
    api_request_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=True)

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r} user_level={self.user_level} auth0_id={self.auth0_id}>"

    def is_auth0_user(self) -> bool:
        return self.auth0_id is not None


# ======================
# Payment Orders - track PayOS/SePay transactions
# ======================
class PaymentOrder(Base):
    __tablename__ = "payment_orders"

    order_code = Column(BigInteger, primary_key=True)
    user_id = Column(Integer, nullable=False, index=True)
    plan = Column(String(50), nullable=False)   # premium_monthly | premium_yearly | dev_monthly | dev_yearly
    amount = Column(Integer, nullable=False)
    status = Column(String(20), default="pending", nullable=False)  # pending | paid | cancelled
    gateway = Column(String(20), default="payos", nullable=False)   # payos | sepay
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=True)
