from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.security import require_admin
from app.core.time import utc8_now
from app.db.models.core import InventoryLock, Material, Order, OrderItem, Printer, PrintTask, ProductionScheduleItem, ProductionScheduleOrder
from app.db.session import get_db
from app.schemas.response import ApiResponse, PageResponse, paginated_response, success_response
from app.services.db_helpers import next_no, paginate, require_entity, to_float
from app.services.order_items import serialize_order_item

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


class SchedulePrintTaskCreate(BaseModel):
    order_item_id: int
    printer_id: int
    scheduled_start_at: datetime
    scheduled_end_at: datetime
    slice_file_id: int | None = None
    material_id: int | None = None
    priority: int = 0
    plate_count: int = Field(default=1, gt=0)
    planned_quantity: int = Field(default=1, gt=0)
    use_ams: bool = False
    estimated_minutes: int | None = Field(default=None, ge=0)


class SchedulePrintTaskBatchCreate(BaseModel):
    tasks: list[SchedulePrintTaskCreate] = Field(min_length=1)


class ScheduleItemDetail(BaseModel):
    id: int | None = None
    schedule_order_id: int | None = None
    print_task_id: int | None = None
    print_task: dict[str, Any] | None = None
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
    order_items: list[dict[str, Any]] = Field(default_factory=list)
    print_tasks: list[dict[str, Any]] = Field(default_factory=list)
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
            if task.order_id != order.id:
                raise AppError("SCHEDULE_TASK_ORDER_MISMATCH", "打印任务不属于该订单", 409)
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


@router.post("/{schedule_order_id}/print-tasks", response_model=ApiResponse[ScheduleDetail])
def create_schedule_print_tasks(schedule_order_id: int, payload: SchedulePrintTaskBatchCreate, current_admin: dict = Depends(require_admin), db: Session = Depends(get_db)):
    schedule = require_entity(db.get(ProductionScheduleOrder, schedule_order_id), "排期不存在")
    if schedule.status == "cancelled":
        raise AppError("SCHEDULE_CANCELLED", "已取消排期不能创建打印任务", 409)

    existing_count = len(
        db.scalars(
            select(ProductionScheduleItem.id).where(ProductionScheduleItem.schedule_order_id == schedule.id)
        ).all()
    )
    for offset, task_payload in enumerate(payload.tasks):
        if task_payload.scheduled_end_at <= task_payload.scheduled_start_at:
            raise AppError("VALIDATION_ERROR", "打印任务结束时间必须晚于开始时间", status_code=422)
        if task_payload.scheduled_start_at < schedule.planned_start_at or task_payload.scheduled_end_at > schedule.planned_end_at:
            raise AppError("SCHEDULE_TIME_OUT_OF_RANGE", "打印任务时间必须在排期时间范围内", 409)
        order_item = require_entity(db.get(OrderItem, task_payload.order_item_id), "订单明细不存在")
        if order_item.order_id != schedule.order_id:
            raise AppError("SCHEDULE_ORDER_ITEM_MISMATCH", "订单明细不属于该排期订单", 409)
        require_entity(db.get(Printer, task_payload.printer_id), "打印机不存在")
        task = PrintTask(
            task_no=next_no(db, "seq_print_task_no", "PT"),
            order_id=schedule.order_id,
            order_item_id=order_item.id,
            printer_id=task_payload.printer_id,
            slice_file_id=task_payload.slice_file_id,
            material_id=task_payload.material_id,
            status="scheduled",
            priority=task_payload.priority,
            plate_count=task_payload.plate_count,
            planned_quantity=task_payload.planned_quantity,
            use_ams=task_payload.use_ams,
            estimated_minutes=task_payload.estimated_minutes,
        )
        db.add(task)
        db.flush()
        db.add(
            ProductionScheduleItem(
                schedule_order_id=schedule.id,
                print_task_id=task.id,
                printer_id=task.printer_id,
                scheduled_start_at=task_payload.scheduled_start_at,
                scheduled_end_at=task_payload.scheduled_end_at,
                status="scheduled",
                sort_order=(existing_count or 0) + offset,
            )
        )
    schedule.status = "scheduled"
    db.commit()
    db.refresh(schedule)
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
        "order_items": [],
        "print_tasks": [],
        "items": [],
        "material_locks": [],
    }
    if include_items:
        order_items = db.scalars(select(OrderItem).where(OrderItem.order_id == schedule.order_id).order_by(OrderItem.id)).all()
        print_tasks = db.scalars(select(PrintTask).where(PrintTask.order_id == schedule.order_id).order_by(PrintTask.id)).all()
        items = db.scalars(select(ProductionScheduleItem).where(ProductionScheduleItem.schedule_order_id == schedule.id).order_by(ProductionScheduleItem.sort_order, ProductionScheduleItem.id)).all()
        locks = db.scalars(select(InventoryLock).where(InventoryLock.order_id == schedule.order_id).order_by(InventoryLock.id)).all()
        order_item_data = {item.id: serialize_order_item(db, item) for item in order_items}
        data["order_items"] = list(order_item_data.values())
        data["print_tasks"] = [
            {
                "id": task.id,
                "task_no": task.task_no,
                "order_item_id": task.order_item_id,
                "item": order_item_data.get(task.order_item_id),
                "printer_id": task.printer_id,
                "status": task.status,
                "plate_count": task.plate_count,
                "planned_quantity": task.planned_quantity,
                "estimated_minutes": task.estimated_minutes,
            }
            for task in print_tasks
        ]
        task_data = {task["id"]: task for task in data["print_tasks"]}
        data["items"] = [
            {
                "id": item.id,
                "schedule_order_id": item.schedule_order_id,
                "print_task_id": item.print_task_id,
                "print_task": task_data.get(item.print_task_id),
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


