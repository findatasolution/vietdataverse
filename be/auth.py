"""
Auth0 JWT Token Verification
Auth0-only authentication functions for VietDataverse API
"""

import os
import json
from jose import jwt, JWTError
from urllib.request import urlopen
from functools import lru_cache

# Auth0 Configuration
AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN")
AUTH0_CLIENT_ID = os.getenv("AUTH0_CLIENT_ID")
AUTH0_CLIENT_SECRET = os.getenv("AUTH0_CLIENT_SECRET")
AUTH0_API_AUDIENCE = os.getenv("AUTH0_API_AUDIENCE")
AUTH0_ALGORITHMS = ["RS256"]
AUTH0_CALLBACK_URL = os.getenv("AUTH0_CALLBACK_URL")
LOGOUT_URL = os.getenv("LOGOUT_URL")
NAMESPACE = "https://vietdataverse.online"


@lru_cache(maxsize=1)
def get_jwks():
    """Fetch and cache Auth0 JWKS (JSON Web Key Set)"""
    jwks_url = f"https://{AUTH0_DOMAIN}/.well-known/jwks.json"
    with urlopen(jwks_url) as response:
        return json.loads(response.read())


def verify_auth0_token(token: str) -> dict:
    """
    Verify an Auth0 JWT access token using JWKS.
    Returns the decoded payload if valid.
    Raises JWTError if invalid.
    """
    jwks = get_jwks()
    unverified_header = jwt.get_unverified_header(token)

    # Find the matching RSA key by kid
    rsa_key = {}
    for key in jwks["keys"]:
        if key["kid"] == unverified_header.get("kid"):
            rsa_key = {
                "kty": key["kty"],
                "kid": key["kid"],
                "use": key["use"],
                "n": key["n"],
                "e": key["e"],
            }
            break

    if not rsa_key:
        raise JWTError("Unable to find appropriate signing key")

    payload = jwt.decode(
        token,
        rsa_key,
        algorithms=AUTH0_ALGORITHMS,
        audience=AUTH0_API_AUDIENCE,
        issuer=f"https://{AUTH0_DOMAIN}/",
    )

    return payload


def get_user_role(payload: dict) -> str:
    """Extract role from Auth0 token custom claims"""
    return payload.get(f"{NAMESPACE}/role", "user")


def get_user_business_unit(payload: dict):
    """Extract business unit from Auth0 token custom claims"""
    return payload.get(f"{NAMESPACE}/business_unit", None)


def get_user_is_admin(payload: dict) -> bool:
    """Check if user is admin from Auth0 token custom claims"""
    return payload.get(f"{NAMESPACE}/is_admin", False)


def get_auth0_user_info(token: str) -> dict:
    """
    Get user information from Auth0 ID token.
    Returns user profile information.
    """
    try:
        # Decode the ID token to get user info
        user_info = jwt.decode(
            token,
            options={"verify_signature": False},  # ID token is already verified
            audience=AUTH0_CLIENT_ID
        )
        
        return {
            "auth0_id": user_info.get("sub"),
            "email": user_info.get("email"),
            "name": user_info.get("name"),
            "picture": user_info.get("picture"),
            "email_verified": user_info.get("email_verified", False),
            "nickname": user_info.get("nickname"),
            "locale": user_info.get("locale")
        }
    except JWTError as e:
        raise JWTError(f"Failed to decode Auth0 user info: {str(e)}")


def create_local_user_from_auth0(auth0_info: dict) -> dict:
    """
    Create local user data structure from Auth0 user info.
    Returns user data ready for database insertion.
    """
    return {
        "auth0_id": auth0_info["auth0_id"],
        "email": auth0_info["email"],
        "name": auth0_info.get("name"),
        "picture": auth0_info.get("picture"),
        "email_verified": auth0_info.get("email_verified", False),
        "role": "user",  # Default role
        "is_admin": False,  # Default admin status
        "auth0_metadata": {
            "nickname": auth0_info.get("nickname"),
            "locale": auth0_info.get("locale"),
            "created_at": auth0_info.get("created_at")
        }
    }


def get_auth0_login_url(state: str = None) -> str:
    """
    Generate Auth0 login URL with proper parameters.
    Returns the complete login URL.
    """
    import urllib.parse
    
    params = {
        "client_id": AUTH0_CLIENT_ID,
        "redirect_uri": AUTH0_CALLBACK_URL,
        "response_type": "code",
        "scope": "openid profile email",
        "audience": AUTH0_API_AUDIENCE
    }
    
    if state:
        params["state"] = state
    
    return f"https://{AUTH0_DOMAIN}/authorize?{urllib.parse.urlencode(params)}"


def get_auth0_logout_url(return_to: str = None) -> str:
    """
    Generate Auth0 logout URL.
    Returns the complete logout URL.
    """
    import urllib.parse
    
    logout_url = f"https://{AUTH0_DOMAIN}/v2/logout"
    
    params = {
        "client_id": AUTH0_CLIENT_ID
    }
    
    if return_to:
        params["returnTo"] = return_to
    else:
        params["returnTo"] = LOGOUT_URL
    
    return f"{logout_url}?{urllib.parse.urlencode(params)}"


def exchange_code_for_tokens(code: str) -> dict:
    """
    Exchange authorization code for tokens.
    Returns access_token, id_token, and refresh_token.
    """
    import requests
    
    token_url = f"https://{AUTH0_DOMAIN}/oauth/token"
    token_data = {
        "grant_type": "authorization_code",
        "client_id": AUTH0_CLIENT_ID,
        "client_secret": AUTH0_CLIENT_SECRET,
        "code": code,
        "redirect_uri": AUTH0_CALLBACK_URL
    }
    
    response = requests.post(token_url, json=token_data)
    
    if response.status_code != 200:
        raise JWTError(f"Failed to exchange code for tokens: {response.text}")
    
    return response.json()
