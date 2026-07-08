from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.security import require_admin
from app.db.session import get_db
from app.schemas.response import ApiResponse, success_response
from app.services.auth_service import admin_login, logout, refresh_admin_token, serialize_staff_user

router = APIRouter()


class AdminLoginRequest(BaseModel):
    username: str
    password: str


class StaffUserInfo(BaseModel):
    id: int | None = None
    username: str
    role: str = "admin"
    display_name: str | None = None


class AdminLoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    staff_user: StaffUserInfo


class TokenRefreshRequest(BaseModel):
    refresh_token: str


class TokenRefreshResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"


class LogoutRequest(BaseModel):
    refresh_token: str


@router.post("/login", response_model=ApiResponse[AdminLoginResponse])
def login(payload: AdminLoginRequest, db: Session = Depends(get_db)):
    return success_response(admin_login(db, payload.username, payload.password))


@router.get("/me", response_model=ApiResponse[StaffUserInfo])
def me(current_admin: dict = Depends(require_admin)):
    return success_response(serialize_staff_user(current_admin["staff_user"]))


@router.post("/refresh", response_model=ApiResponse[TokenRefreshResponse])
def refresh(payload: TokenRefreshRequest, db: Session = Depends(get_db)):
    return success_response(refresh_admin_token(db, payload.refresh_token))


@router.post("/logout", response_model=ApiResponse[dict])
def logout_current(payload: LogoutRequest, db: Session = Depends(get_db)):
    logout(db, payload.refresh_token, "admin")
    return success_response({})
