from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.security import require_admin
from app.schemas.response import paginated_response, success_response

router = APIRouter()


class PrinterCreate(BaseModel):
    name: str
    brand: str | None = None
    model: str | None = None
    printer_type: str | None = None
    supported_materials: str | None = None
    build_volume: str | None = None
    location: str | None = None
    status: str = "idle"
    supports_api: bool = False
    api_endpoint: str | None = None
    remark: str | None = None


class PrinterStatusUpdate(BaseModel):
    status: str
    remark: str | None = None


@router.get("")
def list_printers(page: int = 1, page_size: int = 20, _: dict = Depends(require_admin)):
    return paginated_response([], page, page_size, 0)


@router.post("")
def create_printer(payload: PrinterCreate, _: dict = Depends(require_admin)):
    return success_response({"id": None, **payload.model_dump()})


@router.get("/{printer_id}")
def get_printer(printer_id: int, _: dict = Depends(require_admin)):
    return success_response({"id": printer_id})


@router.patch("/{printer_id}")
def update_printer(printer_id: int, payload: PrinterCreate, _: dict = Depends(require_admin)):
    return success_response({"id": printer_id, **payload.model_dump()})


@router.patch("/{printer_id}/status")
def update_printer_status(printer_id: int, payload: PrinterStatusUpdate, _: dict = Depends(require_admin)):
    return success_response({"id": printer_id, "status": payload.status, "remark": payload.remark})
