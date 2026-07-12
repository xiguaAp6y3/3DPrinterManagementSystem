from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.security import require_admin
from app.core.time import utc_now
from app.db.models.core import Order, OrderItem, PrintTask, ProductionScheduleOrder, Shipment, ShipmentPackage
from app.db.session import get_db
from app.schemas.response import ApiResponse, PageResponse, paginated_response, success_response
from app.services.db_helpers import paginate, require_entity, to_float
from app.services.order_status import sync_order_shipping_status

router = APIRouter()

OrderType = Literal["listed_product", "custom"]
OrderStatus = Literal["submitted", "reviewing", "quoted", "quote_confirmed", "payment_confirmed", "scheduled", "printing", "post_processing", "quality_check", "partially_completed", "completed", "partially_inbound", "in_warehouse", "ready_to_ship", "shipping", "partially_shipped", "shipped", "cancelled"]
PaymentStatus = Literal["unconfirmed", "confirmed", "cancelled"]


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
    shipments: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime | None = None


@router.get("", response_model=ApiResponse[PageResponse[OrderDetail]])
def list_orders(page: int = 1, page_size: int = 20, order_type: OrderType | None = None, status: OrderStatus | None = None, payment_status: PaymentStatus | None = None, keyword: str | None = None, created_from: datetime | None = None, created_to: datetime | None = None, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    stmt = select(Order).order_by(Order.created_at.desc())
    if order_type:
        stmt = stmt.where(Order.order_type == order_type)
    if status:
        stmt = stmt.where(Order.status == status)
    if payment_status:
        stmt = stmt.where(Order.payment_status == payment_status)
    if keyword:
        stmt = stmt.where(or_(Order.order_no.contains(keyword), Order.customer_note.contains(keyword), Order.admin_note.contains(keyword)))
    if created_from:
        stmt = stmt.where(Order.created_at >= created_from)
    if created_to:
        stmt = stmt.where(Order.created_at <= created_to)
    items, page, page_size, total = paginate(db, stmt, page, page_size)
    return paginated_response([serialize_order_detail(db, item, shallow=True) for item in items], page, page_size, total)


@router.get("/{order_id}", response_model=ApiResponse[OrderDetail])
def get_order(order_id: int, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    order = require_entity(db.get(Order, order_id), "订单不存在")
    if order.status in {"shipping", "partially_shipped"}:
        previous_status = order.status
        sync_order_shipping_status(db, order.id)
        if order.status != previous_status:
            db.commit()
            db.refresh(order)
    return success_response(serialize_order_detail(db, order))


@router.patch("/{order_id}/status", response_model=ApiResponse[OrderDetail])
def update_order_status(order_id: int, payload: OrderStatusUpdate, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    order = require_entity(db.get(Order, order_id), "订单不存在")
    order.status = payload.status
    if payload.remark:
        order.admin_note = payload.remark
    db.commit()
    db.refresh(order)
    return success_response(serialize_order_detail(db, order))


@router.post("/{order_id}/payment-confirm", response_model=ApiResponse[OrderDetail])
def confirm_payment(order_id: int, payload: PaymentConfirmRequest | None = None, idempotency_key: str = Header(alias="Idempotency-Key"), current_admin: dict = Depends(require_admin), db: Session = Depends(get_db)):
    order = require_entity(db.get(Order, order_id), "订单不存在")
    order.payment_status = "confirmed"
    order.status = "payment_confirmed"
    order.payment_confirmed_by = current_admin["staff_user"].id
    order.payment_confirmed_at = utc_now()
    if payload and payload.remark:
        order.admin_note = payload.remark
    db.commit()
    db.refresh(order)
    return success_response(serialize_order_detail(db, order))


def serialize_order_detail(db: Session, order: Order, shallow: bool = False) -> dict:
    data = {
        "id": order.id,
        "order_no": order.order_no,
        "user_id": order.user_id,
        "order_type": order.order_type,
        "status": order.status,
        "total_amount": to_float(order.total_amount) or 0,
        "payment_status": order.payment_status,
        "user_coupon_id": order.user_coupon_id,
        "coupon_discount_amount": to_float(order.coupon_discount_amount) or 0,
        "customer_note": order.customer_note,
        "admin_note": order.admin_note,
        "items": [],
        "schedules": [],
        "print_tasks": [],
        "shipments": [],
        "created_at": order.created_at,
    }
    if shallow:
        return data
    items = db.scalars(select(OrderItem).where(OrderItem.order_id == order.id).order_by(OrderItem.id)).all()
    schedules = db.scalars(select(ProductionScheduleOrder).where(ProductionScheduleOrder.order_id == order.id).order_by(ProductionScheduleOrder.id)).all()
    print_tasks = db.scalars(select(PrintTask).where(PrintTask.order_id == order.id).order_by(PrintTask.id)).all()
    data["items"] = [
        {
            "id": item.id,
            "product_id": item.product_id,
            "sku_id": item.sku_id,
            "custom_request_id": item.custom_request_id,
            "item_name": item.item_name,
            "unit_price": to_float(item.unit_price) or 0,
            "quantity": item.quantity,
            "produced_quantity": item.produced_quantity,
            "inbounded_quantity": item.inbounded_quantity,
            "shipped_quantity": item.shipped_quantity,
            "subtotal": to_float(item.subtotal) or 0,
        }
        for item in items
    ]
    data["schedules"] = [{"id": item.id, "schedule_no": item.schedule_no, "status": item.status} for item in schedules]
    data["print_tasks"] = [{"id": item.id, "task_no": item.task_no, "status": item.status, "warehouse_status": item.warehouse_status} for item in print_tasks]
    data["shipments"] = [serialize_shipment(db, item) for item in db.scalars(select(Shipment).where(Shipment.order_id == order.id).order_by(Shipment.created_at.desc())).all()]
    return data


def serialize_shipment(db: Session, shipment: Shipment) -> dict[str, Any]:
    packages = db.scalars(select(ShipmentPackage).where(ShipmentPackage.shipment_id == shipment.id).order_by(ShipmentPackage.id)).all()
    return {
        "id": shipment.id,
        "shipment_no": shipment.shipment_no,
        "status": shipment.status,
        "packages": [
            {
                "id": package.id,
                "package_no": package.package_no,
                "carrier_code": package.carrier_code,
                "carrier_name": package.carrier_name,
                "tracking_no": package.tracking_no,
                "status": package.status,
            }
            for package in packages
        ],
    }
