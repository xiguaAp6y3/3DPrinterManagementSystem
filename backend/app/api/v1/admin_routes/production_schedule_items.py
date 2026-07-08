from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.security import require_admin
from app.db.models.core import Printer, ProductionScheduleItem
from app.db.session import get_db
from app.schemas.response import ApiResponse, success_response
from app.services.db_helpers import require_entity

router = APIRouter()

ScheduleStatus = Literal["scheduled", "locked", "in_progress", "delayed", "completed", "cancelled"]


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
def get_schedule_item(schedule_item_id: int, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    item = require_entity(db.get(ProductionScheduleItem, schedule_item_id), "排期明细不存在")
    return success_response(serialize_item(item))


@router.patch("/{schedule_item_id}", response_model=ApiResponse[ScheduleItemDetail])
def update_schedule_item(schedule_item_id: int, payload: ScheduleItemUpdate, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    item = require_entity(db.get(ProductionScheduleItem, schedule_item_id), "排期明细不存在")
    if payload.printer_id is not None:
        require_entity(db.get(Printer, payload.printer_id), "打印机不存在")
    for key, value in payload.model_dump(exclude_none=True).items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return success_response(serialize_item(item))


def serialize_item(item: ProductionScheduleItem) -> dict:
    return {
        "id": item.id,
        "schedule_order_id": item.schedule_order_id,
        "print_task_id": item.print_task_id,
        "printer_id": item.printer_id,
        "scheduled_start_at": item.scheduled_start_at,
        "scheduled_end_at": item.scheduled_end_at,
        "status": item.status,
        "sort_order": item.sort_order,
    }
