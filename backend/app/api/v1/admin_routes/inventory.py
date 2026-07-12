from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.security import require_admin
from app.core.time import utc8_now
from app.db.models.core import FinishedGoodsInventory, InventoryLock, Material, MaterialStockLog
from app.db.session import get_db
from app.schemas.response import ApiResponse, PageResponse, paginated_response, success_response
from app.services.db_helpers import paginate, require_entity, to_float

router = APIRouter()

MaterialChangeType = Literal["inbound", "adjustment", "consume", "release", "loss"]
LockStatus = Literal["locked", "released", "consumed", "expired"]


class MaterialCreate(BaseModel):
    name: str
    material_type: str
    brand: str | None = None
    color: str | None = None
    diameter: float | None = None
    stock_weight: float = Field(default=0, ge=0)
    safe_stock_weight: float = Field(default=0, ge=0)
    unit_cost: float | None = None


class MaterialUpdate(BaseModel):
    name: str | None = None
    material_type: str | None = None
    brand: str | None = None
    color: str | None = None
    diameter: float | None = None
    safe_stock_weight: float | None = Field(default=None, ge=0)
    unit_cost: float | None = None
    status: str | None = None


class MaterialStockLogCreate(BaseModel):
    change_type: MaterialChangeType
    change_weight: float
    remark: str | None = None


class MaterialLossCreate(BaseModel):
    weight: float = Field(gt=0)
    related_order_id: int | None = None
    related_task_id: int | None = None
    remark: str | None = None


class MaterialInfo(BaseModel):
    id: int | None = None
    name: str | None = None
    material_type: str | None = None
    brand: str | None = None
    color: str | None = None
    diameter: float | None = None
    stock_weight: float = 0
    reserved_weight: float = 0
    safe_stock_weight: float = 0
    unit_cost: float | None = None
    status: str = "active"


class InventoryOverview(BaseModel):
    low_stock_materials: int = 0
    locked_materials: int = 0
    material_sku_count: int = 0
    finished_goods_sku_count: int = 0
    in_progress_quantity: int = 0


class InventoryLockInfo(BaseModel):
    id: int | None = None
    lock_type: str | None = None
    order_id: int | None = None
    print_task_id: int | None = None
    material_id: int | None = None
    quantity: int | None = None
    weight: float | None = None
    status: LockStatus | str = "locked"


class MaterialStockLogItem(BaseModel):
    id: int | None = None
    material_id: int
    change_type: MaterialChangeType | str
    change_weight: float
    before_weight: float | None = None
    after_weight: float | None = None
    related_order_id: int | None = None
    related_task_id: int | None = None
    remark: str | None = None
    created_by: int | None = None
    created_at: datetime | None = None


class FinishedGoodsInventoryItem(BaseModel):
    id: int | None = None
    product_id: int | None = None
    sku_id: int | None = None
    order_id: int | None = None
    available_quantity: int = 0
    reserved_quantity: int = 0
    in_progress_quantity: int = 0
    warehouse_location: str | None = None
    updated_at: datetime | None = None


@router.get("/overview", response_model=ApiResponse[InventoryOverview])
def overview(_: dict = Depends(require_admin), db: Session = Depends(get_db)):
    return success_response(
        {
            "low_stock_materials": db.scalar(select(func.count()).select_from(Material).where(Material.stock_weight <= Material.safe_stock_weight, Material.status == "active")) or 0,
            "locked_materials": db.scalar(select(func.count()).select_from(InventoryLock).where(InventoryLock.status == "locked", InventoryLock.lock_type == "material")) or 0,
            "material_sku_count": db.scalar(select(func.count()).select_from(Material).where(Material.status == "active")) or 0,
            "finished_goods_sku_count": db.scalar(select(func.count()).select_from(FinishedGoodsInventory)) or 0,
            "in_progress_quantity": db.scalar(select(func.coalesce(func.sum(FinishedGoodsInventory.in_progress_quantity), 0))) or 0,
        }
    )


@router.get("/materials", response_model=ApiResponse[PageResponse[MaterialInfo]])
def list_materials(page: int = 1, page_size: int = 20, keyword: str | None = None, material_type: str | None = None, color: str | None = None, status: str | None = None, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    stmt = select(Material).order_by(Material.id.desc())
    if keyword:
        stmt = stmt.where(or_(Material.name.contains(keyword), Material.brand.contains(keyword)))
    if material_type:
        stmt = stmt.where(Material.material_type == material_type)
    if color:
        stmt = stmt.where(Material.color == color)
    if status:
        stmt = stmt.where(Material.status == status)
    items, page, page_size, total = paginate(db, stmt, page, page_size)
    return paginated_response([serialize_material(item) for item in items], page, page_size, total)


@router.post("/materials", response_model=ApiResponse[MaterialInfo])
def create_material(payload: MaterialCreate, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    material = Material(**payload.model_dump(), reserved_weight=0, status="active")
    db.add(material)
    db.commit()
    db.refresh(material)
    return success_response(serialize_material(material))


@router.get("/materials/{material_id}", response_model=ApiResponse[MaterialInfo])
def get_material(material_id: int, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    material = require_entity(db.get(Material, material_id), "材料不存在")
    return success_response(serialize_material(material))


@router.patch("/materials/{material_id}", response_model=ApiResponse[MaterialInfo])
def update_material(material_id: int, payload: MaterialUpdate, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    material = require_entity(db.get(Material, material_id), "材料不存在")
    for key, value in payload.model_dump(exclude_none=True).items():
        setattr(material, key, value)
    db.commit()
    db.refresh(material)
    return success_response(serialize_material(material))


@router.get("/materials/{material_id}/stock-logs", response_model=ApiResponse[PageResponse[MaterialStockLogItem]])
def list_material_stock_logs(material_id: int, page: int = 1, page_size: int = 20, change_type: MaterialChangeType | None = None, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    require_entity(db.get(Material, material_id), "材料不存在")
    stmt = select(MaterialStockLog).where(MaterialStockLog.material_id == material_id).order_by(MaterialStockLog.created_at.desc())
    if change_type:
        stmt = stmt.where(MaterialStockLog.change_type == normalize_change_type(change_type))
    items, page, page_size, total = paginate(db, stmt, page, page_size)
    return paginated_response([serialize_stock_log(item) for item in items], page, page_size, total)


@router.post("/materials/{material_id}/stock-logs", response_model=ApiResponse[MaterialStockLogItem])
def create_stock_log(material_id: int, payload: MaterialStockLogCreate, idempotency_key: str = Header(alias="Idempotency-Key"), current_admin: dict = Depends(require_admin), db: Session = Depends(get_db)):
    material = require_entity(db.get(Material, material_id), "材料不存在")
    log = apply_material_change(db, material, normalize_change_type(payload.change_type), payload.change_weight, payload.remark, current_admin["staff_user"].id)
    db.commit()
    db.refresh(log)
    return success_response(serialize_stock_log(log))


@router.post("/materials/{material_id}/loss", response_model=ApiResponse[MaterialStockLogItem])
def create_material_loss(material_id: int, payload: MaterialLossCreate, idempotency_key: str = Header(alias="Idempotency-Key"), current_admin: dict = Depends(require_admin), db: Session = Depends(get_db)):
    material = require_entity(db.get(Material, material_id), "材料不存在")
    log = apply_material_change(db, material, "loss", -payload.weight, payload.remark, current_admin["staff_user"].id, payload.related_order_id, payload.related_task_id)
    db.commit()
    db.refresh(log)
    return success_response(serialize_stock_log(log))


@router.get("/locks", response_model=ApiResponse[PageResponse[InventoryLockInfo]])
def list_locks(page: int = 1, page_size: int = 20, status: LockStatus | None = None, material_id: int | None = None, order_id: int | None = None, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    stmt = select(InventoryLock).order_by(InventoryLock.created_at.desc())
    if status:
        stmt = stmt.where(InventoryLock.status == status)
    if material_id is not None:
        stmt = stmt.where(InventoryLock.material_id == material_id)
    if order_id is not None:
        stmt = stmt.where(InventoryLock.order_id == order_id)
    items, page, page_size, total = paginate(db, stmt, page, page_size)
    return paginated_response([serialize_lock(item) for item in items], page, page_size, total)


@router.post("/locks/{lock_id}/release", response_model=ApiResponse[InventoryLockInfo])
def release_lock(lock_id: int, idempotency_key: str = Header(alias="Idempotency-Key"), _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    lock = require_entity(db.get(InventoryLock, lock_id), "库存锁定不存在")
    if lock.status == "locked":
        lock.status = "released"
        lock.released_at = utc8_now()
        if lock.material_id and lock.weight:
            material = db.get(Material, lock.material_id)
            if material:
                material.reserved_weight = max(0, to_float(material.reserved_weight) - to_float(lock.weight))
    db.commit()
    db.refresh(lock)
    return success_response(serialize_lock(lock))


@router.post("/locks/{lock_id}/consume", response_model=ApiResponse[InventoryLockInfo])
def consume_lock(lock_id: int, idempotency_key: str = Header(alias="Idempotency-Key"), current_admin: dict = Depends(require_admin), db: Session = Depends(get_db)):
    lock = require_entity(db.get(InventoryLock, lock_id), "库存锁定不存在")
    if lock.status == "locked":
        lock.status = "consumed"
        lock.released_at = utc8_now()
        if lock.material_id and lock.weight:
            material = db.get(Material, lock.material_id)
            if material:
                weight = to_float(lock.weight) or 0
                material.reserved_weight = max(0, (to_float(material.reserved_weight) or 0) - weight)
                apply_material_change(db, material, "consume", -weight, "库存锁定消耗", current_admin["staff_user"].id, lock.order_id, lock.print_task_id)
    db.commit()
    db.refresh(lock)
    return success_response(serialize_lock(lock))


@router.get("/finished-goods", response_model=ApiResponse[PageResponse[FinishedGoodsInventoryItem]])
def list_finished_goods(page: int = 1, page_size: int = 20, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    stmt = select(FinishedGoodsInventory).order_by(FinishedGoodsInventory.updated_at.desc())
    items, page, page_size, total = paginate(db, stmt, page, page_size)
    return paginated_response([serialize_finished_good(item) for item in items], page, page_size, total)


def normalize_change_type(change_type: str) -> str:
    return "adjust" if change_type == "adjustment" else change_type


def apply_material_change(db: Session, material: Material, change_type: str, change_weight: float, remark: str | None, staff_user_id: int, related_order_id: int | None = None, related_task_id: int | None = None) -> MaterialStockLog:
    before = to_float(material.stock_weight) or 0
    after = before + change_weight
    if after < 0:
        require_entity(None, "材料库存不足")
    material.stock_weight = after
    log = MaterialStockLog(
        material_id=material.id,
        change_type=change_type,
        change_weight=change_weight,
        before_weight=before,
        after_weight=after,
        related_order_id=related_order_id,
        related_task_id=related_task_id,
        remark=remark,
        created_by=staff_user_id,
    )
    db.add(log)
    return log


def serialize_material(material: Material) -> dict:
    return {
        "id": material.id,
        "name": material.name,
        "material_type": material.material_type,
        "brand": material.brand,
        "color": material.color,
        "diameter": to_float(material.diameter),
        "stock_weight": to_float(material.stock_weight) or 0,
        "reserved_weight": to_float(material.reserved_weight) or 0,
        "safe_stock_weight": to_float(material.safe_stock_weight) or 0,
        "unit_cost": to_float(material.unit_cost),
        "status": material.status,
    }


def serialize_stock_log(log: MaterialStockLog) -> dict:
    return {
        "id": log.id,
        "material_id": log.material_id,
        "change_type": log.change_type,
        "change_weight": to_float(log.change_weight) or 0,
        "before_weight": to_float(log.before_weight),
        "after_weight": to_float(log.after_weight),
        "related_order_id": log.related_order_id,
        "related_task_id": log.related_task_id,
        "remark": log.remark,
        "created_by": log.created_by,
        "created_at": log.created_at,
    }


def serialize_lock(lock: InventoryLock) -> dict:
    return {
        "id": lock.id,
        "lock_type": lock.lock_type,
        "order_id": lock.order_id,
        "print_task_id": lock.print_task_id,
        "material_id": lock.material_id,
        "quantity": lock.quantity,
        "weight": to_float(lock.weight),
        "status": lock.status,
    }


def serialize_finished_good(item: FinishedGoodsInventory) -> dict:
    return {
        "id": item.id,
        "product_id": item.product_id,
        "sku_id": item.sku_id,
        "order_id": item.order_id,
        "available_quantity": item.available_quantity,
        "reserved_quantity": item.reserved_quantity,
        "in_progress_quantity": item.in_progress_quantity,
        "warehouse_location": item.warehouse_location,
        "updated_at": item.updated_at,
    }
