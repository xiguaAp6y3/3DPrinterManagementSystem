from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.security import require_admin
from app.db.models.core import CustomRequest, Quote
from app.db.session import get_db
from app.schemas.response import ApiResponse, PageResponse, paginated_response, success_response
from app.services.db_helpers import next_no, paginate, require_entity, to_float

router = APIRouter()

QuoteStatus = Literal["draft", "issued", "sent", "confirmed", "cancelled"]


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
def create_quote_for_custom_request(request_id: int, payload: QuoteCreate, current_admin: dict = Depends(require_admin), db: Session = Depends(get_db)):
    custom_request = require_entity(db.get(CustomRequest, request_id), "定制申请不存在")
    quote = Quote(
        quote_no=next_no(db, "seq_quote_no", "QT"),
        custom_request_id=request_id,
        created_by=current_admin["staff_user"].id,
        **payload.model_dump(exclude={"status"}),
        status=normalize_quote_status(payload.status),
    )
    db.add(quote)
    if quote.status == "sent":
        custom_request.status = "quoted"
    elif custom_request.status in {"submitted", "reviewing"}:
        custom_request.status = "quote_pending"
    db.commit()
    db.refresh(quote)
    return success_response(serialize_quote(quote))


@router.get("/quotes", response_model=ApiResponse[PageResponse[QuoteDetail]])
def list_quotes(page: int = 1, page_size: int = 20, status: QuoteStatus | None = None, custom_request_id: int | None = None, order_id: int | None = None, keyword: str | None = None, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    stmt = select(Quote).order_by(Quote.created_at.desc())
    if status:
        stmt = stmt.where(Quote.status == normalize_quote_status(status))
    if custom_request_id is not None:
        stmt = stmt.where(Quote.custom_request_id == custom_request_id)
    if order_id is not None:
        stmt = stmt.where(Quote.order_id == order_id)
    if keyword:
        stmt = stmt.where(or_(Quote.quote_no.contains(keyword), Quote.remark.contains(keyword)))
    items, page, page_size, total = paginate(db, stmt, page, page_size)
    return paginated_response([serialize_quote(item) for item in items], page, page_size, total)


@router.get("/quotes/{quote_id}", response_model=ApiResponse[QuoteDetail])
def get_quote(quote_id: int, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    quote = require_entity(db.get(Quote, quote_id), "报价不存在")
    return success_response(serialize_quote(quote))


def normalize_quote_status(status: str) -> str:
    return "sent" if status == "issued" else status


def serialize_quote(quote: Quote) -> dict:
    return {
        "id": quote.id,
        "quote_no": quote.quote_no,
        "custom_request_id": quote.custom_request_id,
        "order_id": quote.order_id,
        "estimated_price": to_float(quote.estimated_price),
        "manual_price": to_float(quote.manual_price),
        "estimated_days": quote.estimated_days,
        "material_cost": to_float(quote.material_cost),
        "machine_cost": to_float(quote.machine_cost),
        "labor_cost": to_float(quote.labor_cost),
        "post_processing_cost": to_float(quote.post_processing_cost),
        "remark": quote.remark,
        "status": quote.status,
        "created_at": quote.created_at,
        "confirmed_by_user_at": quote.confirmed_by_user_at,
    }
