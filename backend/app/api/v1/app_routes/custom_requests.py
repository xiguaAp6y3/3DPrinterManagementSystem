from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field

from app.core.security import require_app_user
from app.schemas.response import ApiResponse, PageResponse, paginated_response, success_response

router = APIRouter()

CustomRequestStatus = Literal["submitted", "reviewing", "need_more_info", "rejected", "quote_pending", "quoted", "quote_confirmed", "payment_confirmed", "scheduled"]


class CreateCustomRequest(BaseModel):
    slice_file_id: int
    requested_print_time: datetime | None = None
    preferred_printer_id: int | None = None
    preferred_printer_model: str | None = None
    filament_color: str | None = None
    filament_type: str | None = None
    use_ams: bool
    plate_count: int = Field(gt=0)


class CustomRequestSummary(BaseModel):
    id: int | None = None
    request_no: str
    status: CustomRequestStatus | str
    slice_file_id: int | None = None
    plate_count: int
    use_ams: bool
    created_at: datetime | None = None


class CustomRequestDetail(CustomRequestSummary):
    requested_print_time: datetime | None = None
    preferred_printer_id: int | None = None
    preferred_printer_model: str | None = None
    filament_color: str | None = None
    filament_type: str | None = None
    review_remark: str | None = None
    quotes: list[dict[str, Any]] = Field(default_factory=list)


@router.get("", response_model=ApiResponse[PageResponse[CustomRequestSummary]])
def list_custom_requests(page: int = 1, page_size: int = 20, status: CustomRequestStatus | None = None, keyword: str | None = None, created_from: datetime | None = None, created_to: datetime | None = None, _: dict = Depends(require_app_user)):
    return paginated_response([], page, page_size, 0)


@router.post("", response_model=ApiResponse[CustomRequestSummary])
def create_custom_request(payload: CreateCustomRequest, idempotency_key: str = Header(alias="Idempotency-Key"), _: dict = Depends(require_app_user)):
    return success_response({"id": None, "request_no": "CR-PENDING", "status": "submitted", "slice_file_id": payload.slice_file_id, "plate_count": payload.plate_count, "use_ams": payload.use_ams})


@router.get("/{request_id}", response_model=ApiResponse[CustomRequestDetail])
def get_custom_request(request_id: int, _: dict = Depends(require_app_user)):
    return success_response({"id": request_id, "request_no": f"CR-{request_id}", "status": "submitted", "slice_file_id": None, "plate_count": 1, "use_ams": False, "quotes": []})


@router.patch("/{request_id}", response_model=ApiResponse[CustomRequestDetail])
def update_custom_request(request_id: int, payload: CreateCustomRequest, _: dict = Depends(require_app_user)):
    return success_response({"id": request_id, "request_no": f"CR-{request_id}", "status": "submitted", "slice_file_id": payload.slice_file_id, "plate_count": payload.plate_count, "use_ams": payload.use_ams, **payload.model_dump(), "quotes": []})
