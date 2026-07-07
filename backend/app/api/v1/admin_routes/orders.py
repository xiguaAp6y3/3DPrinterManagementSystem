from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field

from app.core.security import require_admin
from app.schemas.response import ApiResponse, PageResponse, paginated_response, success_response

router = APIRouter()

OrderType = Literal["listed_product", "custom"]
OrderStatus = Literal["submitted", "reviewing", "quoted", "quote_confirmed", "payment_confirmed", "scheduled", "printing", "post_processing", "quality_check", "completed", "cancelled"]
PaymentStatus = Literal["unconfirmed", "confirmed", "refunded"]


class OrderStatusUpdate(BaseModel):
    status: OrderStatus
    remark: str | None = None


class PaymentConfirmRequest(BaseModel):
    remark: str | None = None


class OrderDetail(BaseModel):
    id: int | None = None
    order_no: str | None = None
    user_id: int | None = None
    order_type: OrderType | str = "listed_product"
    status: OrderStatus | str = "submitted"
    total_amount: float = 0
    payment_status: PaymentStatus | str = "unconfirmed"
    customer_note: str | None = None
    admin_note: str | None = None
    items: list[dict[str, Any]] = Field(default_factory=list)
    schedules: list[dict[str, Any]] = Field(default_factory=list)
    print_tasks: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime | None = None


@router.get("", response_model=ApiResponse[PageResponse[OrderDetail]])
def list_orders(page: int = 1, page_size: int = 20, order_type: OrderType | None = None, status: OrderStatus | None = None, payment_status: PaymentStatus | None = None, keyword: str | None = None, created_from: datetime | None = None, created_to: datetime | None = None, _: dict = Depends(require_admin)):
    return paginated_response([], page, page_size, 0)


@router.get("/{order_id}", response_model=ApiResponse[OrderDetail])
def get_order(order_id: int, _: dict = Depends(require_admin)):
    return success_response({"id": order_id, "order_no": f"OD-{order_id}", "items": [], "schedules": [], "print_tasks": []})


@router.patch("/{order_id}/status", response_model=ApiResponse[OrderDetail])
def update_order_status(order_id: int, payload: OrderStatusUpdate, _: dict = Depends(require_admin)):
    return success_response({"id": order_id, "status": payload.status, "admin_note": payload.remark, "items": [], "schedules": [], "print_tasks": []})


@router.post("/{order_id}/payment-confirm", response_model=ApiResponse[OrderDetail])
def confirm_payment(order_id: int, payload: PaymentConfirmRequest, idempotency_key: str = Header(alias="Idempotency-Key"), _: dict = Depends(require_admin)):
    return success_response({"id": order_id, "payment_status": "confirmed", "status": "payment_confirmed", "admin_note": payload.remark, "items": [], "schedules": [], "print_tasks": []})
