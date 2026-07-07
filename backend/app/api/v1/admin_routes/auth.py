from fastapi import APIRouter
from pydantic import BaseModel

from app.core.security import create_access_token
from app.schemas.response import success_response

router = APIRouter()


class AdminLoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(payload: AdminLoginRequest):
    token = create_access_token(subject=payload.username, token_type="admin", extra={"username": payload.username, "role": "admin"})
    return success_response(
        {
            "access_token": token,
            "token_type": "Bearer",
            "staff_user": {"id": None, "username": payload.username, "role": "admin"},
        }
    )
