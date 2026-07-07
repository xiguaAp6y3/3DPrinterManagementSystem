from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.security import require_admin
from app.schemas.response import ApiResponse, PageResponse, paginated_response, success_response

router = APIRouter()

QuoteStatus = Literal["draft", "issued", "confirmed", "expired", "cancelled"]


class QuoteCreate(BaseModel):
    estimated_price: float | None = Field(default=None, ge=0)
    manual_price: float = Field(ge=0)
    estimated_days: int | None = Field(default=None, ge=0)
    material_cost: float | None = Field(default=None, ge=0)
    machine_cost: float | None = Field(default=None, ge=0)
    labor_cost: float | None = Field(default=None, ge=0)
    post_processing_cost: float | None = Field(default=None, ge=0)
    remark: str | None = None
    status: QuoteStatus = "issued"


class QuoteDetail(BaseModel):
    id: int | None = None
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
    status: QuoteStatus | str = "issued"
    created_at: datetime | None = None
    confirmed_by_user_at: datetime | None = None


@router.post("/custom-requests/{request_id}/quote", response_model=ApiResponse[QuoteDetail])
def create_quote_for_custom_request(request_id: int, payload: QuoteCreate, _: dict = Depends(require_admin)):
    return success_response({"id": None, "quote_no": "QT-PENDING", "custom_request_id": request_id, **payload.model_dump()})


@router.get("/quotes", response_model=ApiResponse[PageResponse[QuoteDetail]])
def list_quotes(page: int = 1, page_size: int = 20, status: QuoteStatus | None = None, custom_request_id: int | None = None, order_id: int | None = None, keyword: str | None = None, _: dict = Depends(require_admin)):
    return paginated_response([], page, page_size, 0)


@router.get("/quotes/{quote_id}", response_model=ApiResponse[QuoteDetail])
def get_quote(quote_id: int, _: dict = Depends(require_admin)):
    return success_response({"id": quote_id, "status": "issued"})
