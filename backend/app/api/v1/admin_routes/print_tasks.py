from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.security import require_admin
from app.schemas.response import ApiResponse, PageResponse, paginated_response, success_response

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
    priority: int = 0
    plate_count: int = 1
    use_ams: bool = False
    estimated_minutes: int | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    failure_reason: str | None = None


@router.get("", response_model=ApiResponse[PageResponse[PrintTaskDetail]])
def list_print_tasks(page: int = 1, page_size: int = 20, status: PrintTaskStatus | None = None, printer_id: int | None = None, order_id: int | None = None, _: dict = Depends(require_admin)):
    return paginated_response([], page, page_size, 0)


@router.post("", response_model=ApiResponse[PrintTaskDetail])
def create_print_task(payload: PrintTaskCreate, _: dict = Depends(require_admin)):
    return success_response({"id": None, "task_no": "PT-PENDING", "status": "pending", **payload.model_dump()})


@router.get("/{task_id}", response_model=ApiResponse[PrintTaskDetail])
def get_print_task(task_id: int, _: dict = Depends(require_admin)):
    return success_response({"id": task_id, "task_no": f"PT-{task_id}", "order_id": 0, "status": "pending"})


@router.patch("/{task_id}/status", response_model=ApiResponse[PrintTaskDetail])
def update_print_task_status(task_id: int, payload: PrintTaskStatusUpdate, _: dict = Depends(require_admin)):
    return success_response({"id": task_id, "task_no": f"PT-{task_id}", "order_id": 0, "status": payload.status, "failure_reason": payload.failure_reason})
