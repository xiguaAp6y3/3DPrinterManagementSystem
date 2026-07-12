from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.security import require_admin
from app.core.time import utc8_now
from app.db.models.core import InventoryLock, Material, Order, Printer, PrintTask, ProductionScheduleItem, ProductionScheduleOrder
from app.db.session import get_db
from app.schemas.response import ApiResponse, PageResponse, paginated_response, success_response
from app.services.db_helpers import next_no, paginate, require_entity, to_float

router = APIRouter()

ScheduleStatus = Literal["scheduled", "locked", "in_progress", "delayed", "completed", "cancelled"]


class ScheduleItemCreate(BaseModel):
    print_task_id: int | None = None
    printer_id: int
    scheduled_start_at: datetime
    scheduled_end_at: datetime


class MaterialLockCreate(BaseModel):
    material_id: int
    weight: float = Field(gt=0)


class ScheduleCreate(BaseModel):
    order_id: int
    planned_start_at: datetime
    planned_end_at: datetime
    due_at: datetime | None = None
    priority: int = 0
    items: list[ScheduleItemCreate] = Field(default_factory=list)
    material_locks: list[MaterialLockCreate] = Field(default_factory=list)


class ScheduleItemDetail(BaseModel):
    id: int | None = None
    schedule_order_id: int | None = None
    print_task_id: int | None = None
    printer_id: int | None = None
    scheduled_start_at: datetime | None = None
    scheduled_end_at: datetime | None = None
    status: ScheduleStatus = "scheduled"
    sort_order: int = 0


class ScheduleDetail(BaseModel):
    id: int | None = None
    schedule_no: str | None = None
    order_id: int
    status: ScheduleStatus = "scheduled"
    planned_start_at: datetime | None = None
    planned_end_at: datetime | None = None
    due_at: datetime | None = None
    priority: int = 0
    items: list[ScheduleItemDetail] = Field(default_factory=list)
    material_locks: list[dict[str, Any]] = Field(default_factory=list)


@router.get("", response_model=ApiResponse[PageResponse[ScheduleDetail]])
def list_schedules(page: int = 1, page_size: int = 20, printer_id: int | None = None, order_id: int | None = None, status: ScheduleStatus | None = None, start_date: datetime | None = None, end_date: datetime | None = None, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    stmt = select(ProductionScheduleOrder).order_by(ProductionScheduleOrder.planned_start_at.desc())
    if order_id is not None:
        stmt = stmt.where(ProductionScheduleOrder.order_id == order_id)
    if status:
        stmt = stmt.where(ProductionScheduleOrder.status == status)
    if start_date:
        stmt = stmt.where(ProductionScheduleOrder.planned_end_at >= start_date)
    if end_date:
        stmt = stmt.where(ProductionScheduleOrder.planned_start_at <= end_date)
    if printer_id is not None:
        schedule_ids = select(ProductionScheduleItem.schedule_order_id).where(ProductionScheduleItem.printer_id == printer_id)
        stmt = stmt.where(ProductionScheduleOrder.id.in_(schedule_ids))
    items, page, page_size, total = paginate(db, stmt, page, page_size)
    return paginated_response([serialize_schedule(db, item, include_items=False) for item in items], page, page_size, total)


@router.post("", response_model=ApiResponse[ScheduleDetail])
def create_schedule(payload: ScheduleCreate, idempotency_key: str = Header(alias="Idempotency-Key"), current_admin: dict = Depends(require_admin), db: Session = Depends(get_db)):
    if payload.planned_end_at <= payload.planned_start_at:
        raise AppError("VALIDATION_ERROR", "计划结束时间必须晚于开始时间", status_code=422)
    order = require_entity(db.get(Order, payload.order_id), "订单不存在")
    schedule = ProductionScheduleOrder(
        schedule_no=next_no(db, "seq_schedule_no", "SCH"),
        order_id=payload.order_id,
        status="scheduled",
        planned_start_at=payload.planned_start_at,
        planned_end_at=payload.planned_end_at,
        due_at=payload.due_at,
        priority=payload.priority,
        created_by=current_admin["staff_user"].id,
    )
    db.add(schedule)
    db.flush()
    for idx, item in enumerate(payload.items):
        if item.scheduled_end_at <= item.scheduled_start_at:
            raise AppError("VALIDATION_ERROR", "排期明细结束时间必须晚于开始时间", status_code=422)
        require_entity(db.get(Printer, item.printer_id), "打印机不存在")
        if item.print_task_id is not None:
            task = require_entity(db.get(PrintTask, item.print_task_id), "打印任务不存在")
            task.status = "scheduled"
            task.printer_id = item.printer_id
        db.add(ProductionScheduleItem(schedule_order_id=schedule.id, sort_order=idx, status="scheduled", **item.model_dump()))
    for lock in payload.material_locks:
        material = require_entity(db.get(Material, lock.material_id), "材料不存在")
        available = (to_float(material.stock_weight) or 0) - (to_float(material.reserved_weight) or 0)
        if available < lock.weight:
            raise AppError("INSUFFICIENT_MATERIAL_STOCK", "材料库存不足", status_code=409, details={"material_id": lock.material_id, "available": available, "required": lock.weight})
        material.reserved_weight = (to_float(material.reserved_weight) or 0) + lock.weight
        db.add(InventoryLock(lock_type="material", order_id=order.id, material_id=material.id, weight=lock.weight, status="locked", locked_by=current_admin["staff_user"].id))
    order.status = "scheduled"
    db.commit()
    db.refresh(schedule)
    return success_response(serialize_schedule(db, schedule))


@router.get("/{schedule_order_id}", response_model=ApiResponse[ScheduleDetail])
def get_schedule(schedule_order_id: int, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    schedule = require_entity(db.get(ProductionScheduleOrder, schedule_order_id), "排期不存在")
    return success_response(serialize_schedule(db, schedule))


@router.patch("/{schedule_order_id}", response_model=ApiResponse[ScheduleDetail])
def update_schedule(schedule_order_id: int, payload: ScheduleCreate, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    schedule = require_entity(db.get(ProductionScheduleOrder, schedule_order_id), "排期不存在")
    schedule.order_id = payload.order_id
    schedule.planned_start_at = payload.planned_start_at
    schedule.planned_end_at = payload.planned_end_at
    schedule.due_at = payload.due_at
    schedule.priority = payload.priority
    for item in db.scalars(select(ProductionScheduleItem).where(ProductionScheduleItem.schedule_order_id == schedule.id)).all():
        db.delete(item)
    db.flush()
    for idx, item in enumerate(payload.items):
        require_entity(db.get(Printer, item.printer_id), "打印机不存在")
        db.add(ProductionScheduleItem(schedule_order_id=schedule.id, sort_order=idx, status="scheduled", **item.model_dump()))
    db.commit()
    db.refresh(schedule)
    return success_response(serialize_schedule(db, schedule))


@router.delete("/{schedule_order_id}", response_model=ApiResponse[ScheduleDetail])
def cancel_schedule(schedule_order_id: int, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    schedule = require_entity(db.get(ProductionScheduleOrder, schedule_order_id), "排期不存在")
    schedule.status = "cancelled"
    for item in db.scalars(select(ProductionScheduleItem).where(ProductionScheduleItem.schedule_order_id == schedule.id)).all():
        item.status = "cancelled"
    for lock in db.scalars(select(InventoryLock).where(InventoryLock.order_id == schedule.order_id, InventoryLock.status == "locked")).all():
        lock.status = "released"
        lock.released_at = utc8_now()
        if lock.material_id and lock.weight:
            material = db.get(Material, lock.material_id)
            if material:
                material.reserved_weight = max(0, (to_float(material.reserved_weight) or 0) - (to_float(lock.weight) or 0))
    db.commit()
    db.refresh(schedule)
    return success_response(serialize_schedule(db, schedule))


def serialize_schedule(db: Session, schedule: ProductionScheduleOrder, include_items: bool = True) -> dict:
    data = {
        "id": schedule.id,
        "schedule_no": schedule.schedule_no,
        "order_id": schedule.order_id,
        "status": schedule.status,
        "planned_start_at": schedule.planned_start_at,
        "planned_end_at": schedule.planned_end_at,
        "due_at": schedule.due_at,
        "priority": schedule.priority,
        "items": [],
        "material_locks": [],
    }
    if include_items:
        items = db.scalars(select(ProductionScheduleItem).where(ProductionScheduleItem.schedule_order_id == schedule.id).order_by(ProductionScheduleItem.sort_order, ProductionScheduleItem.id)).all()
        locks = db.scalars(select(InventoryLock).where(InventoryLock.order_id == schedule.order_id).order_by(InventoryLock.id)).all()
        data["items"] = [
            {
                "id": item.id,
                "schedule_order_id": item.schedule_order_id,
                "print_task_id": item.print_task_id,
                "printer_id": item.printer_id,
                "scheduled_start_at": item.scheduled_start_at,
                "scheduled_end_at": item.scheduled_end_at,
                "status": item.status,
                "sort_order": item.sort_order,
            }
            for item in items
        ]
        data["material_locks"] = [{"id": item.id, "material_id": item.material_id, "weight": to_float(item.weight), "status": item.status} for item in locks]
    return data


