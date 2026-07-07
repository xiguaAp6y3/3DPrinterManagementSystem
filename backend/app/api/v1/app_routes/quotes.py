from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel

from app.core.security import require_app_user
from app.schemas.response import ApiResponse, success_response

router = APIRouter()

QuoteStatus = Literal["draft", "issued", "confirmed", "expired", "cancelled"]


class QuoteDetail(BaseModel):
    id: int
    quote_no: str | None = None
    custom_request_id: int | None = None
    order_id: int | None = None
    estimated_price: float | None = None
    manual_price: float | None = None
    estimated_days: int | None = None
    material_cost: float | None = None
    machine_cost: float | None = None
    labor_cost: float | None = None
    post_processing_cost: float | None = None
    remark: str | None = None
    status: QuoteStatus | str
    confirmed_by_user_at: datetime | None = None


@router.get("/{quote_id}", response_model=ApiResponse[QuoteDetail])
def get_quote(quote_id: int, _: dict = Depends(require_app_user)):
    return success_response({"id": quote_id, "status": "issued"})


@router.post("/{quote_id}/confirm", response_model=ApiResponse[QuoteDetail])
def confirm_quote(quote_id: int, idempotency_key: str = Header(alias="Idempotency-Key"), _: dict = Depends(require_app_user)):
    return success_response({"id": quote_id, "status": "confirmed"})
