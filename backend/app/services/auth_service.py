from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette import status

from app.core.errors import AppError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_refresh_token,
    refresh_token_expires_at,
    verify_password,
)
from app.db.models.core import AuthRefreshToken, StaffUser, User


DEMO_APP_LOGIN_CODE = "123456"


def serialize_user(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "phone": user.phone,
        "nickname": user.nickname,
        "avatar_url": user.avatar_url,
        "status": user.status,
    }


def serialize_staff_user(staff_user: StaffUser) -> dict:
    return {
        "id": staff_user.id,
        "username": staff_user.username,
        "email": staff_user.email,
        "role": staff_user.role,
        "display_name": staff_user.display_name,
        "status": staff_user.status,
    }


def _create_app_access_token(user: User) -> str:
    return create_access_token(
        subject=str(user.id),
        token_type="app",
        extra={"user_id": user.id, "email": user.email},
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


def app_register(db: Session, email: str, password: str, nickname: str | None = None, phone: str | None = None) -> dict:
    normalized_email = email.strip().lower()
    if "@" not in normalized_email or "." not in normalized_email.rsplit("@", 1)[-1]:
        raise AppError("VALIDATION_ERROR", "邮箱格式不正确", status.HTTP_422_UNPROCESSABLE_ENTITY)
    existing = db.scalar(select(User).where(User.email == normalized_email, User.deleted_at.is_(None)))
    if existing is not None:
        raise AppError("AUTH_EMAIL_EXISTS", "邮箱已注册", status.HTTP_409_CONFLICT)
    if phone:
        existing_phone = db.scalar(select(User).where(User.phone == phone, User.deleted_at.is_(None)))
        if existing_phone is not None:
            raise AppError("AUTH_PHONE_EXISTS", "手机号已存在", status.HTTP_409_CONFLICT)

    user = User(
        email=normalized_email,
        password_hash=hash_password(password),
        phone=phone,
        nickname=nickname or "用户",
        status="active",
    )
    db.add(user)
    db.flush()
    access_token = _create_app_access_token(user)
    refresh_token = _save_refresh_token(db, "app", user_id=user.id)
    db.commit()
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "Bearer",
        "user": serialize_user(user),
    }


def app_login(db: Session, email: str, password: str) -> dict:
    normalized_email = email.strip().lower()
    user = db.scalar(select(User).where(User.email == normalized_email, User.deleted_at.is_(None)))
    if user is None or not user.password_hash or not verify_password(password, user.password_hash):
        raise AppError("AUTH_INVALID_CREDENTIALS", "邮箱或密码错误", status.HTTP_401_UNAUTHORIZED)
    if user.status != "active":
        raise AppError("AUTH_FORBIDDEN", "客户账号不可用", status.HTTP_403_FORBIDDEN)

    user.last_login_at = datetime.utcnow()
    access_token = _create_app_access_token(user)
    refresh_token = _save_refresh_token(db, "app", user_id=user.id)
    db.commit()
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "Bearer",
        "user": serialize_user(user),
    }


def app_demo_login(db: Session, phone: str, code: str) -> dict:
    if code != DEMO_APP_LOGIN_CODE:
        raise AppError("AUTH_INVALID_CODE", "验证码错误，Demo 固定验证码为 123456", status.HTTP_401_UNAUTHORIZED)

    user = db.scalar(select(User).where(User.phone == phone, User.deleted_at.is_(None)))
    if user is None:
        user = User(
            email=f"demo-{phone}@local.3dpms",
            password_hash=hash_password(create_refresh_token()),
            phone=phone,
            nickname="用户",
            status="active",
        )
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


def update_app_profile(
    db: Session,
    user: User,
    nickname: str | None = None,
    old_password: str | None = None,
    new_password: str | None = None,
) -> dict:
    if nickname is None and new_password is None:
        raise AppError("VALIDATION_ERROR", "至少需要修改昵称或密码", status.HTTP_422_UNPROCESSABLE_ENTITY)

    if nickname is not None:
        normalized_nickname = nickname.strip()
        if not normalized_nickname:
            raise AppError("VALIDATION_ERROR", "昵称不能为空", status.HTTP_422_UNPROCESSABLE_ENTITY)
        user.nickname = normalized_nickname

    if new_password is not None:
        if not old_password:
            raise AppError("AUTH_OLD_PASSWORD_REQUIRED", "修改密码必须提供原密码", status.HTTP_422_UNPROCESSABLE_ENTITY)
        if not user.password_hash or not verify_password(old_password, user.password_hash):
            raise AppError("AUTH_INVALID_OLD_PASSWORD", "原密码错误", status.HTTP_401_UNAUTHORIZED)

        user.password_hash = hash_password(new_password)
        for token in db.scalars(
            select(AuthRefreshToken).where(
                AuthRefreshToken.user_id == user.id,
                AuthRefreshToken.subject_type == "app",
                AuthRefreshToken.revoked_at.is_(None),
            )
        ).all():
            token.revoked_at = datetime.utcnow()

    db.commit()
    db.refresh(user)
    return serialize_user(user)


def admin_login(db: Session, username: str, password: str) -> dict:
    login_name = username.strip()
    staff_user = db.scalar(select(StaffUser).where((StaffUser.username == login_name) | (StaffUser.email == login_name.lower())))
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
