from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_admin
from app.core.time import utc8_now
from app.db.models.core import Order, PrintTask, Printer
from app.db.session import get_db
from app.schemas.response import ApiResponse, PageResponse, paginated_response, success_response
from app.services.db_helpers import next_no, paginate, require_entity

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
    use_ams: bool = False
    estimated_minutes: int | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    failure_reason: str | None = None


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
    return paginated_response([serialize_task(item) for item in items], page, page_size, total)


@router.post("", response_model=ApiResponse[PrintTaskDetail])
def create_print_task(payload: PrintTaskCreate, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    require_entity(db.get(Order, payload.order_id), "订单不存在")
    if payload.printer_id is not None:
        require_entity(db.get(Printer, payload.printer_id), "打印机不存在")
    task = PrintTask(task_no=next_no(db, "seq_print_task_no", "PT"), **payload.model_dump(), status="pending")
    db.add(task)
    db.commit()
    db.refresh(task)
    return success_response(serialize_task(task))


@router.get("/{task_id}", response_model=ApiResponse[PrintTaskDetail])
def get_print_task(task_id: int, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    task = require_entity(db.get(PrintTask, task_id), "打印任务不存在")
    return success_response(serialize_task(task))


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
    return success_response(serialize_task(task))


def serialize_task(task: PrintTask) -> dict:
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
        "use_ams": task.use_ams,
        "estimated_minutes": task.estimated_minutes,
        "started_at": task.started_at,
        "finished_at": task.finished_at,
        "failure_reason": task.failure_reason,
    }
