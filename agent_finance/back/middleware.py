from fastapi import Request, HTTPException
from jose import JWTError

from auth import verify_auth0_token, get_user_role, get_user_business_unit, get_user_is_admin, NAMESPACE


async def authenticate_user(request: Request):
    """
    Middleware to authenticate users via Auth0 JWT (RS256 verified by JWKS)
    """
    # Skip authentication for public endpoints
    public_endpoints = [
        '/api/docs', '/api/openapi.json',
        # Public data API endpoints
        '/api/v1/gold', '/api/v1/silver', '/api/v1/sbv-interbank',
        '/api/v1/termdepo', '/api/v1/global-macro', '/api/v1/gold/types',
        '/api/v1/termdepo/banks', '/api/v1/gold-analysis',
    ]

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
        payload = verify_auth0_token(token)

        # Populate request.state.user from Auth0 token claims
        request.state.user = {
            'auth0_id': payload.get('sub'),
            'email': payload.get(f'{NAMESPACE}/email', payload.get('sub')),
            'role': get_user_role(payload),
            'business_unit': get_user_business_unit(payload),
            'is_admin': get_user_is_admin(payload),
        }

        return payload

    except JWTError:
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Authentication error",
        )


def get_current_user(request: Request):
    """Helper function to get current user from request state"""
    if not hasattr(request.state, 'user'):
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
        )
    return request.state.user
