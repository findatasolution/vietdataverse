import os
from datetime import datetime
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

from core.engines import get_engine_user
from auth import get_auth0_user_info, create_local_user_from_auth0, exchange_code_for_tokens
from middleware import authenticate_user
from models import User

router = APIRouter()


def _get_session():
    return sessionmaker(bind=get_engine_user())()


@router.get("/auth/login")
async def auth0_login():
    domain    = os.getenv("AUTH0_DOMAIN")
    client_id = os.getenv("AUTH0_CLIENT_ID")
    callback  = os.getenv("AUTH0_CALLBACK_URL", "https://api.vietdataverse.online/callback")

    if not all([domain, client_id]):
        raise HTTPException(status_code=500, detail="Auth0 configuration missing")

    params = {
        "client_id": client_id,
        "redirect_uri": callback,
        "response_type": "code",
        "scope": "openid profile email",
    }
    return RedirectResponse(url=f"https://{domain}/authorize?{urlencode(params)}")


@router.get("/callback")
async def auth0_callback(request: Request, code: str = None, error: str = None):
    if error:
        raise HTTPException(status_code=400, detail=f"Auth0 error: {error}")
    if not code:
        raise HTTPException(status_code=400, detail="No authorization code provided")

    try:
        tokens    = exchange_code_for_tokens(code)
        id_token  = tokens.get("id_token")
        user_info = get_auth0_user_info(id_token)

        session = _get_session()
        # Tìm theo auth0_id trước
        user = session.query(User).filter_by(auth0_id=user_info["auth0_id"]).first()

        if not user:
            # Thử link với anonymous account có cùng email
            user = session.query(User).filter_by(email=user_info["email"]).first()
            if user and user.auth0_id is None:
                user.auth0_id          = user_info["auth0_id"]
                user.name              = user_info.get("name")
                user.picture           = user_info.get("picture")
                user.email_verified    = user_info.get("email_verified", False)
                user.registration_type = "google"
            else:
                user = User(**create_local_user_from_auth0(user_info))
                session.add(user)
        else:
            user.name           = user_info.get("name")
            user.picture        = user_info.get("picture")
            user.email_verified = user_info.get("email_verified", False)

        session.commit()
        session.close()

        return {
            "message":      "Auth0 login successful",
            "access_token": tokens.get("access_token"),
            "id_token":     id_token,
            "token_type":   "Bearer",
            "expires_in":   tokens.get("expires_in"),
            "user": {
                "email":          user.email,
                "name":           user.name,
                "picture":        user.picture,
                "user_id":        user.id,
                "auth0_id":       user.auth0_id,
                "email_verified": user.email_verified,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/auth/logout")
async def auth0_logout():
    domain     = os.getenv("AUTH0_DOMAIN")
    client_id  = os.getenv("AUTH0_CLIENT_ID")
    logout_url = os.getenv("LOGOUT_URL", "https://vietdataverse.online")

    if not domain:
        raise HTTPException(status_code=500, detail="Auth0 configuration missing")

    params = {"client_id": client_id, "returnTo": logout_url}
    return RedirectResponse(url=f"https://{domain}/v2/logout?{urlencode(params)}")


@router.get("/me")
async def get_current_user_info(request: Request):
    """
    Trả thông tin user hiện tại. Auto-create nếu chưa có trong DB.
    Nếu email trùng với anonymous account (chưa có auth0_id), tự động link lại.
    """
    try:
        await authenticate_user(request)
        user     = request.state.user
        auth0_id = user.get("auth0_id")
        if not auth0_id:
            raise HTTPException(status_code=401, detail="Invalid token: missing auth0_id")

        session = _get_session()
        db_user = session.query(User).filter_by(auth0_id=auth0_id).first()

        if not db_user:
            # Thử link với anonymous account có cùng email
            email   = user.get("email", "")
            db_user = session.query(User).filter_by(email=email).first()

            if db_user and db_user.auth0_id is None:
                # Link anonymous → google
                db_user.auth0_id          = auth0_id
                db_user.name              = user.get("name")
                db_user.picture           = user.get("picture")
                db_user.email_verified    = user.get("email_verified", False)
                db_user.registration_type = "google"
                # Preserve existing premium level — only downgrade if currently 'free'
                if db_user.user_level == "free":
                    db_user.user_level    = user.get("user_level", "free")
                db_user.is_admin          = user.get("is_admin", False)
            else:
                db_user = User(
                    auth0_id          = auth0_id,
                    email             = email,
                    name              = user.get("name"),
                    picture           = user.get("picture"),
                    email_verified    = user.get("email_verified", False),
                    user_level        = user.get("user_level", "free"),
                    registration_type = "google",
                    is_admin          = user.get("is_admin", False),
                )
                session.add(db_user)

            session.commit()
            session.refresh(db_user)

        result = {
            "email":             db_user.email,
            "name":              db_user.name,
            "picture":           db_user.picture,
            "user_id":           db_user.id,
            "user_level":        db_user.user_level,
            "registration_type": db_user.registration_type,
            "is_admin":          db_user.is_admin,
            "auth0_id":          db_user.auth0_id,
            "is_premium":        db_user.is_premium,
            "premium_expiry":    db_user.premium_expiry.isoformat()
                                 if db_user.premium_expiry else None,
            "wallet_balance":    getattr(db_user, "wallet_balance", 0) or 0,
            "created_at":        db_user.created_at.isoformat() if db_user.created_at else None,
            "updated_at":        db_user.updated_at.isoformat() if db_user.updated_at else None,
        }
        session.close()
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/protected")
async def protected_endpoint(request: Request):
    try:
        await authenticate_user(request)
        return {
            "message":   "This is a protected endpoint",
            "user":      request.state.user,
            "timestamp": datetime.now().isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/dashboard")
async def dashboard_data(request: Request):
    try:
        await authenticate_user(request)
        user = request.state.user
        return {
            "user": {
                "email":      user["email"],
                "user_level": user["user_level"],
                "is_admin":   user["is_admin"],
            },
            "dashboard_data": {
                "total_users":     1000,
                "active_sessions": 50,
                "last_login":      datetime.now().isoformat(),
            },
            "timestamp": datetime.now().isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
