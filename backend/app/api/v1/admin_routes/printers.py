from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.security import require_admin
from app.core.time import utc8_now
from app.db.models.core import Printer, PrinterStatusLog
from app.db.session import get_db
from app.schemas.response import ApiResponse, PageResponse, paginated_response, success_response
from app.services.db_helpers import paginate, require_entity

router = APIRouter()

PrinterStatus = Literal["idle", "printing", "paused", "completed", "error", "offline", "maintenance"]


class PrinterCreate(BaseModel):
    name: str
    brand: str | None = None
    model: str | None = None
    printer_type: str | None = None
    supported_materials: str | None = None
    build_volume: str | None = None
    location: str | None = None
    status: PrinterStatus = "idle"
    supports_api: bool = False
    api_endpoint: str | None = None
    remark: str | None = None


class PrinterUpdate(BaseModel):
    name: str | None = None
    brand: str | None = None
    model: str | None = None
    printer_type: str | None = None
    supported_materials: str | None = None
    build_volume: str | None = None
    location: str | None = None
    status: PrinterStatus | None = None
    supports_api: bool | None = None
    api_endpoint: str | None = None
    remark: str | None = None


class PrinterStatusUpdate(BaseModel):
    status: PrinterStatus
    remark: str | None = None


class PrinterItem(BaseModel):
    id: int | None = None
    name: str | None = None
    brand: str | None = None
    model: str | None = None
    printer_type: str | None = None
    supported_materials: str | None = None
    build_volume: str | None = None
    location: str | None = None
    status: PrinterStatus = "idle"
    current_task_id: int | None = None
    supports_api: bool = False
    api_endpoint: str | None = None
    last_seen_at: datetime | None = None
    remark: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@router.get("", response_model=ApiResponse[PageResponse[PrinterItem]])
def list_printers(page: int = 1, page_size: int = 20, status: PrinterStatus | None = None, keyword: str | None = None, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    stmt = select(Printer).order_by(Printer.id.desc())
    if status:
        stmt = stmt.where(Printer.status == status)
    if keyword:
        stmt = stmt.where(or_(Printer.name.contains(keyword), Printer.brand.contains(keyword), Printer.model.contains(keyword), Printer.location.contains(keyword)))
    items, page, page_size, total = paginate(db, stmt, page, page_size)
    return paginated_response([serialize_printer(item) for item in items], page, page_size, total)


@router.post("", response_model=ApiResponse[PrinterItem])
def create_printer(payload: PrinterCreate, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    printer = Printer(**payload.model_dump())
    db.add(printer)
    db.commit()
    db.refresh(printer)
    return success_response(serialize_printer(printer))


@router.get("/{printer_id}", response_model=ApiResponse[PrinterItem])
def get_printer(printer_id: int, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    printer = require_entity(db.get(Printer, printer_id), "打印机不存在")
    return success_response(serialize_printer(printer))


@router.patch("/{printer_id}", response_model=ApiResponse[PrinterItem])
def update_printer(printer_id: int, payload: PrinterUpdate, current_admin: dict = Depends(require_admin), db: Session = Depends(get_db)):
    printer = require_entity(db.get(Printer, printer_id), "打印机不存在")
    old_status = printer.status
    for key, value in payload.model_dump(exclude_none=True).items():
        setattr(printer, key, value)
    if payload.status and payload.status != old_status:
        db.add(PrinterStatusLog(printer_id=printer.id, from_status=old_status, to_status=payload.status, changed_by=current_admin["staff_user"].id))
    db.commit()
    db.refresh(printer)
    return success_response(serialize_printer(printer))


@router.patch("/{printer_id}/status", response_model=ApiResponse[PrinterItem])
def update_printer_status(printer_id: int, payload: PrinterStatusUpdate, current_admin: dict = Depends(require_admin), db: Session = Depends(get_db)):
    printer = require_entity(db.get(Printer, printer_id), "打印机不存在")
    old_status = printer.status
    printer.status = payload.status
    if payload.remark is not None:
        printer.remark = payload.remark
    printer.last_seen_at = utc8_now()
    db.add(PrinterStatusLog(printer_id=printer.id, from_status=old_status, to_status=payload.status, changed_by=current_admin["staff_user"].id))
    db.commit()
    db.refresh(printer)
    return success_response(serialize_printer(printer))


def serialize_printer(printer: Printer) -> dict:
    return {
        "id": printer.id,
        "name": printer.name,
        "brand": printer.brand,
        "model": printer.model,
        "printer_type": printer.printer_type,
        "supported_materials": printer.supported_materials,
        "build_volume": printer.build_volume,
        "location": printer.location,
        "status": printer.status,
        "current_task_id": printer.current_task_id,
        "supports_api": printer.supports_api,
        "api_endpoint": printer.api_endpoint,
        "last_seen_at": printer.last_seen_at,
        "remark": printer.remark,
        "created_at": printer.created_at,
        "updated_at": printer.updated_at,
    }
