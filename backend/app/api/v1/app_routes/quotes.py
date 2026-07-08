from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.security import require_app_user
from app.db.models.core import CustomRequest, Order, OrderItem, Quote
from app.db.session import get_db
from app.schemas.response import ApiResponse, success_response
from app.services.db_helpers import next_no, require_entity, to_float

router = APIRouter()

QuoteStatus = Literal["draft", "issued", "sent", "confirmed", "cancelled"]


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
def get_quote(quote_id: int, current_user: dict = Depends(require_app_user), db: Session = Depends(get_db)):
    quote = get_user_quote(db, quote_id, current_user["user"].id)
    return success_response(serialize_quote(quote))


@router.post("/{quote_id}/confirm", response_model=ApiResponse[QuoteDetail])
def confirm_quote(quote_id: int, idempotency_key: str = Header(alias="Idempotency-Key"), current_user: dict = Depends(require_app_user), db: Session = Depends(get_db)):
    quote = get_user_quote(db, quote_id, current_user["user"].id)
    quote.status = "confirmed"
    quote.confirmed_by_user_at = datetime.utcnow()
    custom_request = db.get(CustomRequest, quote.custom_request_id) if quote.custom_request_id else None
    if custom_request is not None:
        custom_request.status = "quote_confirmed"
    if quote.order_id is None:
        order = Order(
            order_no=next_no(db, "seq_order_no", "OD"),
            user_id=current_user["user"].id,
            order_type="custom",
            status="quote_confirmed",
            payment_status="unconfirmed",
            total_amount=to_float(quote.manual_price) or 0,
            customer_note=f"定制报价 {quote.quote_no}",
        )
        db.add(order)
        db.flush()
        db.add(
            OrderItem(
                order_id=order.id,
                custom_request_id=quote.custom_request_id,
                item_name=f"个性化定制 {custom_request.request_no if custom_request else quote.quote_no}",
                unit_price=to_float(quote.manual_price) or 0,
                quantity=1,
                subtotal=to_float(quote.manual_price) or 0,
            )
        )
        quote.order_id = order.id
    db.commit()
    db.refresh(quote)
    return success_response(serialize_quote(quote))


def get_user_quote(db: Session, quote_id: int, user_id: int) -> Quote:
    quote = require_entity(db.get(Quote, quote_id), "报价不存在")
    if quote.custom_request_id is not None:
        custom_request = db.get(CustomRequest, quote.custom_request_id)
        if custom_request is None or custom_request.user_id != user_id:
            require_entity(None, "报价不存在")
    elif quote.order_id is not None:
        order = db.get(Order, quote.order_id)
        if order is None or order.user_id != user_id:
            require_entity(None, "报价不存在")
    else:
        require_entity(None, "报价不存在")
    return quote


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
        "confirmed_by_user_at": quote.confirmed_by_user_at,
    }
