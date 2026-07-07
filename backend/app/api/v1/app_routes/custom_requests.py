from datetime import datetime

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field

from app.core.errors import AppError
from app.core.security import require_app_user
from app.schemas.response import success_response

router = APIRouter()


class CreateCustomRequest(BaseModel):
    slice_file_id: int
    requested_print_time: datetime | None = None
    preferred_printer_id: int | None = None
    preferred_printer_model: str | None = None
    filament_color: str | None = None
    filament_type: str | None = None
    use_ams: bool
    plate_count: int = Field(gt=0)


@router.post("")
def create_custom_request(
    payload: CreateCustomRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    _: dict = Depends(require_app_user),
):
    if not idempotency_key:
        raise AppError("IDEMPOTENCY_KEY_REQUIRED", "提交定制需求必须提供 Idempotency-Key")
    return success_response({"id": None, "request_no": "CR-PENDING", "status": "submitted", "plate_count": payload.plate_count})


@router.get("/{request_id}")
def get_custom_request(request_id: int, _: dict = Depends(require_app_user)):
    return success_response({"id": request_id})


@router.patch("/{request_id}")
def update_custom_request(request_id: int, payload: CreateCustomRequest, _: dict = Depends(require_app_user)):
    return success_response({"id": request_id, "status": "submitted", "plate_count": payload.plate_count})
