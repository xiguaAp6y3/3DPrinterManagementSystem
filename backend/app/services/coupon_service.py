"""Coupon & lottery service.

Supports three discount types:
- percentage: 折扣率, discount_value=80 → 8折(减免20%)
- fixed: 满减, discount_value=减金额, 需满足 min_spend 门槛
- fixed_no_threshold: 立减, discount_value=减金额, 无门槛

Permission levels:
- User token (lottery): constrained discount upper-bounds
  - percentage: 80 <= discount_value <= 99 (最多八折)
  - fixed: discount_value <= min_spend * 20% (如满30最多减6)
  - fixed_no_threshold: discount_value <= 5 (最多减5元)
- Admin token: no discount limits, can issue any coupon.

Order integration:
  actual_payment = max(order_total - discount_amount, 0)  # 折扣地板 0 元
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session
from starlette import status

from app.core.errors import AppError
from app.db.models.core import (
    CouponGrantBatch,
    CouponTemplate,
    LotteryRecord,
    Order,
    OrderItem,
    Product,
    ProductCategory,
    User,
    UserCoupon,
)
from app.services.db_helpers import next_no, paginate, to_float

# --- Constants --------------------------------------------------------------

# 用户抽奖最多抽取次数（总计）
MAX_DRAWS_PER_USER = 3

# 用户抽奖折扣上限
MIN_PERCENTAGE = 80   # 最多八折
MAX_PERCENTAGE = 99   # 几乎无折扣
MAX_FIXED_RATIO = 0.20  # 满减最多 min_spend 的 20%
MAX_FIXED_NO_THRESHOLD = 5  # 立减最多 5 元

# 优惠券有效期天数
COUPON_VALID_DAYS = 30

VALID_DISCOUNT_TYPES = {"percentage", "fixed", "fixed_no_threshold"}
VALID_SCOPE_TYPES = {"all", "category", "product"}
VALID_SOURCES = {"lottery", "admin_grant", "signup_gift", "promotion"}
VALID_STATUSES = {"unused", "used", "expired", "revoked"}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# --- Lottery coupon issuance (user token) ------------------------------------

def issue_lottery_coupon(
    db: Session,
    user_id: int,
    discount_type: str,
    discount_value: float,
    prize_name: str,
    idempotency_key: str,
    min_spend: float = 0,
    client_ip: str | None = None,
) -> dict:
    """Issue a coupon to a user after a frontend lottery draw.

    The frontend has already decided the prize; this function validates,
    persists, and returns the coupon. User-issued coupons are constrained.
    """
    locked_user = db.scalar(
        select(User)
        .where(User.id == user_id, User.deleted_at.is_(None))
        .with_hint(User, "WITH (UPDLOCK, HOLDLOCK)", dialect_name="mssql")
    )
    if locked_user is None:
        raise AppError("COUPON_USER_NOT_FOUND", "用户不存在或已删除", status.HTTP_404_NOT_FOUND)

    # 1. 校验券类型
    if discount_type not in VALID_DISCOUNT_TYPES:
        raise AppError(
            "COUPON_INVALID_TYPE",
            f"不支持的折扣类型: {discount_type}",
            status.HTTP_400_BAD_REQUEST,
        )

    # 2. 用户折扣上限校验
    _validate_user_discount_limit(discount_type, discount_value, min_spend)

    # 3. 幂等校验
    existing = db.scalar(
        select(LotteryRecord).where(
            LotteryRecord.user_id == user_id,
            LotteryRecord.idempotency_key == idempotency_key,
        )
    )
    if existing:
        coupon = db.get(UserCoupon, existing.won_coupon_id) if existing.won_coupon_id else None
        return _serialize_lottery_result(existing, coupon)

    # 4. 抽奖次数限制（总计 MAX_DRAWS_PER_USER 次）
    total_draws = db.scalar(
        select(func.count()).select_from(LotteryRecord).where(
            LotteryRecord.user_id == user_id,
        )
    ) or 0
    if total_draws >= MAX_DRAWS_PER_USER:
        raise AppError(
            "LOTTERY_DRAWS_EXHAUSTED",
            f"抽奖次数已用尽（最多 {MAX_DRAWS_PER_USER} 次）",
            status.HTTP_409_CONFLICT,
        )

    # 5. 创建用户优惠券
    now = _utcnow()
    coupon = UserCoupon(
        coupon_no=next_no(db, "seq_coupon_no", "UC"),
        user_id=user_id,
        template_id=None,
        name=prize_name,
        discount_type=discount_type,
        discount_value=discount_value,
        min_spend=min_spend,
        scope_type="all",
        source="lottery",
        status="unused",
        valid_from=now,
        valid_until=now + timedelta(days=COUPON_VALID_DAYS),
    )
    db.add(coupon)
    db.flush()

    # 6. 记录抽奖结果
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

    remaining = MAX_DRAWS_PER_USER - (total_draws + 1)
    return _serialize_lottery_result(record, coupon, remaining)


def _validate_user_discount_limit(
    discount_type: str, discount_value: float, min_spend: float
) -> None:
    """Validate that a user-issued (lottery) coupon respects discount upper-bounds."""
    if discount_value < 0:
        raise AppError(
            "COUPON_INVALID_DISCOUNT",
            "折扣金额不能为负数",
            status.HTTP_400_BAD_REQUEST,
        )

    if discount_type == "percentage":
        if discount_value < MIN_PERCENTAGE or discount_value > MAX_PERCENTAGE:
            raise AppError(
                "COUPON_INVALID_DISCOUNT",
                f"百分比折扣必须在 {MIN_PERCENTAGE}-{MAX_PERCENTAGE} 之间（最多八折）",
                status.HTTP_400_BAD_REQUEST,
            )

    elif discount_type == "fixed":
        # 满减: 最多减 min_spend 的 20%
        max_discount = to_float(Decimal(str(min_spend)) * Decimal(str(MAX_FIXED_RATIO)))
        if discount_value > max_discount:
            raise AppError(
                "COUPON_INVALID_DISCOUNT",
                f"满减券最多减免 min_spend 的 {int(MAX_FIXED_RATIO * 100)}%："
                f"满 {min_spend} 最多减 {max_discount}",
                status.HTTP_400_BAD_REQUEST,
            )

    elif discount_type == "fixed_no_threshold":
        # 立减: 最多减 5 元
        if discount_value > MAX_FIXED_NO_THRESHOLD:
            raise AppError(
                "COUPON_INVALID_DISCOUNT",
                f"立减券最多减免 {MAX_FIXED_NO_THRESHOLD} 元",
                status.HTTP_400_BAD_REQUEST,
            )


# --- Admin coupon operations -------------------------------------------------

def admin_create_template(
    db: Session,
    name: str,
    discount_type: str,
    discount_value: float,
    min_spend: float = 0,
    max_discount: float | None = None,
    scope_type: str = "all",
    scope_category_id: int | None = None,
    scope_product_id: int | None = None,
    validity_type: str = "relative",
    valid_days: int | None = None,
    fixed_start_at: datetime | None = None,
    fixed_end_at: datetime | None = None,
    total_quota: int | None = None,
    per_user_limit: int | None = None,
    remark: str | None = None,
    created_by: int | None = None,
) -> dict:
    """Admin creates a coupon template. No discount upper-bound at admin level."""
    if discount_type not in VALID_DISCOUNT_TYPES:
        raise AppError(
            "COUPON_INVALID_TYPE",
            f"不支持的折扣类型: {discount_type}",
            status.HTTP_400_BAD_REQUEST,
        )

    if scope_type not in VALID_SCOPE_TYPES:
        raise AppError(
            "COUPON_INVALID_SCOPE",
            f"不支持的作用域: {scope_type}",
            status.HTTP_400_BAD_REQUEST,
        )

    if scope_type == "category" and scope_category_id is None:
        raise AppError(
            "COUPON_SCOPE_TARGET_REQUIRED",
            "分类券必须指定 scope_category_id",
            status.HTTP_400_BAD_REQUEST,
        )
    if scope_type == "category" and db.get(ProductCategory, scope_category_id) is None:
        raise AppError(
            "COUPON_SCOPE_TARGET_NOT_FOUND",
            "指定的商品分类不存在",
            status.HTTP_404_NOT_FOUND,
        )
    if scope_type == "product" and scope_product_id is None:
        raise AppError(
            "COUPON_SCOPE_TARGET_REQUIRED",
            "商品券必须指定 scope_product_id",
            status.HTTP_400_BAD_REQUEST,
        )
    if scope_type == "product":
        product = db.get(Product, scope_product_id)
        if product is None or product.is_deleted:
            raise AppError(
                "COUPON_SCOPE_TARGET_NOT_FOUND",
                "指定的商品不存在",
                status.HTTP_404_NOT_FOUND,
            )
    if scope_type != "category" and scope_category_id is not None:
        raise AppError(
            "COUPON_SCOPE_TARGET_INVALID",
            "非分类券不能指定 scope_category_id",
            status.HTTP_400_BAD_REQUEST,
        )
    if scope_type != "product" and scope_product_id is not None:
        raise AppError(
            "COUPON_SCOPE_TARGET_INVALID",
            "非商品券不能指定 scope_product_id",
            status.HTTP_400_BAD_REQUEST,
        )

    if validity_type == "relative":
        if not valid_days or valid_days <= 0:
            raise AppError(
                "COUPON_INVALID_VALIDITY",
                "相对有效期必须指定 valid_days > 0",
                status.HTTP_400_BAD_REQUEST,
            )
    elif validity_type == "fixed":
        if not fixed_start_at or not fixed_end_at:
            raise AppError(
                "COUPON_INVALID_VALIDITY",
                "固定有效期必须指定 fixed_start_at 和 fixed_end_at",
                status.HTTP_400_BAD_REQUEST,
            )
        if fixed_end_at <= fixed_start_at:
            raise AppError(
                "COUPON_INVALID_VALIDITY",
                "固定有效期结束时间必须晚于开始时间",
                status.HTTP_400_BAD_REQUEST,
            )
    else:
        raise AppError(
            "COUPON_INVALID_VALIDITY",
            f"不支持的有效期类型: {validity_type}",
            status.HTTP_400_BAD_REQUEST,
        )

    template = CouponTemplate(
        coupon_no=next_no(db, "seq_coupon_no", "CT"),
        name=name,
        discount_type=discount_type,
        discount_value=discount_value,
        min_spend=min_spend,
        max_discount=max_discount,
        scope_type=scope_type,
        scope_category_id=scope_category_id,
        scope_product_id=scope_product_id,
        validity_type=validity_type,
        valid_days=valid_days,
        fixed_start_at=fixed_start_at,
        fixed_end_at=fixed_end_at,
        total_quota=total_quota,
        issued_count=0,
        per_user_limit=per_user_limit,
        status="active",
        remark=remark,
        created_by=created_by,
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return _serialize_template(template)


def admin_list_templates(
    db: Session,
    status_filter: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    stmt = select(CouponTemplate).order_by(CouponTemplate.created_at.desc())
    if status_filter:
        stmt = stmt.where(CouponTemplate.status == status_filter)
    items, page, page_size, total = paginate(db, stmt, page, page_size)
    return {
        "items": [_serialize_template(t) for t in items],
        "page": page,
        "page_size": page_size,
        "total": total,
    }


def admin_grant_coupon(
    db: Session,
    template_id: int,
    user_ids: list[int],
    granted_by: int,
    remark: str | None = None,
) -> dict:
    """Admin grants coupons from a template to specified users. No discount limits."""
    if not user_ids:
        raise AppError(
            "COUPON_USERS_REQUIRED",
            "至少需要指定一个用户",
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    if len(user_ids) != len(set(user_ids)):
        raise AppError(
            "COUPON_DUPLICATE_USERS",
            "用户列表中不能包含重复用户",
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    users = db.scalars(
        select(User).where(
            User.id.in_(user_ids),
            User.deleted_at.is_(None),
        )
    ).all()
    users_by_id = {user.id: user for user in users}
    existing_user_ids = {user.id for user in users}
    missing_user_ids = [user_id for user_id in user_ids if user_id not in existing_user_ids]
    if missing_user_ids:
        raise AppError(
            "COUPON_USER_NOT_FOUND",
            "部分用户不存在或已删除",
            status.HTTP_404_NOT_FOUND,
            details={"user_ids": missing_user_ids},
        )

    template = db.scalar(
        select(CouponTemplate)
        .where(CouponTemplate.id == template_id)
        .with_hint(CouponTemplate, "WITH (UPDLOCK, HOLDLOCK)", dialect_name="mssql")
    )
    if not template or template.status != "active":
        raise AppError(
            "COUPON_TEMPLATE_NOT_FOUND",
            "优惠券模板不存在或已停用",
            status.HTTP_404_NOT_FOUND,
        )

    # 检查模板配额
    if template.total_quota is not None:
        remaining = template.total_quota - (template.issued_count or 0)
        if remaining < len(user_ids):
            raise AppError(
                "COUPON_QUOTA_EXCEEDED",
                f"模板剩余配额不足：剩余 {remaining}，需要 {len(user_ids)}",
                status.HTTP_409_CONFLICT,
            )

    # 检查每人限领
    if template.per_user_limit is not None:
        for uid in user_ids:
            existing_count = db.scalar(
                select(func.count()).select_from(UserCoupon).where(
                    UserCoupon.template_id == template_id,
                    UserCoupon.user_id == uid,
                )
            ) or 0
            if existing_count >= template.per_user_limit:
                raise AppError(
                    "COUPON_PER_USER_LIMIT",
                    f"用户 {uid} 已达到此优惠券的领取上限 ({template.per_user_limit})",
                    status.HTTP_409_CONFLICT,
                )

    now = _utcnow()
    success_count = 0
    coupons: list[UserCoupon] = []

    for uid in user_ids:
        # 计算有效期
        if template.validity_type == "relative":
            valid_from = now
            valid_until = now + timedelta(days=template.valid_days or 30)
        else:
            valid_from = template.fixed_start_at or now
            valid_until = template.fixed_end_at or (now + timedelta(days=30))

        coupon = UserCoupon(
            coupon_no=next_no(db, "seq_coupon_no", "UC"),
            user_id=uid,
            template_id=template.id,
            name=template.name,
            discount_type=template.discount_type,
            discount_value=template.discount_value,
            min_spend=template.min_spend,
            scope_type=template.scope_type,
            source="admin_grant",
            status="unused",
            valid_from=valid_from,
            valid_until=valid_until,
            created_by=granted_by,
        )
        db.add(coupon)
        db.flush()
        coupons.append(coupon)
        success_count += 1

    # 更新模板已发放数量
    template.issued_count = (template.issued_count or 0) + success_count

    # 创建发放批次记录
    batch = CouponGrantBatch(
        batch_no=next_no(db, "seq_grant_batch_no", "GB"),
        template_id=template.id,
        granted_by=granted_by,
        target_type="specified_users" if len(user_ids) > 1 else "single_user",
        target_count=len(user_ids),
        success_count=success_count,
        remark=remark,
    )
    db.add(batch)
    db.commit()

    return {
        "batch_no": batch.batch_no,
        "template_id": template.id,
        "target_count": len(user_ids),
        "success_count": success_count,
        "coupons": [_serialize_coupon(coupon, users_by_id.get(coupon.user_id)) for coupon in coupons],
    }


def admin_revoke_coupon(
    db: Session,
    coupon_id: int,
    revoked_by: int,
    reason: str,
) -> dict:
    """Admin revokes a user coupon."""
    coupon = db.scalar(
        select(UserCoupon)
        .where(UserCoupon.id == coupon_id)
        .with_hint(UserCoupon, "WITH (UPDLOCK, HOLDLOCK)", dialect_name="mssql")
    )
    if not coupon:
        raise AppError(
            "COUPON_NOT_FOUND",
            "优惠券不存在",
            status.HTTP_404_NOT_FOUND,
        )
    if coupon.status == "used":
        raise AppError(
            "COUPON_ALREADY_USED",
            "已使用的优惠券不能作废",
            status.HTTP_409_CONFLICT,
        )
    if coupon.status == "revoked":
        raise AppError(
            "COUPON_ALREADY_REVOKED",
            "优惠券已被作废",
            status.HTTP_409_CONFLICT,
        )

    coupon.status = "revoked"
    coupon.revoked_at = _utcnow()
    coupon.revoked_by = revoked_by
    coupon.revoke_reason = reason
    db.commit()
    db.refresh(coupon)
    return _serialize_coupon(coupon, db.get(User, coupon.user_id))


def admin_list_coupons(
    db: Session,
    user_id: int | None = None,
    status_filter: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """Admin views all user coupons with optional filters."""
    stmt = select(UserCoupon).order_by(UserCoupon.created_at.desc())
    if user_id:
        stmt = stmt.where(UserCoupon.user_id == user_id)
    stmt = _apply_coupon_status_filter(stmt, status_filter)
    items, page, page_size, total = paginate(db, stmt, page, page_size)
    user_ids = {coupon.user_id for coupon in items}
    users = db.scalars(select(User).where(User.id.in_(user_ids))).all() if user_ids else []
    users_by_id = {user.id: user for user in users}
    return {
        "items": [_serialize_coupon(coupon, users_by_id.get(coupon.user_id)) for coupon in items],
        "page": page,
        "page_size": page_size,
        "total": total,
    }


# --- Order integration: discount calculation ---------------------------------

def calculate_discount(
    discount_type: str,
    discount_value: float,
    min_spend: float,
    order_total: float,
) -> float:
    """Compute the discount amount for a given order total.

    Returns the discount amount (always >= 0). The caller is responsible
    for applying the floor: actual_payment = max(order_total - discount, 0).
    """
    if order_total < 0:
        return 0.0

    if discount_type == "percentage":
        # discount_value=80 → 8折 → 减免 20%
        discount = order_total * (1 - discount_value / 100.0)

    elif discount_type == "fixed":
        # 满减: 必须满足 min_spend 门槛
        if order_total < min_spend:
            return 0.0
        discount = discount_value

    elif discount_type == "fixed_no_threshold":
        # 立减: 无门槛
        discount = discount_value

    else:
        discount = 0.0

    return max(discount, 0.0)


def validate_and_apply_coupon(
    db: Session,
    coupon_id: int,
    user_id: int,
    order_total: float,
    order_id: int,
) -> dict:
    """Validate a coupon for an order, compute discount, and lock the coupon.

    Returns dict with: coupon_id, discount_amount, final_amount.
    Raises AppError on any validation failure.
    """
    coupon = db.scalar(
        select(UserCoupon)
        .where(UserCoupon.id == coupon_id)
        .with_hint(UserCoupon, "WITH (UPDLOCK, ROWLOCK)", dialect_name="mssql")
    )
    if not coupon:
        raise AppError(
            "COUPON_NOT_FOUND",
            "优惠券不存在",
            status.HTTP_404_NOT_FOUND,
        )

    # 1. 归属校验
    if coupon.user_id != user_id:
        raise AppError(
            "COUPON_NOT_OWNED",
            "优惠券不属于当前用户",
            status.HTTP_403_FORBIDDEN,
        )

    # 2. 状态校验
    if coupon.status != "unused":
        raise AppError(
            "COUPON_NOT_USABLE",
            f"优惠券状态为 {coupon.status}，不可使用",
            status.HTTP_409_CONFLICT,
        )

    # 3. 有效期校验
    now = _utcnow()
    if now < coupon.valid_from:
        raise AppError(
            "COUPON_NOT_YET_VALID",
            "优惠券尚未生效",
            status.HTTP_409_CONFLICT,
        )
    if now > coupon.valid_until:
        raise AppError(
            "COUPON_EXPIRED",
            "优惠券已过期",
            status.HTTP_409_CONFLICT,
        )

    eligible_total = _coupon_eligible_total(db, coupon, order_id, order_total)

    # 4. 满减门槛校验
    min_spend_val = to_float(coupon.min_spend) or 0
    if coupon.discount_type == "fixed" and eligible_total < min_spend_val:
        raise AppError(
            "COUPON_MIN_SPEND_NOT_MET",
            f"适用商品金额 {eligible_total} 未满足最低消费 {to_float(coupon.min_spend)}",
            status.HTTP_409_CONFLICT,
        )

    # 5. 计算折扣金额
    discount_amount = calculate_discount(
        coupon.discount_type,
        to_float(coupon.discount_value) or 0,
        to_float(coupon.min_spend) or 0,
        eligible_total,
    )

    template = db.get(CouponTemplate, coupon.template_id) if coupon.template_id else None
    max_discount = to_float(template.max_discount) if template else None
    if max_discount is not None:
        discount_amount = min(discount_amount, max_discount)

    # 6. 折扣地板：实付最低 0 元
    final_amount = max(order_total - discount_amount, 0.0)

    # 7. 锁定券
    coupon.status = "used"
    coupon.used_at = now
    coupon.used_order_id = order_id
    coupon.discount_amount = discount_amount

    db.flush()
    return {
        "coupon_id": coupon.id,
        "discount_amount": discount_amount,
        "final_amount": final_amount,
    }


# --- User coupon listing -----------------------------------------------------

def list_user_coupons(
    db: Session,
    user_id: int,
    status_filter: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """List coupons belonging to a user with optional status filter."""
    stmt = (
        select(UserCoupon)
        .where(UserCoupon.user_id == user_id)
        .order_by(UserCoupon.created_at.desc())
    )
    stmt = _apply_coupon_status_filter(stmt, status_filter)

    items, page, page_size, total = paginate(db, stmt, page, page_size)
    return {
        "items": [_serialize_coupon(c) for c in items],
        "page": page,
        "page_size": page_size,
        "total": total,
    }


# --- Serialization -----------------------------------------------------------

def _serialize_template(t: CouponTemplate) -> dict:
    return {
        "id": t.id,
        "coupon_no": t.coupon_no,
        "name": t.name,
        "discount_type": t.discount_type,
        "discount_value": to_float(t.discount_value) or 0,
        "min_spend": to_float(t.min_spend) or 0,
        "max_discount": to_float(t.max_discount),
        "scope_type": t.scope_type,
        "scope_category_id": t.scope_category_id,
        "scope_product_id": t.scope_product_id,
        "validity_type": t.validity_type,
        "valid_days": t.valid_days,
        "fixed_start_at": t.fixed_start_at,
        "fixed_end_at": t.fixed_end_at,
        "total_quota": t.total_quota,
        "issued_count": t.issued_count,
        "per_user_limit": t.per_user_limit,
        "status": t.status,
        "remark": t.remark,
        "created_at": t.created_at,
        "updated_at": t.updated_at,
    }


def _serialize_coupon(coupon: UserCoupon, user: User | None = None) -> dict:
    return {
        "id": coupon.id,
        "user_id": coupon.user_id,
        "user_nickname": user.nickname if user else None,
        "user_email": user.email if user else None,
        "coupon_no": coupon.coupon_no,
        "template_id": coupon.template_id,
        "name": coupon.name,
        "discount_type": coupon.discount_type,
        "discount_value": to_float(coupon.discount_value) or 0,
        "min_spend": to_float(coupon.min_spend) or 0,
        "scope_type": coupon.scope_type,
        "source": coupon.source,
        "status": _effective_coupon_status(coupon),
        "valid_from": coupon.valid_from,
        "valid_until": coupon.valid_until,
        "used_at": coupon.used_at,
        "used_order_id": coupon.used_order_id,
        "discount_amount": to_float(coupon.discount_amount),
        "revoked_at": coupon.revoked_at,
        "revoke_reason": coupon.revoke_reason,
        "created_by": coupon.created_by,
        "created_at": coupon.created_at,
    }


def admin_update_template_status(db: Session, template_id: int, template_status: str) -> dict:
    if template_status not in {"active", "disabled", "archived"}:
        raise AppError("COUPON_INVALID_STATUS", "不支持的优惠券模板状态", status.HTTP_400_BAD_REQUEST)
    template = db.scalar(
        select(CouponTemplate)
        .where(CouponTemplate.id == template_id)
        .with_hint(CouponTemplate, "WITH (UPDLOCK, HOLDLOCK)", dialect_name="mssql")
    )
    if template is None:
        raise AppError("COUPON_TEMPLATE_NOT_FOUND", "优惠券模板不存在", status.HTTP_404_NOT_FOUND)
    template.status = template_status
    db.commit()
    db.refresh(template)
    return _serialize_template(template)


def _coupon_eligible_total(db: Session, coupon: UserCoupon, order_id: int, order_total: float) -> float:
    if coupon.scope_type == "all":
        return order_total

    template = db.get(CouponTemplate, coupon.template_id) if coupon.template_id else None
    if template is None:
        raise AppError(
            "COUPON_SCOPE_INVALID",
            "优惠券缺少有效的适用范围配置",
            status.HTTP_409_CONFLICT,
        )

    order_items = db.scalars(select(OrderItem).where(OrderItem.order_id == order_id)).all()
    eligible_total = 0.0
    for item in order_items:
        if coupon.scope_type == "product" and item.product_id == template.scope_product_id:
            eligible_total += to_float(item.subtotal) or 0
        elif coupon.scope_type == "category":
            product = db.get(Product, item.product_id) if item.product_id else None
            if product and product.category_id == template.scope_category_id:
                eligible_total += to_float(item.subtotal) or 0

    if eligible_total <= 0:
        raise AppError(
            "COUPON_SCOPE_NOT_MATCHED",
            "订单中没有该优惠券适用的商品",
            status.HTTP_409_CONFLICT,
        )
    return eligible_total


def _apply_coupon_status_filter(stmt, status_filter: str | None):
    now = _utcnow()
    if status_filter == "expired":
        return stmt.where(
            or_(
                UserCoupon.status == "expired",
                and_(UserCoupon.status == "unused", UserCoupon.valid_until < now),
            )
        )
    if status_filter == "unused":
        return stmt.where(UserCoupon.status == "unused", UserCoupon.valid_until >= now)
    if status_filter:
        return stmt.where(UserCoupon.status == status_filter)
    return stmt


def _effective_coupon_status(coupon: UserCoupon) -> str:
    if coupon.status == "unused" and coupon.valid_until < _utcnow():
        return "expired"
    return coupon.status


def _serialize_lottery_result(
    record: LotteryRecord, coupon: UserCoupon | None, remaining_draws: int = 0
) -> dict:
    return {
        "is_win": record.is_win,
        "prize_name": record.prize_name,
        "discount_value": to_float(record.discount_value),
        "coupon": _serialize_coupon(coupon) if coupon else None,
        "record_no": record.record_no,
        "remaining_draws": remaining_draws,
        "created_at": record.created_at,
    }
