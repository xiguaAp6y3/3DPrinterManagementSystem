from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.security import hash_password, require_admin
from app.core.time import utc8_now
from app.db.models.core import AuthRefreshToken, StaffUser
from app.db.session import get_db
from app.schemas.response import ApiResponse, PageResponse, paginated_response, success_response
from app.services.db_helpers import paginate, require_entity

router = APIRouter()


class StaffUserCreate(BaseModel):
    username: str
    password: str = Field(min_length=8)
    email: str | None = None
    display_name: str | None = None
    role: str = "admin"
    status: str = "active"


class StaffUserUpdate(BaseModel):
    username: str | None = None
    email: str | None = None
    display_name: str | None = None
    role: str | None = None
    status: str | None = None


class StaffStatusUpdate(BaseModel):
    status: str


class PasswordResetRequest(BaseModel):
    new_password: str = Field(min_length=8)


class StaffUserInfo(BaseModel):
    id: int | None = None
    username: str | None = None
    email: str | None = None
    display_name: str | None = None
    role: str = "admin"
    status: str = "active"
    last_login_at: datetime | None = None
    created_at: datetime | None = None


@router.get("", response_model=ApiResponse[PageResponse[StaffUserInfo]])
def list_staff_users(page: int = 1, page_size: int = 20, keyword: str | None = None, status: str | None = None, current_admin: dict = Depends(require_admin), db: Session = Depends(get_db)):
    require_super_admin(current_admin)
    stmt = select(StaffUser).where(StaffUser.deleted_at.is_(None)).order_by(StaffUser.created_at.desc())
    if keyword:
        stmt = stmt.where(or_(StaffUser.username.contains(keyword), StaffUser.email.contains(keyword), StaffUser.display_name.contains(keyword)))
    if status:
        stmt = stmt.where(StaffUser.status == status)
    items, page, page_size, total = paginate(db, stmt, page, page_size)
    return paginated_response([serialize_staff_user(item) for item in items], page, page_size, total)


@router.post("", response_model=ApiResponse[StaffUserInfo])
def create_staff_user(payload: StaffUserCreate, current_admin: dict = Depends(require_admin), db: Session = Depends(get_db)):
    require_super_admin(current_admin)
    username = payload.username.strip()
    email = normalize_optional_email(payload.email)
    ensure_staff_unique(db, username, email)
    staff_user = StaffUser(
        username=username,
        email=email,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name,
        role=payload.role,
        status=payload.status,
    )
    db.add(staff_user)
    db.commit()
    db.refresh(staff_user)
    return success_response(serialize_staff_user(staff_user))


@router.get("/{staff_user_id}", response_model=ApiResponse[StaffUserInfo])
def get_staff_user(staff_user_id: int, current_admin: dict = Depends(require_admin), db: Session = Depends(get_db)):
    require_super_admin(current_admin)
    return success_response(serialize_staff_user(require_active_row(db.get(StaffUser, staff_user_id))))


@router.patch("/{staff_user_id}", response_model=ApiResponse[StaffUserInfo])
def update_staff_user(staff_user_id: int, payload: StaffUserUpdate, current_admin: dict = Depends(require_admin), db: Session = Depends(get_db)):
    require_super_admin(current_admin)
    staff_user = require_active_row(db.get(StaffUser, staff_user_id))
    data = payload.model_dump(exclude_none=True)
    if "username" in data:
        data["username"] = data["username"].strip()
        ensure_staff_unique(db, data["username"], None, exclude_staff_id=staff_user.id)
    if "email" in data:
        data["email"] = normalize_optional_email(data["email"])
        ensure_staff_unique(db, None, data["email"], exclude_staff_id=staff_user.id)
    if data.get("status") != "active" and staff_user.role == "super_admin":
        ensure_not_last_super_admin(db, staff_user.id)
    if data.get("role") and staff_user.role == "super_admin" and data["role"] != "super_admin":
        ensure_not_last_super_admin(db, staff_user.id)
    for key, value in data.items():
        setattr(staff_user, key, value)
    db.commit()
    db.refresh(staff_user)
    return success_response(serialize_staff_user(staff_user))


@router.patch("/{staff_user_id}/status", response_model=ApiResponse[StaffUserInfo])
def update_staff_user_status(staff_user_id: int, payload: StaffStatusUpdate, current_admin: dict = Depends(require_admin), db: Session = Depends(get_db)):
    require_super_admin(current_admin)
    if payload.status not in {"active", "disabled"}:
        raise AppError("VALIDATION_ERROR", "后台账号状态只能是 active 或 disabled", 422)
    staff_user = require_active_row(db.get(StaffUser, staff_user_id))
    if payload.status != "active" and staff_user.role == "super_admin":
        ensure_not_last_super_admin(db, staff_user.id)
    staff_user.status = payload.status
    if payload.status != "active":
        revoke_staff_tokens(db, staff_user.id)
    db.commit()
    db.refresh(staff_user)
    return success_response(serialize_staff_user(staff_user))


@router.post("/{staff_user_id}/reset-password", response_model=ApiResponse[dict])
def reset_staff_user_password(staff_user_id: int, payload: PasswordResetRequest, current_admin: dict = Depends(require_admin), db: Session = Depends(get_db)):
    require_super_admin(current_admin)
    staff_user = require_active_row(db.get(StaffUser, staff_user_id))
    staff_user.password_hash = hash_password(payload.new_password)
    revoke_staff_tokens(db, staff_user.id)
    db.commit()
    return success_response({"staff_user_id": staff_user.id, "status": "password_reset"})


@router.delete("/{staff_user_id}", response_model=ApiResponse[dict])
def delete_staff_user(staff_user_id: int, current_admin: dict = Depends(require_admin), db: Session = Depends(get_db)):
    require_super_admin(current_admin)
    staff_user = require_active_row(db.get(StaffUser, staff_user_id))
    if staff_user.role == "super_admin":
        ensure_not_last_super_admin(db, staff_user.id)
    staff_user.status = "deleted"
    staff_user.deleted_at = utc8_now()
    revoke_staff_tokens(db, staff_user.id)
    db.commit()
    return success_response({"staff_user_id": staff_user.id, "status": "deleted"})


def require_super_admin(current_admin: dict) -> None:
    if current_admin["staff_user"].role != "super_admin":
        raise AppError("AUTH_FORBIDDEN", "只有超级管理员可以管理后台账号", 403)


def normalize_optional_email(email: str | None) -> str | None:
    if not email:
        return None
    value = email.strip().lower()
    if "@" not in value or "." not in value.rsplit("@", 1)[-1]:
        raise AppError("VALIDATION_ERROR", "邮箱格式不正确", 422)
    return value


def ensure_staff_unique(db: Session, username: str | None, email: str | None, exclude_staff_id: int | None = None) -> None:
    if username:
        stmt = select(StaffUser).where(StaffUser.username == username)
        if exclude_staff_id:
            stmt = stmt.where(StaffUser.id != exclude_staff_id)
        if db.scalar(stmt):
            raise AppError("STAFF_USERNAME_EXISTS", "用户名已存在", 409)
    if email:
        stmt = select(StaffUser).where(StaffUser.email == email)
        if exclude_staff_id:
            stmt = stmt.where(StaffUser.id != exclude_staff_id)
        if db.scalar(stmt):
            raise AppError("STAFF_EMAIL_EXISTS", "邮箱已存在", 409)


def ensure_not_last_super_admin(db: Session, current_staff_id: int) -> None:
    count = db.scalar(
        select(func.count())
        .select_from(StaffUser)
        .where(
            StaffUser.role == "super_admin",
            StaffUser.status == "active",
            StaffUser.deleted_at.is_(None),
            StaffUser.id != current_staff_id,
        )
    ) or 0
    if count <= 0:
        raise AppError("LAST_SUPER_ADMIN", "不能禁用、删除或降级最后一个超级管理员", 409)


def require_active_row(staff_user: StaffUser | None) -> StaffUser:
    staff_user = require_entity(staff_user, "后台账号不存在")
    if staff_user.deleted_at is not None:
        raise AppError("RESOURCE_NOT_FOUND", "后台账号不存在", 404)
    return staff_user


def revoke_staff_tokens(db: Session, staff_user_id: int) -> None:
    now = utc8_now()
    for token in db.scalars(select(AuthRefreshToken).where(AuthRefreshToken.staff_user_id == staff_user_id, AuthRefreshToken.revoked_at.is_(None))).all():
        token.revoked_at = now


def serialize_staff_user(staff_user: StaffUser) -> dict:
    return {
        "id": staff_user.id,
        "username": staff_user.username,
        "email": staff_user.email,
        "display_name": staff_user.display_name,
        "role": staff_user.role,
        "status": staff_user.status,
        "last_login_at": staff_user.last_login_at,
        "created_at": staff_user.created_at,
    }
