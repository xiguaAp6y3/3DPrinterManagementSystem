from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from starlette import status

from app.core.config import settings
from app.core.errors import AppError


password_context = PasswordHash.recommended()
bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return password_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return password_context.verify(password, password_hash)


def create_access_token(subject: str, token_type: str, extra: dict[str, Any] | None = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    payload: dict[str, Any] = {"sub": subject, "type": token_type, "exp": expire}
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise AppError("AUTH_INVALID_TOKEN", "token 无效", status.HTTP_401_UNAUTHORIZED) from exc


def require_token(credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)) -> dict[str, Any]:
    if credentials is None:
        raise AppError("AUTH_INVALID_TOKEN", "缺少认证 token", status.HTTP_401_UNAUTHORIZED)
    return decode_token(credentials.credentials)


def require_app_user(payload: dict[str, Any] = Depends(require_token)) -> dict[str, Any]:
    if payload.get("type") != "app":
        raise AppError("AUTH_FORBIDDEN", "不是客户 token", status.HTTP_403_FORBIDDEN)
    return payload


def require_admin(payload: dict[str, Any] = Depends(require_token)) -> dict[str, Any]:
    if payload.get("type") != "admin":
        raise AppError("AUTH_FORBIDDEN", "不是管理员 token", status.HTTP_403_FORBIDDEN)
    return payload
