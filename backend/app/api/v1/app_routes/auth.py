from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.security import require_app_user
from app.db.session import get_db
from app.schemas.response import ApiResponse, success_response
from app.services.auth_service import app_demo_login, app_login, app_register, logout, refresh_app_token, serialize_user

router = APIRouter()


class AppLoginRequest(BaseModel):
    email: str
    password: str


class AppRegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=8)
    nickname: str | None = None
    phone: str | None = None


class AppDemoLoginRequest(BaseModel):
    phone: str
    code: str


class AppUserInfo(BaseModel):
    id: int | None = None
    email: str | None = None
    phone: str | None = None
    nickname: str | None = None
    avatar_url: str | None = None
    status: str | None = None


class AppLoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    user: AppUserInfo


class TokenRefreshRequest(BaseModel):
    refresh_token: str


class TokenRefreshResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"


class LogoutRequest(BaseModel):
    refresh_token: str


@router.post("/login", response_model=ApiResponse[AppLoginResponse])
def login(payload: AppLoginRequest, db: Session = Depends(get_db)):
    return success_response(app_login(db, payload.email, payload.password))


@router.post("/register", response_model=ApiResponse[AppLoginResponse])
def register(payload: AppRegisterRequest, db: Session = Depends(get_db)):
    return success_response(app_register(db, payload.email, payload.password, payload.nickname, payload.phone))


@router.post("/login-demo", response_model=ApiResponse[AppLoginResponse])
def login_demo(payload: AppDemoLoginRequest, db: Session = Depends(get_db)):
    return success_response(app_demo_login(db, payload.phone, payload.code))


@router.get("/me", response_model=ApiResponse[AppUserInfo])
def me(current_user: dict = Depends(require_app_user)):
    return success_response(serialize_user(current_user["user"]))


@router.post("/refresh", response_model=ApiResponse[TokenRefreshResponse])
def refresh(payload: TokenRefreshRequest, db: Session = Depends(get_db)):
    return success_response(refresh_app_token(db, payload.refresh_token))


@router.post("/logout", response_model=ApiResponse[dict])
def logout_current(payload: LogoutRequest, db: Session = Depends(get_db)):
    logout(db, payload.refresh_token, "app")
    return success_response({})
