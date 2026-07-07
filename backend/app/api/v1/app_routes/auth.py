from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.security import create_access_token
from app.schemas.response import ApiResponse, success_response

router = APIRouter()


class AppLoginRequest(BaseModel):
    phone: str
    code: str


@router.post("/login", response_model=ApiResponse[dict[str, Any]])
def login(payload: AppLoginRequest):
    token = create_access_token(subject=payload.phone, token_type="app", extra={"phone": payload.phone})
    return success_response({"access_token": token, "token_type": "Bearer", "user": {"id": None, "phone": payload.phone, "nickname": "用户"}})
