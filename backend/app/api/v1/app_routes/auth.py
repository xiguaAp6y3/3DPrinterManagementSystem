from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.security import require_app_user
from app.db.session import get_db
from app.schemas.response import ApiResponse, success_response
from app.services.auth_service import app_login, logout, refresh_app_token, serialize_user

router = APIRouter()


class AppLoginRequest(BaseModel):
    phone: str
    code: str


class AppUserInfo(BaseModel):
    id: int | None = None
    phone: str
    nickname: str | None = None
    avatar_url: str | None = None


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
    return success_response(app_login(db, payload.phone, payload.code))


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
