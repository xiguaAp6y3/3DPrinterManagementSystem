from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.security import require_admin
from app.db.models.core import CustomRequest, CustomRequestReview, ModelFile, Quote
from app.db.session import get_db
from app.schemas.response import ApiResponse, PageResponse, paginated_response, success_response
from app.services.db_helpers import paginate, require_entity, to_float

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
def list_custom_requests(page: int = 1, page_size: int = 20, status: CustomRequestStatus | None = None, keyword: str | None = None, created_from: datetime | None = None, created_to: datetime | None = None, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    stmt = select(CustomRequest).order_by(CustomRequest.created_at.desc())
    if status:
        stmt = stmt.where(CustomRequest.status == status)
    if keyword:
        stmt = stmt.where(or_(CustomRequest.request_no.contains(keyword), CustomRequest.review_remark.contains(keyword)))
    if created_from:
        stmt = stmt.where(CustomRequest.created_at >= created_from)
    if created_to:
        stmt = stmt.where(CustomRequest.created_at <= created_to)
    items, page, page_size, total = paginate(db, stmt, page, page_size)
    return paginated_response([serialize_custom_request(item) for item in items], page, page_size, total)


@router.get("/{request_id}", response_model=ApiResponse[CustomRequestDetail])
def get_custom_request(request_id: int, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    custom_request = require_entity(db.get(CustomRequest, request_id), "定制申请不存在")
    return success_response(serialize_custom_request(custom_request, db=db, detail=True))


@router.patch("/{request_id}/review", response_model=ApiResponse[CustomRequestDetail])
def review_custom_request(request_id: int, payload: ReviewRequest, current_admin: dict = Depends(require_admin), db: Session = Depends(get_db)):
    custom_request = require_entity(db.get(CustomRequest, request_id), "定制申请不存在")
    old_status = custom_request.status
    custom_request.status = payload.status
    custom_request.reviewer_id = current_admin["staff_user"].id
    custom_request.reviewed_at = datetime.utcnow()
    custom_request.review_remark = payload.remark
    db.add(
        CustomRequestReview(
            custom_request_id=custom_request.id,
            reviewer_id=current_admin["staff_user"].id,
            from_status=old_status,
            to_status=payload.status,
            remark=payload.remark,
        )
    )
    db.commit()
    db.refresh(custom_request)
    return success_response(serialize_custom_request(custom_request, db=db, detail=True))


def serialize_custom_request(custom_request: CustomRequest, db: Session | None = None, detail: bool = False) -> dict:
    data = {
        "id": custom_request.id,
        "request_no": custom_request.request_no,
        "user_id": custom_request.user_id,
        "slice_file_id": custom_request.slice_file_id,
        "status": custom_request.status,
        "plate_count": custom_request.plate_count,
        "use_ams": custom_request.use_ams,
        "created_at": custom_request.created_at,
    }
    if detail:
        data.update(
            {
                "requested_print_time": custom_request.requested_print_time,
                "preferred_printer_id": custom_request.preferred_printer_id,
                "preferred_printer_model": custom_request.preferred_printer_model,
                "filament_color": custom_request.filament_color,
                "filament_type": custom_request.filament_type,
                "reviewer_id": custom_request.reviewer_id,
                "reviewed_at": custom_request.reviewed_at,
                "review_remark": custom_request.review_remark,
                "files": [],
                "quotes": [],
            }
        )
        if db is not None:
            files = db.scalars(select(ModelFile).where(ModelFile.custom_request_id == custom_request.id).order_by(ModelFile.id)).all()
            quotes = db.scalars(select(Quote).where(Quote.custom_request_id == custom_request.id).order_by(Quote.created_at.desc())).all()
            data["files"] = [{"id": item.id, "file_name": item.file_name, "file_type": item.file_type, "file_size": item.file_size} for item in files]
            data["quotes"] = [
                {
                    "id": quote.id,
                    "quote_no": quote.quote_no,
                    "manual_price": to_float(quote.manual_price),
                    "estimated_price": to_float(quote.estimated_price),
                    "status": quote.status,
                    "created_at": quote.created_at,
                }
                for quote in quotes
            ]
    return data
