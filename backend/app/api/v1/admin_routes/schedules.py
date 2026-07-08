from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field

from app.core.errors import AppError
from app.core.security import require_admin
from app.schemas.response import ApiResponse, PageResponse, paginated_response, success_response

router = APIRouter()

ScheduleStatus = Literal["scheduled", "printing", "completed", "cancelled"]


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
def list_schedules(page: int = 1, page_size: int = 20, printer_id: int | None = None, order_id: int | None = None, status: ScheduleStatus | None = None, start_date: datetime | None = None, end_date: datetime | None = None, _: dict = Depends(require_admin)):
    return paginated_response([], page, page_size, 0)


@router.post("", response_model=ApiResponse[ScheduleDetail])
def create_schedule(payload: ScheduleCreate, idempotency_key: str = Header(alias="Idempotency-Key"), _: dict = Depends(require_admin)):
    if payload.planned_end_at <= payload.planned_start_at:
        raise AppError("VALIDATION_ERROR", "计划结束时间必须晚于开始时间", status_code=422)
    return success_response({"id": None, "schedule_no": "SCH-PENDING", "order_id": payload.order_id, "status": "scheduled", "planned_start_at": payload.planned_start_at, "planned_end_at": payload.planned_end_at, "due_at": payload.due_at, "priority": payload.priority, "items": [item.model_dump() for item in payload.items], "material_locks": [item.model_dump() for item in payload.material_locks]})


@router.get("/{schedule_order_id}", response_model=ApiResponse[ScheduleDetail])
def get_schedule(schedule_order_id: int, _: dict = Depends(require_admin)):
    return success_response({"id": schedule_order_id, "schedule_no": f"SCH-{schedule_order_id}", "order_id": 0, "items": [], "material_locks": []})


@router.patch("/{schedule_order_id}", response_model=ApiResponse[ScheduleDetail])
def update_schedule(schedule_order_id: int, payload: ScheduleCreate, _: dict = Depends(require_admin)):
    return success_response({"id": schedule_order_id, "order_id": payload.order_id, "items": [item.model_dump() for item in payload.items], "material_locks": [item.model_dump() for item in payload.material_locks]})


@router.delete("/{schedule_order_id}", response_model=ApiResponse[ScheduleDetail])
def cancel_schedule(schedule_order_id: int, _: dict = Depends(require_admin)):
    return success_response({"id": schedule_order_id, "schedule_no": f"SCH-{schedule_order_id}", "order_id": 0, "status": "cancelled", "items": [], "material_locks": []})


