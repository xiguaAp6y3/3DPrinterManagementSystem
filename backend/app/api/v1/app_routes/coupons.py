"""App-side coupon & lottery routes.

The lottery (prize selection) runs entirely on the frontend.
After the frontend draws a prize, it calls ``POST /lottery/draw`` to
have the backend issue the coupon to the logged-in user.

Three discount types supported:
- percentage: discount_value=80 → 8折 (20% off, max discount for users)
- fixed: 满减, discount_value=减免金额, min_spend=门槛
- fixed_no_threshold: 立减, discount_value=减免金额, 无门槛

User-issued (lottery) coupons are constrained:
- percentage: 80 <= discount_value <= 99
- fixed: discount_value <= min_spend * 20%
- fixed_no_threshold: discount_value <= 5
"""

from datetime import datetime
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
DiscountType = Literal["percentage", "fixed", "fixed_no_threshold"]


class LotteryDrawRequest(BaseModel):
    """Frontend sends the drawn result; backend issues the coupon."""

    discount_type: DiscountType = Field(
        ...,
        description="折扣类型: percentage=折扣率, fixed=满减, fixed_no_threshold=立减",
    )
    discount_value: float = Field(
        ...,
        ge=0,
        description="折扣值: percentage时80=8折, fixed/立减时为减免金额",
    )
    prize_name: str = Field(..., min_length=1, max_length=100, description="奖品名称")
    min_spend: float = Field(0, ge=0, description="满减门槛金额（fixed类型时使用）")


class CouponOut(BaseModel):
    id: int | None = None
    coupon_no: str
    template_id: int | None = None
    name: str
    discount_type: DiscountType = "percentage"
    discount_value: float = 0
    min_spend: float = 0
    scope_type: str = "all"
    source: str = "lottery"
    status: CouponStatus | str = "unused"
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    used_at: datetime | None = None
    used_order_id: int | None = None
    discount_amount: float | None = None
    revoked_at: datetime | None = None
    revoke_reason: str | None = None
    created_by: int | None = None
    created_at: datetime | None = None


class LotteryDrawResult(BaseModel):
    is_win: bool = True
    prize_name: str
    discount_value: float | None = None
    coupon: CouponOut | None = None
    record_no: str
    remaining_draws: int = 0
    created_at: datetime | None = None


@router.post("/lottery/draw", response_model=ApiResponse[LotteryDrawResult])
def draw_lottery(
    payload: LotteryDrawRequest,
    request: Request,
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=1, max_length=100),
    current_user: dict = Depends(require_app_user),
    db: Session = Depends(get_db),
):
    """前端抽奖后调用此接口，后端发放优惠券。

    前端完成抽奖逻辑后，将抽中的券类型、折扣值和奖品名称
    发给后端，后端校验后创建用户优惠券并记录抽奖结果。

    用户折扣上限：
    - percentage: discount_value >= 80（最多八折）
    - fixed: discount_value <= min_spend * 20%（如满30最多减6）
    - fixed_no_threshold: discount_value <= 5（最多减5元）

    每个用户最多抽奖 3 次。同一 Idempotency-Key 重复请求返回原结果。
    """
    client_ip = request.client.host if request.client else None
    result = coupon_service.issue_lottery_coupon(
        db=db,
        user_id=current_user["user"].id,
        discount_type=payload.discount_type,
        discount_value=payload.discount_value,
        prize_name=payload.prize_name,
        idempotency_key=idempotency_key,
        min_spend=payload.min_spend,
        client_ip=client_ip,
    )
    return success_response(result)


@router.get("", response_model=ApiResponse[PageResponse[CouponOut]])
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
