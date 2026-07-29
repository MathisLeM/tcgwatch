"""Authentication — custom JWT in an httpOnly cookie (mirrors Vigilyx).

Endpoints: POST /auth/signup, POST /auth/login, POST /auth/logout, GET /auth/me.
The `get_current_user` dependency is reused by every protected router.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.config import settings
from api.database import get_db
from api.limiter import limiter
from api.models.user import User
from api.schemas import SignupRequest, UserOut

router = APIRouter()


# ── Auth dependency ─────────────────────────────────────────────────────────
class CurrentUser(BaseModel):
    user_id: int
    email: str
    is_admin: bool


def get_current_user(request: Request) -> CurrentUser:
    """Decode/validate the JWT from the httpOnly access_token cookie."""
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return CurrentUser(
        user_id=int(payload["sub"]),
        email=payload["email"],
        is_admin=payload.get("is_admin", False),
    )


# ── Helpers ─────────────────────────────────────────────────────────────────
def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(data: dict) -> str:
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def _set_auth_cookie(response: Response, token: str) -> None:
    # Prod: frontend (Vercel) and API (Railway) are cross-site -> SameSite=None; Secure.
    # Dev: SameSite=Lax so the cookie persists over plain HTTP.
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=settings.is_production,
        samesite="none" if settings.is_production else "lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


def _issue(response: Response, user: User) -> UserOut:
    token = create_access_token(
        {"sub": str(user.id), "email": user.email, "is_admin": user.is_admin}
    )
    _set_auth_cookie(response, token)
    return UserOut(id=user.id, email=user.email, is_admin=user.is_admin)


# ── Endpoints ───────────────────────────────────────────────────────────────
@router.post("/signup", response_model=UserOut)
@limiter.limit("5/minute")
def signup(
    request: Request,
    response: Response,
    body: SignupRequest,
    db: Session = Depends(get_db),
):
    if not settings.ALLOW_PUBLIC_SIGNUP:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Les inscriptions sont fermées (alpha sur invitation).",
        )
    if len(body.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(email=body.email, hashed_password=hash_password(body.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return _issue(response, user)


@router.post("/login", response_model=UserOut)
@limiter.limit("10/minute")
def login(
    request: Request,
    response: Response,
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == form.username).first()
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")
    return _issue(response, user)


@router.post("/logout", status_code=204)
def logout(response: Response):
    response.delete_cookie(
        "access_token",
        samesite="none" if settings.is_production else "lax",
        secure=settings.is_production,
    )


@router.get("/me", response_model=UserOut)
def me(current_user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    user: Optional[User] = db.get(User, current_user.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserOut(id=user.id, email=user.email, is_admin=user.is_admin)
