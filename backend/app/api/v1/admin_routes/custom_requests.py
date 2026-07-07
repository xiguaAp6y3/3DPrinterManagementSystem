from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.security import require_admin
from app.schemas.response import ApiResponse, PageResponse, paginated_response, success_response

router = APIRouter()

CustomRequestStatus = Literal["submitted", "reviewing", "need_more_info", "rejected", "quote_pending", "quoted", "quote_confirmed", "payment_confirmed", "scheduled"]
ReviewTargetStatus = Literal["reviewing", "need_more_info", "rejected", "quote_pending"]


class CustomRequestSummary(BaseModel):
    id: int | None = None
    request_no: str | None = None
    user_id: int | None = None
    slice_file_id: int | None = None
    status: CustomRequestStatus | str = "submitted"
    plate_count: int = 1
    use_ams: bool = False
    created_at: datetime | None = None


class CustomRequestDetail(CustomRequestSummary):
    requested_print_time: datetime | None = None
    preferred_printer_id: int | None = None
    preferred_printer_model: str | None = None
    filament_color: str | None = None
    filament_type: str | None = None
    reviewer_id: int | None = None
    reviewed_at: datetime | None = None
    review_remark: str | None = None
    files: list[dict[str, Any]] = Field(default_factory=list)
    quotes: list[dict[str, Any]] = Field(default_factory=list)


class ReviewRequest(BaseModel):
    status: ReviewTargetStatus
    remark: str | None = None


@router.get("", response_model=ApiResponse[PageResponse[CustomRequestSummary]])
def list_custom_requests(page: int = 1, page_size: int = 20, status: CustomRequestStatus | None = None, keyword: str | None = None, created_from: datetime | None = None, created_to: datetime | None = None, _: dict = Depends(require_admin)):
    return paginated_response([], page, page_size, 0)


@router.get("/{request_id}", response_model=ApiResponse[CustomRequestDetail])
def get_custom_request(request_id: int, _: dict = Depends(require_admin)):
    return success_response({"id": request_id, "request_no": f"CR-{request_id}", "files": [], "quotes": []})


@router.patch("/{request_id}/review", response_model=ApiResponse[CustomRequestDetail])
def review_custom_request(request_id: int, payload: ReviewRequest, _: dict = Depends(require_admin)):
    return success_response({"id": request_id, "request_no": f"CR-{request_id}", "status": payload.status, "review_remark": payload.remark, "files": [], "quotes": []})
