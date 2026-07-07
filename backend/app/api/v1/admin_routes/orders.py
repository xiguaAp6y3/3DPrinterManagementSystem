from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel

from app.core.errors import AppError
from app.core.security import require_admin
from app.schemas.response import paginated_response, success_response

router = APIRouter()


class OrderStatusUpdate(BaseModel):
    status: str
    remark: str | None = None


class PaymentConfirmRequest(BaseModel):
    remark: str | None = None


@router.get("")
def list_orders(page: int = 1, page_size: int = 20, _: dict = Depends(require_admin)):
    return paginated_response([], page, page_size, 0)


@router.get("/{order_id}")
def get_order(order_id: int, _: dict = Depends(require_admin)):
    return success_response({"id": order_id})


@router.patch("/{order_id}/status")
def update_order_status(order_id: int, payload: OrderStatusUpdate, _: dict = Depends(require_admin)):
    return success_response({"id": order_id, "status": payload.status, "remark": payload.remark})


@router.post("/{order_id}/payment-confirm")
def confirm_payment(
    order_id: int,
    payload: PaymentConfirmRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    _: dict = Depends(require_admin),
):
    if not idempotency_key:
        raise AppError("IDEMPOTENCY_KEY_REQUIRED", "确认收款必须提供 Idempotency-Key")
    return success_response({"id": order_id, "payment_status": "confirmed", "status": "payment_confirmed", "remark": payload.remark})
