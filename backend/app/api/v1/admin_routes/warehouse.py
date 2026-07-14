from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.security import require_admin
from app.core.time import utc8_now
from app.db.models.core import (
    OperationLog,
    Order,
    OrderItem,
    PrintTask,
    Product,
    ProductSku,
    Shipment,
    ShipmentItem,
    ShipmentPackage,
    Warehouse,
    WarehouseInboundRecord,
    WarehouseLocation,
    WarehouseOutboundItem,
    WarehouseOutboundRecord,
    WarehouseStockItem,
)
from app.db.session import get_db
from app.schemas.response import ApiResponse, PageResponse, paginated_response, success_response
from app.services.db_helpers import next_no, paginate, require_entity
from app.services.order_status import sync_order_shipping_status

router = APIRouter()


class WarehouseCreate(BaseModel):
    warehouse_code: str
    name: str
    status: str = "active"
    remark: str | None = None


class WarehouseUpdate(BaseModel):
    name: str | None = None
    status: str | None = None
    remark: str | None = None


class WarehouseLocationCreate(BaseModel):
    warehouse_id: int
    location_code: str
    name: str | None = None
    status: str = "active"
    remark: str | None = None


class WarehouseLocationUpdate(BaseModel):
    name: str | None = None
    status: str | None = None
    remark: str | None = None


class TransferTaskInboundRequest(BaseModel):
    warehouse_id: int
    location_id: int | None = None
    quantity: int = Field(default=1, gt=0)
    remark: str | None = None


class TransferOrderInboundItem(BaseModel):
    print_task_id: int
    quantity: int = Field(default=1, gt=0)


class TransferOrderInboundRequest(BaseModel):
    warehouse_id: int
    location_id: int | None = None
    items: list[TransferOrderInboundItem] = Field(min_length=1)
    remark: str | None = None


class ManualFinishedGoodsInboundRequest(BaseModel):
    warehouse_id: int
    location_id: int | None = None
    product_id: int
    sku_id: int
    quantity: int = Field(gt=0)
    remark: str | None = None


class ShipmentPackageCreate(BaseModel):
    carrier_code: str | None = None
    carrier_name: str | None = None
    tracking_no: str


class ShipmentCreate(BaseModel):
    receiver_name: str | None = None
    receiver_phone: str | None = None
    receiver_address: str | None = None
    packages: list[ShipmentPackageCreate] = Field(min_length=1)
    stock_item_ids: list[int] = Field(default_factory=list)
    auto_allocate_by_sku: bool = True
    remark: str | None = None


class ShipmentUpdate(BaseModel):
    receiver_name: str | None = None
    receiver_phone: str | None = None
    receiver_address: str | None = None
    remark: str | None = None


class BatchOutboundCreate(BaseModel):
    shipment_ids: list[int] = Field(min_length=1)
    remark: str | None = None


@router.get("/warehouses", response_model=ApiResponse[PageResponse[dict[str, Any]]])
def list_warehouses(page: int = 1, page_size: int = 20, keyword: str | None = None, status: str | None = None, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    stmt = select(Warehouse).order_by(Warehouse.id.desc())
    if keyword:
        stmt = stmt.where(or_(Warehouse.name.contains(keyword), Warehouse.warehouse_code.contains(keyword)))
    if status:
        stmt = stmt.where(Warehouse.status == status)
    items, page, page_size, total = paginate(db, stmt, page, page_size)
    return paginated_response([serialize_warehouse(item) for item in items], page, page_size, total)


@router.post("/warehouses", response_model=ApiResponse[dict[str, Any]])
def create_warehouse(payload: WarehouseCreate, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    if db.scalar(select(Warehouse).where(Warehouse.warehouse_code == payload.warehouse_code)):
        raise AppError("WAREHOUSE_CODE_EXISTS", "仓库编码已存在", 409)
    warehouse = Warehouse(**payload.model_dump())
    db.add(warehouse)
    db.commit()
    db.refresh(warehouse)
    return success_response(serialize_warehouse(warehouse))


@router.get("/warehouses/{warehouse_id}", response_model=ApiResponse[dict[str, Any]])
def get_warehouse(warehouse_id: int, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    return success_response(serialize_warehouse(require_entity(db.get(Warehouse, warehouse_id), "仓库不存在")))


@router.patch("/warehouses/{warehouse_id}", response_model=ApiResponse[dict[str, Any]])
def update_warehouse(warehouse_id: int, payload: WarehouseUpdate, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    warehouse = require_entity(db.get(Warehouse, warehouse_id), "仓库不存在")
    for key, value in payload.model_dump(exclude_none=True).items():
        setattr(warehouse, key, value)
    db.commit()
    db.refresh(warehouse)
    return success_response(serialize_warehouse(warehouse))


@router.get("/warehouse-locations", response_model=ApiResponse[PageResponse[dict[str, Any]]])
def list_locations(page: int = 1, page_size: int = 20, warehouse_id: int | None = None, status: str | None = None, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    stmt = select(WarehouseLocation).order_by(WarehouseLocation.id.desc())
    if warehouse_id is not None:
        stmt = stmt.where(WarehouseLocation.warehouse_id == warehouse_id)
    if status:
        stmt = stmt.where(WarehouseLocation.status == status)
    items, page, page_size, total = paginate(db, stmt, page, page_size)
    return paginated_response([serialize_location(item) for item in items], page, page_size, total)


@router.post("/warehouse-locations", response_model=ApiResponse[dict[str, Any]])
def create_location(payload: WarehouseLocationCreate, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    require_entity(db.get(Warehouse, payload.warehouse_id), "仓库不存在")
    if db.scalar(select(WarehouseLocation).where(WarehouseLocation.warehouse_id == payload.warehouse_id, WarehouseLocation.location_code == payload.location_code)):
        raise AppError("WAREHOUSE_LOCATION_EXISTS", "库位编码已存在", 409)
    location = WarehouseLocation(**payload.model_dump())
    db.add(location)
    db.commit()
    db.refresh(location)
    return success_response(serialize_location(location))


@router.patch("/warehouse-locations/{location_id}", response_model=ApiResponse[dict[str, Any]])
def update_location(location_id: int, payload: WarehouseLocationUpdate, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    location = require_entity(db.get(WarehouseLocation, location_id), "库位不存在")
    for key, value in payload.model_dump(exclude_none=True).items():
        setattr(location, key, value)
    db.commit()
    db.refresh(location)
    return success_response(serialize_location(location))


@router.post("/print-tasks/{task_id}/transfer-to-warehouse", response_model=ApiResponse[dict[str, Any]])
def transfer_task_to_warehouse(task_id: int, payload: TransferTaskInboundRequest, idempotency_key: str = Header(alias="Idempotency-Key"), current_admin: dict = Depends(require_admin), db: Session = Depends(get_db)):
    task = require_entity(db.get(PrintTask, task_id), "打印任务不存在")
    record = inbound_print_task(db, task, payload.warehouse_id, payload.location_id, payload.quantity, payload.remark, current_admin["staff_user"].id)
    db.commit()
    return success_response(serialize_inbound(record))


@router.post("/orders/{order_id}/transfer-to-warehouse", response_model=ApiResponse[list[dict[str, Any]]])
def transfer_order_to_warehouse(order_id: int, payload: TransferOrderInboundRequest, idempotency_key: str = Header(alias="Idempotency-Key"), current_admin: dict = Depends(require_admin), db: Session = Depends(get_db)):
    require_entity(db.get(Order, order_id), "订单不存在")
    records = []
    for item in payload.items:
        task = require_entity(db.get(PrintTask, item.print_task_id), "打印任务不存在")
        if task.order_id != order_id:
            raise AppError("ORDER_TASK_MISMATCH", "打印任务不属于该订单", 409)
        records.append(inbound_print_task(db, task, payload.warehouse_id, payload.location_id, item.quantity, payload.remark, current_admin["staff_user"].id))
    db.commit()
    return success_response([serialize_inbound(item) for item in records])


@router.post("/warehouse/manual-inbounds", response_model=ApiResponse[dict[str, Any]])
def manual_finished_goods_inbound(payload: ManualFinishedGoodsInboundRequest, idempotency_key: str = Header(alias="Idempotency-Key"), current_admin: dict = Depends(require_admin), db: Session = Depends(get_db)):
    warehouse = require_entity(db.get(Warehouse, payload.warehouse_id), "仓库不存在")
    if warehouse.status != "active":
        raise AppError("WAREHOUSE_DISABLED", "仓库不可用", 409)
    if payload.location_id is not None:
        location = require_entity(db.get(WarehouseLocation, payload.location_id), "库位不存在")
        if location.warehouse_id != warehouse.id:
            raise AppError("LOCATION_WAREHOUSE_MISMATCH", "库位不属于该仓库", 409)
    require_entity(db.get(Product, payload.product_id), "商品不存在")
    sku = require_entity(db.get(ProductSku, payload.sku_id), "商品 SKU 不存在")
    if sku.product_id != payload.product_id:
        raise AppError("SKU_PRODUCT_MISMATCH", "SKU 不属于该商品", 409)

    stock_item = WarehouseStockItem(
        stock_item_no=next_no(db, "seq_stock_item_no", "ST"),
        warehouse_id=warehouse.id,
        location_id=payload.location_id,
        product_id=payload.product_id,
        sku_id=sku.id,
        quantity=payload.quantity,
        status="available",
        inbounded_at=utc8_now(),
        created_by=current_admin["staff_user"].id,
    )
    db.add(stock_item)
    db.flush()
    record = WarehouseInboundRecord(
        inbound_no=next_no(db, "seq_inbound_no", "IN"),
        inbound_type="manual_adjustment",
        warehouse_id=warehouse.id,
        location_id=payload.location_id,
        stock_item_id=stock_item.id,
        quantity=payload.quantity,
        operator_id=current_admin["staff_user"].id,
        remark=payload.remark,
    )
    db.add(record)
    db.add(OperationLog(operator_id=current_admin["staff_user"].id, operation_type="manual_finished_goods_inbound", target_table="warehouse_stock_items", target_id=stock_item.id, remark=payload.remark))
    db.commit()
    return success_response(serialize_inbound(record))


@router.get("/warehouse/stock-items", response_model=ApiResponse[PageResponse[dict[str, Any]]])
def list_stock_items(page: int = 1, page_size: int = 20, order_id: int | None = None, status: str | None = None, warehouse_id: int | None = None, location_id: int | None = None, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    stmt = select(WarehouseStockItem).order_by(WarehouseStockItem.created_at.desc())
    if order_id is not None:
        stmt = stmt.where(WarehouseStockItem.order_id == order_id)
    if status:
        stmt = stmt.where(WarehouseStockItem.status == status)
    if warehouse_id is not None:
        stmt = stmt.where(WarehouseStockItem.warehouse_id == warehouse_id)
    if location_id is not None:
        stmt = stmt.where(WarehouseStockItem.location_id == location_id)
    items, page, page_size, total = paginate(db, stmt, page, page_size)
    return paginated_response([serialize_stock_item(item) for item in items], page, page_size, total)


@router.get("/warehouse/inbounds", response_model=ApiResponse[PageResponse[dict[str, Any]]])
def list_inbounds(page: int = 1, page_size: int = 20, order_id: int | None = None, print_task_id: int | None = None, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    stmt = select(WarehouseInboundRecord).order_by(WarehouseInboundRecord.created_at.desc())
    if order_id is not None:
        stmt = stmt.where(WarehouseInboundRecord.order_id == order_id)
    if print_task_id is not None:
        stmt = stmt.where(WarehouseInboundRecord.print_task_id == print_task_id)
    items, page, page_size, total = paginate(db, stmt, page, page_size)
    return paginated_response([serialize_inbound(item) for item in items], page, page_size, total)


@router.post("/orders/{order_id}/shipments", response_model=ApiResponse[dict[str, Any]])
def create_order_shipment(order_id: int, payload: ShipmentCreate, idempotency_key: str = Header(alias="Idempotency-Key"), current_admin: dict = Depends(require_admin), db: Session = Depends(get_db)):
    order = require_entity(db.get(Order, order_id), "订单不存在")
    if order.status not in {"payment_confirmed", "scheduled", "ready_to_ship", "in_warehouse", "partially_shipped", "shipping"}:
        raise AppError("ORDER_NOT_READY_TO_SHIP", "订单当前状态不允许创建发货单", 409)
    shipment = Shipment(
        shipment_no=next_no(db, "seq_shipment_no", "SP"),
        order_id=order_id,
        status="ready",
        receiver_name=payload.receiver_name or order.receiver_name,
        receiver_phone=payload.receiver_phone or order.receiver_phone,
        receiver_address=payload.receiver_address or order.receiver_address,
        remark=payload.remark,
        created_by=current_admin["staff_user"].id,
    )
    db.add(shipment)
    db.flush()

    packages = []
    for idx, package_payload in enumerate(payload.packages, start=1):
        package = ShipmentPackage(
            shipment_id=shipment.id,
            package_no=f"{shipment.shipment_no}-{idx:02d}",
            carrier_code=package_payload.carrier_code,
            carrier_name=package_payload.carrier_name,
            tracking_no=package_payload.tracking_no,
            status="ready",
        )
        db.add(package)
        packages.append(package)
    db.flush()

    if payload.auto_allocate_by_sku or not payload.stock_item_ids:
        allocations = allocate_order_stock_by_sku(db, order)
    else:
        allocations = allocate_selected_order_stock(db, order, payload.stock_item_ids)

    first_package_id = packages[0].id
    for stock_item, order_item, quantity in allocations:
        db.add(ShipmentItem(shipment_id=shipment.id, package_id=first_package_id, stock_item_id=stock_item.id, order_item_id=order_item.id, quantity=quantity))
    order.status = "shipping"
    db.commit()
    db.refresh(shipment)
    return success_response(serialize_shipment(db, shipment))


def allocate_order_stock_by_sku(db: Session, order: Order) -> list[tuple[WarehouseStockItem, OrderItem, int]]:
    allocations: list[tuple[WarehouseStockItem, OrderItem, int]] = []
    order_items = db.scalars(select(OrderItem).where(OrderItem.order_id == order.id).order_by(OrderItem.id)).all()
    for order_item in order_items:
        if order_item.sku_id is None or order_item.product_id is None:
            raise AppError("ORDER_ITEM_SKU_REQUIRED", "定制商品没有可匹配的 SKU 库存，不能自动发货", 409, details={"order_item_id": order_item.id})
        reserved_quantity = db.scalar(
            select(func.coalesce(func.sum(ShipmentItem.quantity), 0))
            .join(Shipment, Shipment.id == ShipmentItem.shipment_id)
            .where(
                Shipment.order_id == order.id,
                ShipmentItem.order_item_id == order_item.id,
                Shipment.status == "ready",
            )
        ) or 0
        required_quantity = order_item.quantity - order_item.shipped_quantity - int(reserved_quantity)
        if required_quantity <= 0:
            continue
        stock_items = db.scalars(
            select(WarehouseStockItem)
            .where(
                WarehouseStockItem.status == "available",
                WarehouseStockItem.product_id == order_item.product_id,
                WarehouseStockItem.sku_id == order_item.sku_id,
            )
            .order_by(WarehouseStockItem.inbounded_at, WarehouseStockItem.id)
        ).all()
        available_quantity = sum(stock_item.quantity for stock_item in stock_items)
        if available_quantity < required_quantity:
            raise AppError(
                "INSUFFICIENT_SKU_STOCK",
                "仓库中可用 SKU 成品不足，无法发货",
                409,
                details={"order_item_id": order_item.id, "sku_id": order_item.sku_id, "required": required_quantity, "available": available_quantity},
            )
        remaining_quantity = required_quantity
        for stock_item in stock_items:
            if remaining_quantity == 0:
                break
            allocation_quantity = min(stock_item.quantity, remaining_quantity)
            allocated_stock_item = reserve_stock_item(db, stock_item, order, order_item, allocation_quantity)
            allocations.append((allocated_stock_item, order_item, allocation_quantity))
            remaining_quantity -= allocation_quantity
    if not allocations:
        raise AppError("ORDER_ALREADY_ALLOCATED", "订单没有待发货商品", 409)
    return allocations


def reserve_stock_item(db: Session, stock_item: WarehouseStockItem, order: Order, order_item: OrderItem, quantity: int) -> WarehouseStockItem:
    if quantity == stock_item.quantity:
        stock_item.status = "reserved"
        return stock_item

    stock_item.quantity -= quantity
    reserved_stock_item = WarehouseStockItem(
        stock_item_no=next_no(db, "seq_stock_item_no", "ST"),
        warehouse_id=stock_item.warehouse_id,
        location_id=stock_item.location_id,
        order_id=order.id,
        order_item_id=order_item.id,
        print_task_id=stock_item.print_task_id,
        product_id=stock_item.product_id,
        sku_id=stock_item.sku_id,
        custom_request_id=stock_item.custom_request_id,
        quantity=quantity,
        status="reserved",
        inbounded_at=stock_item.inbounded_at,
        created_by=stock_item.created_by,
    )
    db.add(reserved_stock_item)
    db.flush()
    return reserved_stock_item


def allocate_selected_order_stock(db: Session, order: Order, stock_item_ids: list[int]) -> list[tuple[WarehouseStockItem, OrderItem, int]]:
    stock_items = db.scalars(select(WarehouseStockItem).where(WarehouseStockItem.id.in_(stock_item_ids))).all()
    if len(stock_items) != len(set(stock_item_ids)):
        raise AppError("STOCK_ITEM_NOT_FOUND", "部分库存件不存在", 404)
    allocations = []
    for stock_item in stock_items:
        if stock_item.order_id != order.id:
            raise AppError("STOCK_ITEM_ORDER_MISMATCH", "库存件不属于该订单", 409)
        if stock_item.status != "available":
            raise AppError("STOCK_ITEM_NOT_AVAILABLE", "库存件不可发货", 409)
        order_item = require_entity(db.get(OrderItem, stock_item.order_item_id), "库存件未关联订单明细")
        stock_item.status = "reserved"
        allocations.append((stock_item, order_item, stock_item.quantity))
    return allocations


@router.get("/orders/{order_id}/shipments", response_model=ApiResponse[list[dict[str, Any]]])
def list_order_shipments(order_id: int, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    require_entity(db.get(Order, order_id), "订单不存在")
    shipments = db.scalars(select(Shipment).where(Shipment.order_id == order_id).order_by(Shipment.created_at.desc())).all()
    return success_response([serialize_shipment(db, item) for item in shipments])


@router.patch("/shipments/{shipment_id}", response_model=ApiResponse[dict[str, Any]])
def update_shipment(shipment_id: int, payload: ShipmentUpdate, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    shipment = require_entity(db.get(Shipment, shipment_id), "发货单不存在")
    if shipment.status == "outbounded":
        raise AppError("SHIPMENT_ALREADY_OUTBOUNDED", "已出库发货单不能修改", 409)
    for key, value in payload.model_dump(exclude_none=True).items():
        setattr(shipment, key, value)
    db.commit()
    db.refresh(shipment)
    return success_response(serialize_shipment(db, shipment))


@router.delete("/shipments/{shipment_id}", response_model=ApiResponse[dict[str, Any]])
def delete_shipment(shipment_id: int, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    shipment = require_entity(db.get(Shipment, shipment_id), "发货单不存在")
    if shipment.status not in {"draft", "ready"}:
        raise AppError("SHIPMENT_DELETE_FORBIDDEN", "当前发货单状态不允许删除", 409)
    linked_outbound = db.scalar(
        select(WarehouseOutboundRecord)
        .join(WarehouseOutboundItem, WarehouseOutboundItem.outbound_id == WarehouseOutboundRecord.id)
        .where(
            WarehouseOutboundItem.shipment_id == shipment.id,
            WarehouseOutboundRecord.status != "cancelled",
        )
    )
    if linked_outbound is not None:
        raise AppError("SHIPMENT_HAS_OUTBOUND", "发货单已关联出库单，不能撤销", 409)
    for item in db.scalars(select(ShipmentItem).where(ShipmentItem.shipment_id == shipment.id)).all():
        stock_item = db.get(WarehouseStockItem, item.stock_item_id)
        if stock_item and stock_item.status == "reserved":
            stock_item.status = "available"
        db.delete(item)
    for package in db.scalars(select(ShipmentPackage).where(ShipmentPackage.shipment_id == shipment.id)).all():
        db.delete(package)
    shipment.status = "cancelled"
    db.commit()
    return success_response({"shipment_id": shipment_id, "status": "cancelled"})


@router.post("/warehouse/outbounds/batch", response_model=ApiResponse[dict[str, Any]])
def create_batch_outbound(payload: BatchOutboundCreate, idempotency_key: str = Header(alias="Idempotency-Key"), current_admin: dict = Depends(require_admin), db: Session = Depends(get_db)):
    shipments = db.scalars(select(Shipment).where(Shipment.id.in_(payload.shipment_ids))).all()
    if len(shipments) != len(set(payload.shipment_ids)):
        raise AppError("SHIPMENT_NOT_FOUND", "部分发货单不存在", 404)
    existing_shipment_id = db.scalar(
        select(WarehouseOutboundItem.shipment_id)
        .join(WarehouseOutboundRecord, WarehouseOutboundRecord.id == WarehouseOutboundItem.outbound_id)
        .where(
            WarehouseOutboundItem.shipment_id.in_(payload.shipment_ids),
            WarehouseOutboundRecord.status != "cancelled",
        )
    )
    if existing_shipment_id is not None:
        raise AppError(
            "SHIPMENT_OUTBOUND_EXISTS",
            "部分发货单已关联有效出库单",
            409,
            details={"shipment_id": existing_shipment_id},
        )
    outbound = WarehouseOutboundRecord(outbound_no=next_no(db, "seq_outbound_no", "OB"), status="draft", outbound_type="shipment", operator_id=current_admin["staff_user"].id, remark=payload.remark)
    db.add(outbound)
    db.flush()
    for shipment in shipments:
        if shipment.status != "ready":
            raise AppError("SHIPMENT_NOT_READY", "只有 ready 状态发货单可以批量出库", 409)
        package = db.scalar(select(ShipmentPackage).where(ShipmentPackage.shipment_id == shipment.id).order_by(ShipmentPackage.id))
        if package is None or not package.tracking_no:
            raise AppError("SHIPMENT_TRACKING_REQUIRED", "发货单必须填写快递单号", 409)
        items = db.scalars(select(ShipmentItem).where(ShipmentItem.shipment_id == shipment.id)).all()
        for item in items:
            stock_item = require_entity(db.get(WarehouseStockItem, item.stock_item_id), "库存件不存在")
            if stock_item.status != "reserved":
                raise AppError("STOCK_ITEM_NOT_RESERVED", "库存件不是已预留状态", 409)
            db.add(WarehouseOutboundItem(outbound_id=outbound.id, shipment_id=shipment.id, package_id=item.package_id, stock_item_id=stock_item.id, quantity=item.quantity))
    db.commit()
    db.refresh(outbound)
    return success_response(serialize_outbound(db, outbound))


@router.post("/warehouse/outbounds/{outbound_id}/confirm", response_model=ApiResponse[dict[str, Any]])
def confirm_outbound(outbound_id: int, idempotency_key: str = Header(alias="Idempotency-Key"), current_admin: dict = Depends(require_admin), db: Session = Depends(get_db)):
    outbound = require_entity(db.get(WarehouseOutboundRecord, outbound_id), "出库单不存在")
    if outbound.status != "draft":
        raise AppError("OUTBOUND_ALREADY_CONFIRMED", "出库单不是草稿状态", 409)
    items = db.scalars(select(WarehouseOutboundItem).where(WarehouseOutboundItem.outbound_id == outbound.id)).all()
    affected_order_ids = set()
    affected_shipment_ids = set()
    now = utc8_now()
    for item in items:
        stock_item = require_entity(db.get(WarehouseStockItem, item.stock_item_id), "库存件不存在")
        stock_item.status = "shipped"
        stock_item.outbounded_at = now
        shipment = require_entity(db.get(Shipment, item.shipment_id), "发货单不存在")
        affected_order_ids.add(shipment.order_id)
        affected_shipment_ids.add(item.shipment_id)
        shipment_item = db.scalar(
            select(ShipmentItem).where(
                ShipmentItem.shipment_id == shipment.id,
                ShipmentItem.stock_item_id == stock_item.id,
            )
        )
        if shipment_item and shipment_item.order_item_id:
            order_item = db.get(OrderItem, shipment_item.order_item_id)
            if order_item:
                order_item.shipped_quantity += item.quantity
    for shipment_id in affected_shipment_ids:
        shipment = db.get(Shipment, shipment_id)
        if shipment:
            shipment.status = "outbounded"
            for package in db.scalars(select(ShipmentPackage).where(ShipmentPackage.shipment_id == shipment.id)).all():
                package.status = "outbounded"
    outbound.status = "confirmed"
    outbound.operator_id = current_admin["staff_user"].id
    outbound.confirmed_at = now
    db.flush()
    for order_id in affected_order_ids:
        sync_order_shipping_status(db, order_id)
    db.commit()
    db.refresh(outbound)
    return success_response(serialize_outbound(db, outbound))


@router.get("/warehouse/outbounds", response_model=ApiResponse[PageResponse[dict[str, Any]]])
def list_outbounds(page: int = 1, page_size: int = 20, status: str | None = None, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    stmt = select(WarehouseOutboundRecord).order_by(WarehouseOutboundRecord.created_at.desc())
    if status:
        stmt = stmt.where(WarehouseOutboundRecord.status == status)
    items, page, page_size, total = paginate(db, stmt, page, page_size)
    return paginated_response([serialize_outbound(db, item) for item in items], page, page_size, total)


@router.get("/warehouse/outbounds/{outbound_id}", response_model=ApiResponse[dict[str, Any]])
def get_outbound(outbound_id: int, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    return success_response(serialize_outbound(db, require_entity(db.get(WarehouseOutboundRecord, outbound_id), "出库单不存在")))


def inbound_print_task(db: Session, task: PrintTask, warehouse_id: int, location_id: int | None, quantity: int, remark: str | None, staff_user_id: int) -> WarehouseInboundRecord:
    warehouse = require_entity(db.get(Warehouse, warehouse_id), "仓库不存在")
    if warehouse.status != "active":
        raise AppError("WAREHOUSE_DISABLED", "仓库不可用", 409)
    if location_id is not None:
        location = require_entity(db.get(WarehouseLocation, location_id), "库位不存在")
        if location.warehouse_id != warehouse_id:
            raise AppError("LOCATION_WAREHOUSE_MISMATCH", "库位不属于该仓库", 409)
    if task.status != "completed":
        raise AppError("PRINT_TASK_NOT_COMPLETED", "只有已完成打印任务可以入库", 409)
    if task.warehouse_status == "inbounded":
        raise AppError("PRINT_TASK_ALREADY_INBOUNDED", "打印任务已入库", 409)
    order = require_entity(db.get(Order, task.order_id), "订单不存在")
    order_item = resolve_task_order_item(db, task)

    stock_item = WarehouseStockItem(
        stock_item_no=next_no(db, "seq_stock_item_no", "ST"),
        warehouse_id=warehouse_id,
        location_id=location_id,
        order_id=task.order_id,
        order_item_id=order_item.id,
        print_task_id=task.id,
        product_id=order_item.product_id,
        sku_id=order_item.sku_id,
        custom_request_id=order_item.custom_request_id,
        quantity=quantity,
        status="available",
        inbounded_at=utc8_now(),
        created_by=staff_user_id,
    )
    db.add(stock_item)
    db.flush()
    record = WarehouseInboundRecord(
        inbound_no=next_no(db, "seq_inbound_no", "IN"),
        inbound_type="production_completed",
        warehouse_id=warehouse_id,
        location_id=location_id,
        order_id=task.order_id,
        order_item_id=order_item.id,
        print_task_id=task.id,
        stock_item_id=stock_item.id,
        quantity=quantity,
        operator_id=staff_user_id,
        remark=remark,
    )
    db.add(record)
    task.warehouse_status = "inbounded"
    order_item.inbounded_quantity += quantity
    order_item.produced_quantity = max(order_item.produced_quantity, order_item.inbounded_quantity)
    sync_order_inbound_status(db, order)
    db.add(OperationLog(operator_id=staff_user_id, operation_type="transfer_to_warehouse", target_table="print_tasks", target_id=task.id, remark=remark))
    return record


def resolve_task_order_item(db: Session, task: PrintTask) -> OrderItem:
    if task.order_item_id is not None:
        order_item = require_entity(db.get(OrderItem, task.order_item_id), "订单明细不存在")
        if order_item.order_id != task.order_id:
            raise AppError("PRINT_TASK_ORDER_ITEM_MISMATCH", "打印任务关联的订单明细不属于该订单", 409)
        return order_item

    order_items = db.scalars(select(OrderItem).where(OrderItem.order_id == task.order_id)).all()
    if len(order_items) != 1:
        raise AppError("PRINT_TASK_ORDER_ITEM_REQUIRED", "打印任务未关联订单明细，无法确定商品和 SKU", 409)

    task.order_item_id = order_items[0].id
    return order_items[0]


def sync_order_inbound_status(db: Session, order: Order) -> None:
    tasks = db.scalars(select(PrintTask).where(PrintTask.order_id == order.id, PrintTask.status != "cancelled")).all()
    if not tasks:
        return
    completed_count = sum(1 for task in tasks if task.status == "completed")
    inbounded_count = sum(1 for task in tasks if task.warehouse_status == "inbounded")
    if inbounded_count == len(tasks):
        order.status = "ready_to_ship"
    elif inbounded_count > 0:
        order.status = "partially_inbound"
    elif completed_count == len(tasks):
        order.status = "completed"
    elif completed_count > 0:
        order.status = "partially_completed"


def serialize_warehouse(item: Warehouse) -> dict[str, Any]:
    return {"id": item.id, "warehouse_code": item.warehouse_code, "name": item.name, "status": item.status, "remark": item.remark, "created_at": item.created_at}


def serialize_location(item: WarehouseLocation) -> dict[str, Any]:
    return {"id": item.id, "warehouse_id": item.warehouse_id, "location_code": item.location_code, "name": item.name, "status": item.status, "remark": item.remark}


def serialize_stock_item(item: WarehouseStockItem) -> dict[str, Any]:
    return {
        "id": item.id,
        "stock_item_no": item.stock_item_no,
        "warehouse_id": item.warehouse_id,
        "location_id": item.location_id,
        "order_id": item.order_id,
        "order_item_id": item.order_item_id,
        "print_task_id": item.print_task_id,
        "product_id": item.product_id,
        "sku_id": item.sku_id,
        "quantity": item.quantity,
        "status": item.status,
        "inbounded_at": item.inbounded_at,
        "outbounded_at": item.outbounded_at,
    }


def serialize_inbound(item: WarehouseInboundRecord) -> dict[str, Any]:
    return {
        "id": item.id,
        "inbound_no": item.inbound_no,
        "inbound_type": item.inbound_type,
        "warehouse_id": item.warehouse_id,
        "location_id": item.location_id,
        "order_id": item.order_id,
        "order_item_id": item.order_item_id,
        "print_task_id": item.print_task_id,
        "stock_item_id": item.stock_item_id,
        "quantity": item.quantity,
        "remark": item.remark,
        "created_at": item.created_at,
    }


def serialize_shipment(db: Session, item: Shipment) -> dict[str, Any]:
    packages = db.scalars(select(ShipmentPackage).where(ShipmentPackage.shipment_id == item.id).order_by(ShipmentPackage.id)).all()
    shipment_items = db.scalars(select(ShipmentItem).where(ShipmentItem.shipment_id == item.id).order_by(ShipmentItem.id)).all()
    outbound_item = db.scalar(
        select(WarehouseOutboundItem)
        .join(WarehouseOutboundRecord, WarehouseOutboundRecord.id == WarehouseOutboundItem.outbound_id)
        .where(
            WarehouseOutboundItem.shipment_id == item.id,
            WarehouseOutboundRecord.status != "cancelled",
        )
        .order_by(WarehouseOutboundItem.id.desc())
    )
    outbound = db.get(WarehouseOutboundRecord, outbound_item.outbound_id) if outbound_item else None
    return {
        "id": item.id,
        "shipment_no": item.shipment_no,
        "order_id": item.order_id,
        "status": item.status,
        "receiver_name": item.receiver_name,
        "receiver_phone": item.receiver_phone,
        "receiver_address": item.receiver_address,
        "remark": item.remark,
        "outbound_id": outbound.id if outbound else None,
        "outbound_status": outbound.status if outbound else None,
        "packages": [
            {"id": package.id, "package_no": package.package_no, "carrier_code": package.carrier_code, "carrier_name": package.carrier_name, "tracking_no": package.tracking_no, "status": package.status}
            for package in packages
        ],
        "items": [{"id": si.id, "stock_item_id": si.stock_item_id, "quantity": si.quantity, "package_id": si.package_id} for si in shipment_items],
        "created_at": item.created_at,
    }


def serialize_outbound(db: Session, item: WarehouseOutboundRecord) -> dict[str, Any]:
    items = db.scalars(select(WarehouseOutboundItem).where(WarehouseOutboundItem.outbound_id == item.id).order_by(WarehouseOutboundItem.id)).all()
    return {
        "id": item.id,
        "outbound_no": item.outbound_no,
        "status": item.status,
        "outbound_type": item.outbound_type,
        "operator_id": item.operator_id,
        "confirmed_at": item.confirmed_at,
        "remark": item.remark,
        "items": [{"id": row.id, "shipment_id": row.shipment_id, "package_id": row.package_id, "stock_item_id": row.stock_item_id, "quantity": row.quantity} for row in items],
        "created_at": item.created_at,
    }
