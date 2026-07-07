from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field

from app.core.errors import AppError
from app.core.security import require_app_user
from app.schemas.response import success_response

router = APIRouter()


class ListedProductOrderItem(BaseModel):
    sku_id: int
    quantity: int = Field(gt=0)
    custom_note: str | None = None


class CreateListedProductOrderRequest(BaseModel):
    items: list[ListedProductOrderItem]
    customer_note: str | None = None


@router.post("/listed-product")
def create_listed_product_order(
    payload: CreateListedProductOrderRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    _: dict = Depends(require_app_user),
):
    if not idempotency_key:
        raise AppError("IDEMPOTENCY_KEY_REQUIRED", "创建订单必须提供 Idempotency-Key")
    return success_response(
        {
            "order_no": "OD-PENDING",
            "status": "submitted",
            "payment_status": "unconfirmed",
            "item_count": len(payload.items),
        }
    )
