from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.security import require_admin
from app.schemas.response import ApiResponse, PageResponse, paginated_response, success_response

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
def list_printers(page: int = 1, page_size: int = 20, status: PrinterStatus | None = None, keyword: str | None = None, _: dict = Depends(require_admin)):
    return paginated_response([], page, page_size, 0)


@router.post("", response_model=ApiResponse[PrinterItem])
def create_printer(payload: PrinterCreate, _: dict = Depends(require_admin)):
    return success_response({"id": None, **payload.model_dump()})


@router.get("/{printer_id}", response_model=ApiResponse[PrinterItem])
def get_printer(printer_id: int, _: dict = Depends(require_admin)):
    return success_response({"id": printer_id, "status": "idle", "supports_api": False})


@router.patch("/{printer_id}", response_model=ApiResponse[PrinterItem])
def update_printer(printer_id: int, payload: PrinterUpdate, _: dict = Depends(require_admin)):
    return success_response({"id": printer_id, **payload.model_dump(exclude_none=True)})


@router.patch("/{printer_id}/status", response_model=ApiResponse[PrinterItem])
def update_printer_status(printer_id: int, payload: PrinterStatusUpdate, _: dict = Depends(require_admin)):
    return success_response({"id": printer_id, "status": payload.status, "remark": payload.remark})
