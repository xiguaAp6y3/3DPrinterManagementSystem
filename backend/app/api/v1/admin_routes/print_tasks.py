from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.security import require_admin
from app.core.time import utc8_now
from app.db.models.core import Order, OrderItem, PrintTask, Printer
from app.db.session import get_db
from app.schemas.response import ApiResponse, PageResponse, paginated_response, success_response
from app.services.db_helpers import next_no, paginate, require_entity
from app.services.order_items import serialize_order_item

router = APIRouter()

PrintTaskStatus = Literal["pending", "scheduled", "printing", "paused", "completed", "failed", "cancelled"]


class PrintTaskCreate(BaseModel):
    order_id: int
    order_item_id: int | None = None
    printer_id: int | None = None
    slice_file_id: int | None = None
    material_id: int | None = None
    priority: int = 0
    plate_count: int = Field(default=1, gt=0)
    planned_quantity: int = Field(default=1, gt=0)
    use_ams: bool = False
    estimated_minutes: int | None = Field(default=None, ge=0)


class PrintTaskStatusUpdate(BaseModel):
    status: PrintTaskStatus
    failure_reason: str | None = None
    remark: str | None = None


class PrintTaskDetail(BaseModel):
    id: int | None = None
    task_no: str | None = None
    order_id: int
    order_item_id: int | None = None
    printer_id: int | None = None
    slice_file_id: int | None = None
    material_id: int | None = None
    status: PrintTaskStatus | str = "pending"
    warehouse_status: str = "not_required"
    priority: int = 0
    plate_count: int = 1
    planned_quantity: int = 1
    use_ams: bool = False
    estimated_minutes: int | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    failure_reason: str | None = None
    item: dict | None = None


@router.get("", response_model=ApiResponse[PageResponse[PrintTaskDetail]])
def list_print_tasks(page: int = 1, page_size: int = 20, status: PrintTaskStatus | None = None, printer_id: int | None = None, order_id: int | None = None, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    stmt = select(PrintTask).order_by(PrintTask.created_at.desc())
    if status:
        stmt = stmt.where(PrintTask.status == status)
    if printer_id is not None:
        stmt = stmt.where(PrintTask.printer_id == printer_id)
    if order_id is not None:
        stmt = stmt.where(PrintTask.order_id == order_id)
    items, page, page_size, total = paginate(db, stmt, page, page_size)
    return paginated_response([serialize_task(db, item) for item in items], page, page_size, total)


@router.post("", response_model=ApiResponse[PrintTaskDetail])
def create_print_task(payload: PrintTaskCreate, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    require_entity(db.get(Order, payload.order_id), "订单不存在")
    order_item_id = resolve_order_item_id(db, payload.order_id, payload.order_item_id)
    if payload.printer_id is not None:
        require_entity(db.get(Printer, payload.printer_id), "打印机不存在")
    task = PrintTask(
        task_no=next_no(db, "seq_print_task_no", "PT"),
        **payload.model_dump(exclude={"order_item_id"}),
        order_item_id=order_item_id,
        status="pending",
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return success_response(serialize_task(db, task))


def resolve_order_item_id(db: Session, order_id: int, order_item_id: int | None) -> int:
    if order_item_id is not None:
        order_item = require_entity(db.get(OrderItem, order_item_id), "订单明细不存在")
        if order_item.order_id != order_id:
            raise AppError("PRINT_TASK_ORDER_ITEM_MISMATCH", "订单明细不属于该订单", 409)
        return order_item.id

    order_items = db.scalars(select(OrderItem).where(OrderItem.order_id == order_id)).all()
    if len(order_items) != 1:
        raise AppError("PRINT_TASK_ORDER_ITEM_REQUIRED", "多商品订单创建打印任务时必须指定订单明细", 409)
    return order_items[0].id


@router.get("/{task_id}", response_model=ApiResponse[PrintTaskDetail])
def get_print_task(task_id: int, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    task = require_entity(db.get(PrintTask, task_id), "打印任务不存在")
    return success_response(serialize_task(db, task))


@router.patch("/{task_id}/status", response_model=ApiResponse[PrintTaskDetail])
def update_print_task_status(task_id: int, payload: PrintTaskStatusUpdate, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    task = require_entity(db.get(PrintTask, task_id), "打印任务不存在")
    task.status = payload.status
    if payload.failure_reason is not None:
        task.failure_reason = payload.failure_reason
    if payload.status == "printing" and task.started_at is None:
        task.started_at = utc8_now()
    if payload.status in {"completed", "failed", "cancelled"}:
        task.finished_at = utc8_now()
    if payload.status == "completed" and task.warehouse_status == "not_required":
        task.warehouse_status = "pending_inbound"
    if task.printer_id:
        printer = db.get(Printer, task.printer_id)
        if printer:
            printer.current_task_id = task.id if payload.status in {"scheduled", "printing", "paused"} else None
            if payload.status == "printing":
                printer.status = "printing"
            elif payload.status == "paused":
                printer.status = "paused"
            elif payload.status == "failed":
                printer.status = "error"
            elif payload.status in {"completed", "cancelled"}:
                printer.status = "idle"
    db.commit()
    db.refresh(task)
    return success_response(serialize_task(db, task))


def serialize_task(db: Session, task: PrintTask) -> dict:
    order_item = db.get(OrderItem, task.order_item_id) if task.order_item_id else None
    return {
        "id": task.id,
        "task_no": task.task_no,
        "order_id": task.order_id,
        "order_item_id": task.order_item_id,
        "printer_id": task.printer_id,
        "slice_file_id": task.slice_file_id,
        "material_id": task.material_id,
        "status": task.status,
        "warehouse_status": task.warehouse_status,
        "priority": task.priority,
        "plate_count": task.plate_count,
        "planned_quantity": task.planned_quantity,
        "use_ams": task.use_ams,
        "estimated_minutes": task.estimated_minutes,
        "started_at": task.started_at,
        "finished_at": task.finished_at,
        "failure_reason": task.failure_reason,
        "item": serialize_order_item(db, order_item) if order_item else None,
    }
