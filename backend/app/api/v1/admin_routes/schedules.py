from datetime import datetime

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field

from app.core.errors import AppError
from app.core.security import require_admin
from app.schemas.response import paginated_response, success_response

router = APIRouter()


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
    items: list[ScheduleItemCreate]
    material_locks: list[MaterialLockCreate] = []


@router.get("")
def list_schedules(page: int = 1, page_size: int = 20, _: dict = Depends(require_admin)):
    return paginated_response([], page, page_size, 0)


@router.post("")
def create_schedule(
    payload: ScheduleCreate,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    _: dict = Depends(require_admin),
):
    if not idempotency_key:
        raise AppError("IDEMPOTENCY_KEY_REQUIRED", "创建排期必须提供 Idempotency-Key")
    if payload.planned_end_at <= payload.planned_start_at:
        raise AppError("VALIDATION_ERROR", "计划结束时间必须晚于开始时间", status_code=422)
    return success_response({"id": None, "order_id": payload.order_id, "status": "scheduled", "item_count": len(payload.items)})


@router.patch("/{schedule_order_id}")
def update_schedule(schedule_order_id: int, payload: ScheduleCreate, _: dict = Depends(require_admin)):
    return success_response({"id": schedule_order_id, "order_id": payload.order_id})
