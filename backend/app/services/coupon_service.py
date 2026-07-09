"""Coupon & lottery service for the demo.

Design:
- The lottery (random prize selection) runs on the frontend.
- The frontend calls ``issue_lottery_coupon`` with the drawn result.
- The backend enforces the max-discount rule (最多八折, discount_value >= 80)
  and persists the coupon + a lottery record atomically.

discount_value convention (percentage):
    80  = 8折   (20% off, the maximum discount allowed)
    85  = 8.5折 (15% off)
    90  = 9折   (10% off)
    95  = 9.5折 (5%  off)
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette import status

from app.core.errors import AppError
from app.db.models.core import LotteryRecord, UserCoupon
from app.services.db_helpers import next_no, to_float

# 最多八折：discount_value 不能低于 80（80 = 8折 = 减免20%）
MIN_DISCOUNT_VALUE = 80
# 无折扣上限：100 表示原价，不享受折扣
MAX_DISCOUNT_VALUE = 99

# 每个用户每天最多抽奖次数
DAILY_DRAW_LIMIT = 1

# 优惠券有效期天数（自发放之日起）
COUPON_VALID_DAYS = 30


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def issue_lottery_coupon(
    db: Session,
    user_id: int,
    discount_value: float,
    prize_name: str,
    idempotency_key: str,
    client_ip: str | None = None,
) -> dict:
    """Issue a percentage-discount coupon to a user after a frontend lottery draw.

    The frontend has already decided the prize; this function only validates,
    persists, and returns the coupon.
    """
    # 1. 校验折扣力度：最多八折
    if discount_value < MIN_DISCOUNT_VALUE or discount_value > MAX_DISCOUNT_VALUE:
        raise AppError(
            "COUPON_INVALID_DISCOUNT",
            f"折扣力度不合法，discount_value 必须在 {MIN_DISCOUNT_VALUE}-{MAX_DISCOUNT_VALUE} 之间（最多八折）",
            status.HTTP_400_BAD_REQUEST,
        )

    # 2. 幂等校验：同一用户 + 同一 idempotency_key 只生效一次
    existing = db.scalar(
        select(LotteryRecord).where(
            LotteryRecord.user_id == user_id,
            LotteryRecord.idempotency_key == idempotency_key,
        )
    )
    if existing:
        # 返回已有记录的结果
        coupon = db.get(UserCoupon, existing.won_coupon_id) if existing.won_coupon_id else None
        return _serialize_lottery_result(existing, coupon)

    # 3. 每日抽奖次数限制
    today_start = _utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_count = db.scalar(
        select(func.count()).select_from(LotteryRecord).where(
            LotteryRecord.user_id == user_id,
            LotteryRecord.created_at >= today_start,
        )
    ) or 0
    if today_count >= DAILY_DRAW_LIMIT:
        raise AppError(
            "LOTTERY_DAILY_DRAWS_EXHAUSTED",
            f"每天最多抽奖 {DAILY_DRAW_LIMIT} 次",
            status.HTTP_409_CONFLICT,
        )

    # 4. 创建用户优惠券（有效期 30 天）
    now = _utcnow()
    coupon = UserCoupon(
        coupon_no=next_no(db, "seq_coupon_no", "UC"),
        user_id=user_id,
        name=prize_name,
        discount_type="percentage",
        discount_value=discount_value,
        min_spend=0,
        scope_type="all",
        source="lottery",
        status="unused",
        valid_from=now,
        valid_until=now + timedelta(days=COUPON_VALID_DAYS),
    )
    db.add(coupon)
    db.flush()

    # 5. 记录抽奖结果
    record = LotteryRecord(
        record_no=next_no(db, "seq_lottery_record_no", "LR"),
        user_id=user_id,
        is_win=True,
        prize_name=prize_name,
        discount_value=discount_value,
        won_coupon_id=coupon.id,
        idempotency_key=idempotency_key,
        client_ip=client_ip,
    )
    db.add(record)
    db.commit()
    db.refresh(coupon)
    db.refresh(record)

    return _serialize_lottery_result(record, coupon)


def list_user_coupons(
    db: Session,
    user_id: int,
    status_filter: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """List coupons belonging to a user with optional status filter."""
    from app.services.db_helpers import paginate

    stmt = (
        select(UserCoupon)
        .where(UserCoupon.user_id == user_id)
        .order_by(UserCoupon.created_at.desc())
    )
    if status_filter:
        stmt = stmt.where(UserCoupon.status == status_filter)

    items, page, page_size, total = paginate(db, stmt, page, page_size)
    return {
        "items": [_serialize_coupon(c) for c in items],
        "page": page,
        "page_size": page_size,
        "total": total,
    }


def _serialize_coupon(coupon: UserCoupon) -> dict:
    return {
        "id": coupon.id,
        "coupon_no": coupon.coupon_no,
        "name": coupon.name,
        "discount_type": coupon.discount_type,
        "discount_value": to_float(coupon.discount_value) or 0,
        "min_spend": to_float(coupon.min_spend) or 0,
        "scope_type": coupon.scope_type,
        "source": coupon.source,
        "status": coupon.status,
        "valid_from": coupon.valid_from,
        "valid_until": coupon.valid_until,
        "used_at": coupon.used_at,
        "used_order_id": coupon.used_order_id,
        "discount_amount": to_float(coupon.discount_amount),
        "created_at": coupon.created_at,
    }


def _serialize_lottery_result(record: LotteryRecord, coupon: UserCoupon | None) -> dict:
    return {
        "is_win": record.is_win,
        "prize_name": record.prize_name,
        "discount_value": to_float(record.discount_value),
        "coupon": _serialize_coupon(coupon) if coupon else None,
        "record_no": record.record_no,
        "created_at": record.created_at,
    }
