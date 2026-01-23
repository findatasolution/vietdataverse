from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from jose import JWTError, jwt
import os
from datetime import datetime

# Import the auth functions
from neon_auth import decode_access_token

async def authenticate_user(request: Request):
    """
    Middleware to authenticate users based on JWT token
    """
    # Skip authentication for public endpoints
    public_endpoints = ['/api/register', '/api/login', '/api/docs', '/api/openapi.json']
    
    if request.url.path in public_endpoints:
        return None
    
    # Check for authorization header
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = auth_header.split(' ')[1]
    
    try:
        # Decode and verify the token
        payload = decode_access_token(token)
        
        # Check if token is expired
        if 'exp' in payload:
            exp_time = datetime.fromtimestamp(payload['exp'])
            if exp_time < datetime.utcnow():
                raise HTTPException(
                    status_code=401,
                    detail="Token has expired",
                    headers={"WWW-Authenticate": "Bearer"},
                )
        
        # Add user info to request state
        request.state.user = {
            'email': payload.get('sub'),
            'user_id': payload.get('user_id'),
            'type': payload.get('type', 'basic'),
            'membership_level': payload.get('membership_level', 'free')
        }
        
        return payload
        
    except JWTError as e:
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail="Authentication error",
        )

def get_current_user(request: Request):
    """
    Helper function to get current user from request state
    """
    if not hasattr(request.state, 'user'):
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
        )
    return request.state.user

def require_auth(request: Request):
    """
    Decorator to require authentication for endpoints
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            await authenticate_user(request)
            return await func(*args, **kwargs)
        return wrapper
    return decorator
