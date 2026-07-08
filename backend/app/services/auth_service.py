from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette import status

from app.core.errors import AppError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_refresh_token,
    refresh_token_expires_at,
    verify_password,
)
from app.db.models.core import AuthRefreshToken, StaffUser, User


DEMO_APP_LOGIN_CODE = "123456"


def serialize_user(user: User) -> dict:
    return {
        "id": user.id,
        "phone": user.phone,
        "nickname": user.nickname,
        "avatar_url": user.avatar_url,
    }


def serialize_staff_user(staff_user: StaffUser) -> dict:
    return {
        "id": staff_user.id,
        "username": staff_user.username,
        "role": staff_user.role,
        "display_name": staff_user.display_name,
    }


def _create_app_access_token(user: User) -> str:
    return create_access_token(
        subject=str(user.id),
        token_type="app",
        extra={"user_id": user.id, "phone": user.phone},
    )


def _create_admin_access_token(staff_user: StaffUser) -> str:
    return create_access_token(
        subject=str(staff_user.id),
        token_type="admin",
        extra={"staff_user_id": staff_user.id, "username": staff_user.username, "role": staff_user.role},
    )


def _save_refresh_token(db: Session, subject_type: str, user_id: int | None = None, staff_user_id: int | None = None) -> str:
    refresh_token = create_refresh_token()
    db.add(
        AuthRefreshToken(
            token_hash=hash_refresh_token(refresh_token),
            subject_type=subject_type,
            user_id=user_id,
            staff_user_id=staff_user_id,
            expires_at=refresh_token_expires_at(),
        )
    )
    return refresh_token


def app_login(db: Session, phone: str, code: str) -> dict:
    if code != DEMO_APP_LOGIN_CODE:
        raise AppError("AUTH_INVALID_CODE", "验证码错误，Demo 固定验证码为 123456", status.HTTP_401_UNAUTHORIZED)

    user = db.scalar(select(User).where(User.phone == phone))
    if user is None:
        user = User(phone=phone, nickname="用户", status="active")
        db.add(user)
        db.flush()
    elif user.status != "active":
        raise AppError("AUTH_FORBIDDEN", "客户账号不可用", status.HTTP_403_FORBIDDEN)

    access_token = _create_app_access_token(user)
    refresh_token = _save_refresh_token(db, "app", user_id=user.id)
    db.commit()
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "Bearer",
        "user": serialize_user(user),
    }


def admin_login(db: Session, username: str, password: str) -> dict:
    staff_user = db.scalar(select(StaffUser).where(StaffUser.username == username))
    if staff_user is None or not verify_password(password, staff_user.password_hash):
        raise AppError("AUTH_INVALID_CREDENTIALS", "用户名或密码错误", status.HTTP_401_UNAUTHORIZED)
    if staff_user.status != "active":
        raise AppError("AUTH_FORBIDDEN", "管理员账号不可用", status.HTTP_403_FORBIDDEN)

    staff_user.last_login_at = datetime.utcnow()
    access_token = _create_admin_access_token(staff_user)
    refresh_token = _save_refresh_token(db, "admin", staff_user_id=staff_user.id)
    db.commit()
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "Bearer",
        "staff_user": serialize_staff_user(staff_user),
    }


def refresh_app_token(db: Session, refresh_token: str) -> dict:
    token_record = _get_valid_refresh_token(db, refresh_token, "app")
    user = db.scalar(select(User).where(User.id == token_record.user_id))
    if user is None or user.status != "active":
        raise AppError("AUTH_FORBIDDEN", "客户账号不可用", status.HTTP_403_FORBIDDEN)

    token_record.revoked_at = datetime.utcnow()
    new_refresh_token = _save_refresh_token(db, "app", user_id=user.id)
    access_token = _create_app_access_token(user)
    db.commit()
    return {"access_token": access_token, "refresh_token": new_refresh_token, "token_type": "Bearer"}


def refresh_admin_token(db: Session, refresh_token: str) -> dict:
    token_record = _get_valid_refresh_token(db, refresh_token, "admin")
    staff_user = db.scalar(select(StaffUser).where(StaffUser.id == token_record.staff_user_id))
    if staff_user is None or staff_user.status != "active":
        raise AppError("AUTH_FORBIDDEN", "管理员账号不可用", status.HTTP_403_FORBIDDEN)

    token_record.revoked_at = datetime.utcnow()
    new_refresh_token = _save_refresh_token(db, "admin", staff_user_id=staff_user.id)
    access_token = _create_admin_access_token(staff_user)
    db.commit()
    return {"access_token": access_token, "refresh_token": new_refresh_token, "token_type": "Bearer"}


def logout(db: Session, refresh_token: str, subject_type: str) -> None:
    token_record = db.scalar(
        select(AuthRefreshToken).where(
            AuthRefreshToken.token_hash == hash_refresh_token(refresh_token),
            AuthRefreshToken.subject_type == subject_type,
            AuthRefreshToken.revoked_at.is_(None),
        )
    )
    if token_record is not None:
        token_record.revoked_at = datetime.utcnow()
        db.commit()


def _get_valid_refresh_token(db: Session, refresh_token: str, subject_type: str) -> AuthRefreshToken:
    token_record = db.scalar(
        select(AuthRefreshToken).where(
            AuthRefreshToken.token_hash == hash_refresh_token(refresh_token),
            AuthRefreshToken.subject_type == subject_type,
        )
    )
    if token_record is None or token_record.revoked_at is not None or token_record.expires_at <= datetime.utcnow():
        raise AppError("AUTH_INVALID_REFRESH_TOKEN", "refresh token 无效或已过期", status.HTTP_401_UNAUTHORIZED)
    return token_record
