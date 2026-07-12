from datetime import datetime, timedelta, timezone
import hashlib
import secrets
from typing import Any

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette import status

from app.core.config import settings
from app.core.errors import AppError
from app.core.time import utc8_now
from app.db.models.core import StaffUser, User
from app.db.session import get_db


password_context = PasswordHash.recommended()
bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return password_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return password_context.verify(password, password_hash)
    except Exception:
        return False


def create_access_token(subject: str, token_type: str, extra: dict[str, Any] | None = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    payload: dict[str, Any] = {"sub": subject, "type": token_type, "exp": expire}
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def refresh_token_expires_at() -> datetime:
    return utc8_now() + timedelta(days=settings.refresh_token_expire_days)


def decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise AppError("AUTH_INVALID_TOKEN", "token 无效", status.HTTP_401_UNAUTHORIZED) from exc


def require_token(credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)) -> dict[str, Any]:
    if credentials is None:
        raise AppError("AUTH_INVALID_TOKEN", "缺少认证 token", status.HTTP_401_UNAUTHORIZED)
    return decode_token(credentials.credentials)


def require_app_user(payload: dict[str, Any] = Depends(require_token), db: Session = Depends(get_db)) -> dict[str, Any]:
    if payload.get("type") != "app":
        raise AppError("AUTH_FORBIDDEN", "不是客户 token", status.HTTP_403_FORBIDDEN)
    user_id = payload.get("user_id")
    if not user_id:
        raise AppError("AUTH_INVALID_TOKEN", "token 缺少用户信息", status.HTTP_401_UNAUTHORIZED)
    user = db.scalar(select(User).where(User.id == int(user_id)))
    if user is None or user.status != "active":
        raise AppError("AUTH_FORBIDDEN", "客户账号不可用", status.HTTP_403_FORBIDDEN)
    payload["user"] = user
    return payload


def require_admin(payload: dict[str, Any] = Depends(require_token), db: Session = Depends(get_db)) -> dict[str, Any]:
    if payload.get("type") != "admin":
        raise AppError("AUTH_FORBIDDEN", "不是管理员 token", status.HTTP_403_FORBIDDEN)
    staff_user_id = payload.get("staff_user_id")
    if not staff_user_id:
        raise AppError("AUTH_INVALID_TOKEN", "token 缺少管理员信息", status.HTTP_401_UNAUTHORIZED)
    staff_user = db.scalar(select(StaffUser).where(StaffUser.id == int(staff_user_id)))
    if staff_user is None or staff_user.status != "active":
        raise AppError("AUTH_FORBIDDEN", "管理员账号不可用", status.HTTP_403_FORBIDDEN)
    payload["staff_user"] = staff_user
    return payload
