import bcrypt
from datetime import datetime, timedelta
from jose import JWTError, jwt
import os

# Neon-specific secret key and algorithm
NEON_SECRET_KEY = os.getenv("NEON_SECRET_KEY", "neon_secret_key_for_jwt")
NEON_ALGORITHM = os.getenv("NEON_ALGORITHM", "HS256")
NEON_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("NEON_ACCESS_TOKEN_EXPIRE_MINUTES", "60"))


def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    # Ensure password is bytes and truncate to 72 bytes
    if len(password.encode('utf-8')) > 72:
        password = password[:72]
    
    # Convert to bytes
    password_bytes = password.encode('utf-8')
    
    # Generate salt and hash
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    
    # Return as string
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    # Ensure plain password is bytes and truncate to 72 bytes
    if len(plain_password.encode('utf-8')) > 72:
        plain_password = plain_password[:72]
    
    # Convert to bytes
    plain_password_bytes = plain_password.encode('utf-8')
    hashed_password_bytes = hashed_password.encode('utf-8')
    
    return bcrypt.checkpw(plain_password_bytes, hashed_password_bytes)

def create_access_token(data: dict, expires_delta: timedelta = None):
    """Create a JWT access token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=NEON_ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, NEON_SECRET_KEY, algorithm=NEON_ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> dict:
    """
    Decode a JWT token and return the payload.
    Raises JWTError if the token is invalid.
    """
    payload = jwt.decode(token, NEON_SECRET_KEY, algorithms=[NEON_ALGORITHM])
    return payload
