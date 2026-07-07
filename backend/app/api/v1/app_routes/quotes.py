from fastapi import APIRouter, Depends, Header

from app.core.errors import AppError
from app.core.security import require_app_user
from app.schemas.response import success_response

router = APIRouter()


@router.get("/{quote_id}")
def get_quote(quote_id: int, _: dict = Depends(require_app_user)):
    return success_response({"id": quote_id})


@router.post("/{quote_id}/confirm")
def confirm_quote(
    quote_id: int,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    _: dict = Depends(require_app_user),
):
    if not idempotency_key:
        raise AppError("IDEMPOTENCY_KEY_REQUIRED", "确认报价必须提供 Idempotency-Key")
    return success_response({"id": quote_id, "status": "confirmed"})
