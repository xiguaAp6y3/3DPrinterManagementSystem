"""App-side coupon & lottery routes for the demo.

The lottery (prize selection) runs entirely on the frontend.
After the frontend draws a prize, it calls ``POST /lottery/draw`` to
have the backend issue the coupon to the logged-in user.

discount_value convention:
    80 = 8折 (20% off — the maximum discount allowed)
    90 = 9折 (10% off)
    95 = 9.5折 (5% off)
"""

from typing import Literal

from fastapi import APIRouter, Depends, Header, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.security import require_app_user
from app.db.session import get_db
from app.schemas.response import ApiResponse, PageResponse, paginated_response, success_response
from app.services import coupon_service

router = APIRouter()

CouponStatus = Literal["unused", "used", "expired", "revoked"]


class LotteryDrawRequest(BaseModel):
    """Frontend sends the drawn result; backend issues the coupon."""

    discount_value: float = Field(
        ...,
        ge=80,
        le=99,
        description="折扣百分比，80=8折（最多八折），90=9折，95=9.5折",
    )
    prize_name: str = Field(..., min_length=1, max_length=100, description="奖品名称，如「8.5折优惠券」")


class CouponOut(BaseModel):
    id: int | None = None
    coupon_no: str
    name: str
    discount_type: str = "percentage"
    discount_value: float = 0
    min_spend: float = 0
    scope_type: str = "all"
    source: str = "lottery"
    status: CouponStatus | str = "unused"
    valid_from: str | None = None
    valid_until: str | None = None
    used_at: str | None = None
    used_order_id: int | None = None
    discount_amount: float | None = None
    created_at: str | None = None


class LotteryDrawResult(BaseModel):
    is_win: bool = True
    prize_name: str
    discount_value: float | None = None
    coupon: CouponOut | None = None
    record_no: str
    created_at: str | None = None


@router.post("/lottery/draw", response_model=ApiResponse[LotteryDrawResult])
def draw_lottery(
    payload: LotteryDrawRequest,
    request: Request,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    current_user: dict = Depends(require_app_user),
    db: Session = Depends(get_db),
):
    """前端抽奖后调用此接口，后端发放优惠券。

    前端完成抽奖逻辑后，将抽中的折扣力度（discount_value）和奖品名称
    发给后端，后端校验后创建用户优惠券并记录抽奖结果。

    - discount_value 必须 >= 80（最多八折）且 <= 99
    - 每个用户每天最多抽奖 1 次
    - 同一 Idempotency-Key 重复请求返回原结果
    """
    client_ip = request.client.host if request.client else None
    result = coupon_service.issue_lottery_coupon(
        db=db,
        user_id=current_user["user"].id,
        discount_value=payload.discount_value,
        prize_name=payload.prize_name,
        idempotency_key=idempotency_key,
        client_ip=client_ip,
    )
    return success_response(result)


@router.get("/my", response_model=ApiResponse[PageResponse[CouponOut]])
def list_my_coupons(
    status: CouponStatus | None = None,
    page: int = 1,
    page_size: int = 20,
    current_user: dict = Depends(require_app_user),
    db: Session = Depends(get_db),
):
    """查询当前用户的优惠券列表。"""
    result = coupon_service.list_user_coupons(
        db=db,
        user_id=current_user["user"].id,
        status_filter=status,
        page=page,
        page_size=page_size,
    )
    return paginated_response(result["items"], result["page"], result["page_size"], result["total"])
