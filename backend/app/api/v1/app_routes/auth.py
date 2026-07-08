from fastapi import APIRouter
from pydantic import BaseModel

from app.core.security import create_access_token
from app.schemas.response import ApiResponse, success_response

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
    token_type: str = "Bearer"
    user: AppUserInfo


@router.post("/login", response_model=ApiResponse[AppLoginResponse])
def login(payload: AppLoginRequest):
    token = create_access_token(subject=payload.phone, token_type="app", extra={"phone": payload.phone})
    return success_response({"access_token": token, "token_type": "Bearer", "user": {"id": None, "phone": payload.phone, "nickname": "用户"}})
