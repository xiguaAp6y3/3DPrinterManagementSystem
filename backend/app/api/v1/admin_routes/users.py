from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.security import hash_password, require_admin
from app.core.time import utc8_now
from app.db.models.core import AuthRefreshToken, User
from app.db.session import get_db
from app.schemas.response import ApiResponse, PageResponse, paginated_response, success_response
from app.services.db_helpers import paginate, require_entity

router = APIRouter()


class UserCreate(BaseModel):
    email: str
    password: str = Field(min_length=8)
    nickname: str | None = None
    phone: str | None = None
    status: str = "active"


class UserUpdate(BaseModel):
    email: str | None = None
    nickname: str | None = None
    phone: str | None = None
    avatar_url: str | None = None
    status: str | None = None


class UserStatusUpdate(BaseModel):
    status: str


class PasswordResetRequest(BaseModel):
    new_password: str = Field(min_length=8)


class UserInfo(BaseModel):
    id: int | None = None
    email: str | None = None
    phone: str | None = None
    nickname: str | None = None
    avatar_url: str | None = None
    status: str = "active"
    last_login_at: datetime | None = None
    created_at: datetime | None = None


@router.get("", response_model=ApiResponse[PageResponse[UserInfo]])
def list_users(page: int = 1, page_size: int = 20, keyword: str | None = None, status: str | None = None, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    stmt = select(User).where(User.deleted_at.is_(None)).order_by(User.created_at.desc())
    if keyword:
        stmt = stmt.where(or_(User.email.contains(keyword), User.phone.contains(keyword), User.nickname.contains(keyword)))
    if status:
        stmt = stmt.where(User.status == status)
    items, page, page_size, total = paginate(db, stmt, page, page_size)
    return paginated_response([serialize_user(item) for item in items], page, page_size, total)


@router.post("", response_model=ApiResponse[UserInfo])
def create_user(payload: UserCreate, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    email = normalize_email(payload.email)
    ensure_user_unique(db, email, payload.phone)
    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        nickname=payload.nickname or "用户",
        phone=payload.phone,
        status=payload.status,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return success_response(serialize_user(user))


@router.get("/{user_id}", response_model=ApiResponse[UserInfo])
def get_user(user_id: int, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    return success_response(serialize_user(require_active_row(db.get(User, user_id))))


@router.patch("/{user_id}", response_model=ApiResponse[UserInfo])
def update_user(user_id: int, payload: UserUpdate, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    user = require_active_row(db.get(User, user_id))
    data = payload.model_dump(exclude_none=True)
    if "email" in data:
        data["email"] = normalize_email(data["email"])
        ensure_user_unique(db, data["email"], None, exclude_user_id=user.id)
    if "phone" in data:
        ensure_user_unique(db, None, data["phone"], exclude_user_id=user.id)
    for key, value in data.items():
        setattr(user, key, value)
    db.commit()
    db.refresh(user)
    return success_response(serialize_user(user))


@router.patch("/{user_id}/status", response_model=ApiResponse[UserInfo])
def update_user_status(user_id: int, payload: UserStatusUpdate, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    if payload.status not in {"active", "disabled"}:
        raise AppError("VALIDATION_ERROR", "客户状态只能是 active 或 disabled", 422)
    user = require_active_row(db.get(User, user_id))
    user.status = payload.status
    if payload.status != "active":
        revoke_user_tokens(db, user.id)
    db.commit()
    db.refresh(user)
    return success_response(serialize_user(user))


@router.post("/{user_id}/reset-password", response_model=ApiResponse[dict])
def reset_user_password(user_id: int, payload: PasswordResetRequest, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    user = require_active_row(db.get(User, user_id))
    user.password_hash = hash_password(payload.new_password)
    revoke_user_tokens(db, user.id)
    db.commit()
    return success_response({"user_id": user.id, "status": "password_reset"})


@router.delete("/{user_id}", response_model=ApiResponse[dict])
def delete_user(user_id: int, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    user = require_active_row(db.get(User, user_id))
    user.status = "deleted"
    user.deleted_at = utc8_now()
    revoke_user_tokens(db, user.id)
    db.commit()
    return success_response({"user_id": user.id, "status": "deleted"})


def normalize_email(email: str) -> str:
    value = email.strip().lower()
    if "@" not in value or "." not in value.rsplit("@", 1)[-1]:
        raise AppError("VALIDATION_ERROR", "邮箱格式不正确", 422)
    return value


def ensure_user_unique(db: Session, email: str | None, phone: str | None, exclude_user_id: int | None = None) -> None:
    if email:
        stmt = select(User).where(User.email == email, User.deleted_at.is_(None))
        if exclude_user_id:
            stmt = stmt.where(User.id != exclude_user_id)
        if db.scalar(stmt):
            raise AppError("USER_EMAIL_EXISTS", "邮箱已存在", 409)
    if phone:
        stmt = select(User).where(User.phone == phone, User.deleted_at.is_(None))
        if exclude_user_id:
            stmt = stmt.where(User.id != exclude_user_id)
        if db.scalar(stmt):
            raise AppError("USER_PHONE_EXISTS", "手机号已存在", 409)


def require_active_row(user: User | None) -> User:
    user = require_entity(user, "客户不存在")
    if user.deleted_at is not None:
        raise AppError("RESOURCE_NOT_FOUND", "客户不存在", 404)
    return user


def revoke_user_tokens(db: Session, user_id: int) -> None:
    now = utc8_now()
    for token in db.scalars(select(AuthRefreshToken).where(AuthRefreshToken.user_id == user_id, AuthRefreshToken.revoked_at.is_(None))).all():
        token.revoked_at = now


def serialize_user(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "phone": user.phone,
        "nickname": user.nickname,
        "avatar_url": user.avatar_url,
        "status": user.status,
        "last_login_at": user.last_login_at,
        "created_at": user.created_at,
    }
