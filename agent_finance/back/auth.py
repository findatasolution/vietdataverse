"""
Auth0 JWT Token Verification
Verifies RS256 tokens issued by Auth0 using JWKS (JSON Web Key Set)
"""

import os
import json
from jose import jwt, JWTError
from urllib.request import urlopen
from functools import lru_cache

AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN")
AUTH0_API_AUDIENCE = os.getenv("AUTH0_API_AUDIENCE", "https://api.nguyenphamdieuhien.online")
AUTH0_ALGORITHMS = ["RS256"]
NAMESPACE = "https://nguyenphamdieuhien.online"


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
