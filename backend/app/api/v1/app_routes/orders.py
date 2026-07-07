from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field

from app.core.security import require_app_user
from app.schemas.response import ApiResponse, PageResponse, paginated_response, success_response

router = APIRouter()

OrderType = Literal["listed_product", "custom"]
OrderStatus = Literal["submitted", "reviewing", "quoted", "quote_confirmed", "payment_confirmed", "scheduled", "printing", "post_processing", "quality_check", "completed", "cancelled"]
PaymentStatus = Literal["unconfirmed", "confirmed", "refunded"]


class ListedProductOrderItem(BaseModel):
    sku_id: int
    quantity: int = Field(gt=0)
    custom_note: str | None = None


class CreateListedProductOrderRequest(BaseModel):
    items: list[ListedProductOrderItem] = Field(min_length=1)
    customer_note: str | None = None


class OrderSummary(BaseModel):
    id: int | None = None
    order_no: str
    order_type: OrderType | str
    status: OrderStatus | str
    total_amount: float = 0
    payment_status: PaymentStatus | str
    item_count: int = 0
    created_at: datetime | None = None


class OrderDetail(OrderSummary):
    customer_note: str | None = None
    admin_note: str | None = None
    items: list[dict[str, Any]] = Field(default_factory=list)
    schedules: list[dict[str, Any]] = Field(default_factory=list)
    print_tasks: list[dict[str, Any]] = Field(default_factory=list)


@router.get("", response_model=ApiResponse[PageResponse[OrderSummary]])
def list_orders(page: int = 1, page_size: int = 20, order_type: OrderType | None = None, status: OrderStatus | None = None, payment_status: PaymentStatus | None = None, keyword: str | None = None, created_from: datetime | None = None, created_to: datetime | None = None, _: dict = Depends(require_app_user)):
    return paginated_response([], page, page_size, 0)


@router.get("/{order_no}", response_model=ApiResponse[OrderDetail])
def get_order(order_no: str, _: dict = Depends(require_app_user)):
    return success_response({"id": None, "order_no": order_no, "order_type": "listed_product", "status": "submitted", "total_amount": 0, "payment_status": "unconfirmed", "item_count": 0, "items": [], "schedules": [], "print_tasks": []})


@router.post("/listed-product", response_model=ApiResponse[OrderSummary])
def create_listed_product_order(payload: CreateListedProductOrderRequest, idempotency_key: str = Header(alias="Idempotency-Key"), _: dict = Depends(require_app_user)):
    return success_response({"id": None, "order_no": "OD-PENDING", "order_type": "listed_product", "status": "submitted", "payment_status": "unconfirmed", "item_count": len(payload.items), "total_amount": 0})
