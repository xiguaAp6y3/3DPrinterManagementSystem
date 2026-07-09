from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.security import require_app_user
from app.db.models.core import Order, OrderItem, PrintTask, Product, ProductSku, ProductionScheduleOrder, Shipment, ShipmentPackage
from app.db.session import get_db
from app.schemas.response import ApiResponse, PageResponse, paginated_response, success_response
from app.services import coupon_service
from app.services.db_helpers import next_no, paginate, require_entity, to_float

router = APIRouter()

OrderType = Literal["listed_product", "custom"]
OrderStatus = Literal["submitted", "reviewing", "quoted", "quote_confirmed", "payment_confirmed", "scheduled", "printing", "post_processing", "quality_check", "partially_completed", "completed", "partially_inbound", "in_warehouse", "ready_to_ship", "shipping", "partially_shipped", "shipped", "cancelled"]
PaymentStatus = Literal["unconfirmed", "confirmed", "cancelled"]


class ListedProductOrderItem(BaseModel):
    sku_id: int
    quantity: int = Field(gt=0)
    custom_note: str | None = None


class CreateListedProductOrderRequest(BaseModel):
    items: list[ListedProductOrderItem] = Field(min_length=1)
    customer_note: str | None = None
    coupon_id: int | None = Field(None, description="可选优惠券ID，下单时自动抵扣，实付最低0元")


class OrderSummary(BaseModel):
    id: int | None = None
    order_no: str
    order_type: OrderType | str
    status: OrderStatus | str
    total_amount: float = 0
    payment_status: PaymentStatus | str
    item_count: int = 0
    user_coupon_id: int | None = None
    coupon_discount_amount: float = 0
    created_at: datetime | None = None


class OrderDetail(OrderSummary):
    customer_note: str | None = None
    admin_note: str | None = None
    items: list[dict[str, Any]] = Field(default_factory=list)
    schedules: list[dict[str, Any]] = Field(default_factory=list)
    print_tasks: list[dict[str, Any]] = Field(default_factory=list)
    shipments: list[dict[str, Any]] = Field(default_factory=list)


@router.get("", response_model=ApiResponse[PageResponse[OrderSummary]])
def list_orders(page: int = 1, page_size: int = 20, order_type: OrderType | None = None, status: OrderStatus | None = None, payment_status: PaymentStatus | None = None, keyword: str | None = None, created_from: datetime | None = None, created_to: datetime | None = None, current_user: dict = Depends(require_app_user), db: Session = Depends(get_db)):
    stmt = select(Order).where(Order.user_id == current_user["user"].id).order_by(Order.created_at.desc())
    if order_type:
        stmt = stmt.where(Order.order_type == order_type)
    if status:
        stmt = stmt.where(Order.status == status)
    if payment_status:
        stmt = stmt.where(Order.payment_status == payment_status)
    if keyword:
        stmt = stmt.where(or_(Order.order_no.contains(keyword), Order.customer_note.contains(keyword)))
    if created_from:
        stmt = stmt.where(Order.created_at >= created_from)
    if created_to:
        stmt = stmt.where(Order.created_at <= created_to)
    items, page, page_size, total = paginate(db, stmt, page, page_size)
    return paginated_response([serialize_order_summary(db, item) for item in items], page, page_size, total)


@router.get("/{order_no}", response_model=ApiResponse[OrderDetail])
def get_order(order_no: str, current_user: dict = Depends(require_app_user), db: Session = Depends(get_db)):
    order = require_entity(db.scalar(select(Order).where(Order.order_no == order_no, Order.user_id == current_user["user"].id)), "订单不存在")
    return success_response(serialize_order_detail(db, order))


@router.get("/{order_no}/shipments", response_model=ApiResponse[list[dict[str, Any]]])
def get_order_shipments(order_no: str, current_user: dict = Depends(require_app_user), db: Session = Depends(get_db)):
    order = require_entity(db.scalar(select(Order).where(Order.order_no == order_no, Order.user_id == current_user["user"].id)), "订单不存在")
    shipments = db.scalars(select(Shipment).where(Shipment.order_id == order.id).order_by(Shipment.created_at.desc())).all()
    return success_response([serialize_shipment(db, item) for item in shipments])


@router.post("/listed-product", response_model=ApiResponse[OrderSummary])
def create_listed_product_order(payload: CreateListedProductOrderRequest, idempotency_key: str = Header(alias="Idempotency-Key"), current_user: dict = Depends(require_app_user), db: Session = Depends(get_db)):
    order = Order(
        order_no=next_no(db, "seq_order_no", "OD"),
        user_id=current_user["user"].id,
        order_type="listed_product",
        status="submitted",
        payment_status="unconfirmed",
        total_amount=0,
        customer_note=payload.customer_note,
    )
    db.add(order)
    db.flush()

    total_amount = 0.0
    for item in payload.items:
        sku = require_entity(db.get(ProductSku, item.sku_id), "商品 SKU 不存在")
        product = require_entity(db.get(Product, sku.product_id), "商品不存在")
        if product.is_deleted or product.sales_status != "on_sale" or sku.status != "active":
            require_entity(None, "商品不可下单")
        unit_price = to_float(sku.price) or 0
        subtotal = unit_price * item.quantity
        total_amount += subtotal
        db.add(
            OrderItem(
                order_id=order.id,
                product_id=product.id,
                sku_id=sku.id,
                item_name=product.name,
                unit_price=unit_price,
                quantity=item.quantity,
                subtotal=subtotal,
            )
        )

    order.total_amount = total_amount

    # 优惠券抵扣：校验+计算折扣+锁定券，实付最低 0 元
    if payload.coupon_id:
        result = coupon_service.validate_and_apply_coupon(
            db=db,
            coupon_id=payload.coupon_id,
            user_id=current_user["user"].id,
            order_total=total_amount,
            order_id=order.id,
        )
        order.user_coupon_id = payload.coupon_id
        order.coupon_discount_amount = result["discount_amount"]
        order.total_amount = result["final_amount"]

    db.commit()
    db.refresh(order)
    return success_response(serialize_order_summary(db, order))


def serialize_order_summary(db: Session, order: Order) -> dict:
    item_count = db.scalar(select(func.count()).select_from(OrderItem).where(OrderItem.order_id == order.id)) or 0
    return {
        "id": order.id,
        "order_no": order.order_no,
        "order_type": order.order_type,
        "status": order.status,
        "total_amount": to_float(order.total_amount) or 0,
        "payment_status": order.payment_status,
        "item_count": item_count,
        "user_coupon_id": order.user_coupon_id,
        "coupon_discount_amount": to_float(order.coupon_discount_amount) or 0,
        "created_at": order.created_at,
    }


def serialize_order_detail(db: Session, order: Order) -> dict:
    data = serialize_order_summary(db, order)
    items = db.scalars(select(OrderItem).where(OrderItem.order_id == order.id).order_by(OrderItem.id)).all()
    schedules = db.scalars(select(ProductionScheduleOrder).where(ProductionScheduleOrder.order_id == order.id).order_by(ProductionScheduleOrder.id)).all()
    print_tasks = db.scalars(select(PrintTask).where(PrintTask.order_id == order.id).order_by(PrintTask.id)).all()
    data.update(
        {
            "customer_note": order.customer_note,
            "admin_note": order.admin_note,
            "items": [
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
            ],
            "schedules": [{"id": item.id, "schedule_no": item.schedule_no, "status": item.status} for item in schedules],
            "print_tasks": [{"id": item.id, "task_no": item.task_no, "status": item.status, "warehouse_status": item.warehouse_status} for item in print_tasks],
            "shipments": [serialize_shipment(db, item) for item in db.scalars(select(Shipment).where(Shipment.order_id == order.id).order_by(Shipment.created_at.desc())).all()],
        }
    )
    return data


def serialize_shipment(db: Session, shipment: Shipment) -> dict[str, Any]:
    packages = db.scalars(select(ShipmentPackage).where(ShipmentPackage.shipment_id == shipment.id).order_by(ShipmentPackage.id)).all()
    return {
        "id": shipment.id,
        "shipment_no": shipment.shipment_no,
        "status": shipment.status,
        "receiver_name": shipment.receiver_name,
        "receiver_phone": shipment.receiver_phone,
        "receiver_address": shipment.receiver_address,
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
        "created_at": shipment.created_at,
    }
