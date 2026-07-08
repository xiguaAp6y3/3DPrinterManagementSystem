from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.security import require_admin
from app.schemas.response import ApiResponse, success_response

router = APIRouter()

ScheduleStatus = Literal["scheduled", "printing", "completed", "cancelled"]


class ScheduleItemUpdate(BaseModel):
    printer_id: int | None = None
    scheduled_start_at: datetime | None = None
    scheduled_end_at: datetime | None = None
    status: ScheduleStatus | None = None
    sort_order: int | None = None


class ScheduleItemDetail(BaseModel):
    id: int
    schedule_order_id: int | None = None
    print_task_id: int | None = None
    printer_id: int | None = None
    scheduled_start_at: datetime | None = None
    scheduled_end_at: datetime | None = None
    status: ScheduleStatus | str = "scheduled"
    sort_order: int = 0


@router.get("/{schedule_item_id}", response_model=ApiResponse[ScheduleItemDetail])
def get_schedule_item(schedule_item_id: int, _: dict = Depends(require_admin)):
    return success_response({"id": schedule_item_id, "status": "scheduled"})


@router.patch("/{schedule_item_id}", response_model=ApiResponse[ScheduleItemDetail])
def update_schedule_item(schedule_item_id: int, payload: ScheduleItemUpdate, _: dict = Depends(require_admin)):
    return success_response({"id": schedule_item_id, **payload.model_dump(exclude_none=True)})
