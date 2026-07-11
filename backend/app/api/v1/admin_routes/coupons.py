"""Admin-side coupon routes.

Admins can:
- Create coupon templates (any discount, no upper-bound)
- Grant coupons to users from templates
- Revoke user coupons
- List all user coupons
- List coupon templates
"""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.security import require_admin
from app.db.session import get_db
from app.schemas.response import ApiResponse, PageResponse, paginated_response, success_response
from app.services import coupon_service

router = APIRouter()

DiscountType = Literal["percentage", "fixed", "fixed_no_threshold"]
ScopeType = Literal["all", "category", "product"]
ValidityType = Literal["relative", "fixed"]
TemplateStatus = Literal["active", "disabled", "archived"]
CouponStatus = Literal["unused", "used", "expired", "revoked"]


class TemplateCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    discount_type: DiscountType
    discount_value: float = Field(..., ge=0)
    min_spend: float = Field(0, ge=0)
    max_discount: float | None = Field(default=None, ge=0)
    scope_type: ScopeType = "all"
    scope_category_id: int | None = None
    scope_product_id: int | None = None
    validity_type: ValidityType = "relative"
    valid_days: int | None = Field(default=None, gt=0)
    fixed_start_at: datetime | None = None
    fixed_end_at: datetime | None = None
    total_quota: int | None = Field(default=None, gt=0)
    per_user_limit: int | None = Field(default=None, gt=0)
    remark: str | None = None


class GrantRequest(BaseModel):
    template_id: int
    user_ids: list[int] = Field(..., min_length=1, max_length=500)
    remark: str | None = None


class RevokeRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=500)


class TemplateStatusUpdateRequest(BaseModel):
    status: TemplateStatus


class TemplateOut(BaseModel):
    id: int | None = None
    coupon_no: str
    name: str
    discount_type: DiscountType
    discount_value: float = 0
    min_spend: float = 0
    max_discount: float | None = None
    scope_type: str = "all"
    scope_category_id: int | None = None
    scope_product_id: int | None = None
    validity_type: str = "relative"
    valid_days: int | None = None
    fixed_start_at: datetime | None = None
    fixed_end_at: datetime | None = None
    total_quota: int | None = None
    issued_count: int = 0
    per_user_limit: int | None = None
    status: str = "active"
    remark: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class CouponOut(BaseModel):
    id: int | None = None
    user_id: int
    user_nickname: str | None = None
    user_email: str | None = None
    coupon_no: str
    template_id: int | None = None
    name: str
    discount_type: DiscountType = "percentage"
    discount_value: float = 0
    min_spend: float = 0
    scope_type: str = "all"
    source: str = "admin_grant"
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


class GrantResult(BaseModel):
    batch_no: str
    template_id: int
    target_count: int
    success_count: int
    coupons: list[CouponOut]


@router.post("/templates", response_model=ApiResponse[TemplateOut])
def create_template(
    payload: TemplateCreateRequest,
    current_admin: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """管理员创建优惠券模板。管理员可创建任意折扣力力的券，无上限约束。"""
    result = coupon_service.admin_create_template(
        db=db,
        name=payload.name,
        discount_type=payload.discount_type,
        discount_value=payload.discount_value,
        min_spend=payload.min_spend,
        max_discount=payload.max_discount,
        scope_type=payload.scope_type,
        scope_category_id=payload.scope_category_id,
        scope_product_id=payload.scope_product_id,
        validity_type=payload.validity_type,
        valid_days=payload.valid_days,
        fixed_start_at=payload.fixed_start_at,
        fixed_end_at=payload.fixed_end_at,
        total_quota=payload.total_quota,
        per_user_limit=payload.per_user_limit,
        remark=payload.remark,
        created_by=current_admin["staff_user"].id,
    )
    return success_response(result)


@router.get("/templates", response_model=ApiResponse[PageResponse[TemplateOut]])
def list_templates(
    status: TemplateStatus | None = None,
    page: int = 1,
    page_size: int = 20,
    current_admin: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """查询优惠券模板列表。"""
    result = coupon_service.admin_list_templates(
        db=db,
        status_filter=status,
        page=page,
        page_size=page_size,
    )
    return paginated_response(result["items"], result["page"], result["page_size"], result["total"])


@router.patch("/templates/{template_id}/status", response_model=ApiResponse[TemplateOut])
def update_template_status(
    template_id: int,
    payload: TemplateStatusUpdateRequest,
    current_admin: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    result = coupon_service.admin_update_template_status(db, template_id, payload.status)
    return success_response(result)


@router.post("/grant", response_model=ApiResponse[GrantResult])
def grant_coupon(
    payload: GrantRequest,
    current_admin: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """管理员向指定用户发放优惠券（基于模板）。管理员发券无折扣上限。"""
    result = coupon_service.admin_grant_coupon(
        db=db,
        template_id=payload.template_id,
        user_ids=payload.user_ids,
        granted_by=current_admin["staff_user"].id,
        remark=payload.remark,
    )
    return success_response(result)


@router.post("/{coupon_id}/revoke", response_model=ApiResponse[CouponOut])
def revoke_coupon(
    coupon_id: int,
    payload: RevokeRequest,
    current_admin: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """管理员作废用户优惠券。"""
    result = coupon_service.admin_revoke_coupon(
        db=db,
        coupon_id=coupon_id,
        revoked_by=current_admin["staff_user"].id,
        reason=payload.reason,
    )
    return success_response(result)


@router.get("", response_model=ApiResponse[PageResponse[CouponOut]])
def list_coupons(
    user_id: int | None = None,
    status: CouponStatus | None = None,
    page: int = 1,
    page_size: int = 20,
    current_admin: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """管理员查看所有用户优惠券列表。"""
    result = coupon_service.admin_list_coupons(
        db=db,
        user_id=user_id,
        status_filter=status,
        page=page,
        page_size=page_size,
    )
    return paginated_response(result["items"], result["page"], result["page_size"], result["total"])
