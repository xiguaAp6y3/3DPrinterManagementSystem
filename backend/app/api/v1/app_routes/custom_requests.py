from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.security import require_app_user
from app.db.models.core import CustomRequest, ModelFile, Quote
from app.db.session import get_db
from app.schemas.response import ApiResponse, PageResponse, paginated_response, success_response
from app.services.db_helpers import next_no, paginate, require_entity, to_float

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
def list_custom_requests(page: int = 1, page_size: int = 20, status: CustomRequestStatus | None = None, keyword: str | None = None, created_from: datetime | None = None, created_to: datetime | None = None, current_user: dict = Depends(require_app_user), db: Session = Depends(get_db)):
    stmt = select(CustomRequest).where(CustomRequest.user_id == current_user["user"].id).order_by(CustomRequest.created_at.desc())
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


@router.post("", response_model=ApiResponse[CustomRequestSummary])
def create_custom_request(payload: CreateCustomRequest, idempotency_key: str = Header(alias="Idempotency-Key"), current_user: dict = Depends(require_app_user), db: Session = Depends(get_db)):
    model_file = require_entity(db.get(ModelFile, payload.slice_file_id), "切片文件不存在")
    if model_file.user_id != current_user["user"].id or model_file.deleted_at is not None:
        require_entity(None, "切片文件不存在")
    custom_request = CustomRequest(
        request_no=next_no(db, "seq_custom_request_no", "CR"),
        user_id=current_user["user"].id,
        **payload.model_dump(),
        status="submitted",
    )
    db.add(custom_request)
    db.flush()
    model_file.custom_request_id = custom_request.id
    db.commit()
    db.refresh(custom_request)
    return success_response(serialize_custom_request(custom_request))


@router.get("/{request_id}", response_model=ApiResponse[CustomRequestDetail])
def get_custom_request(request_id: int, current_user: dict = Depends(require_app_user), db: Session = Depends(get_db)):
    custom_request = require_entity(db.get(CustomRequest, request_id), "定制申请不存在")
    if custom_request.user_id != current_user["user"].id:
        require_entity(None, "定制申请不存在")
    return success_response(serialize_custom_request(custom_request, db=db, detail=True))


@router.patch("/{request_id}", response_model=ApiResponse[CustomRequestDetail])
def update_custom_request(request_id: int, payload: CreateCustomRequest, current_user: dict = Depends(require_app_user), db: Session = Depends(get_db)):
    custom_request = require_entity(db.get(CustomRequest, request_id), "定制申请不存在")
    if custom_request.user_id != current_user["user"].id:
        require_entity(None, "定制申请不存在")
    model_file = require_entity(db.get(ModelFile, payload.slice_file_id), "切片文件不存在")
    if model_file.user_id != current_user["user"].id or model_file.deleted_at is not None:
        require_entity(None, "切片文件不存在")
    for key, value in payload.model_dump().items():
        setattr(custom_request, key, value)
    if custom_request.status == "need_more_info":
        custom_request.status = "submitted"
    model_file.custom_request_id = custom_request.id
    db.commit()
    db.refresh(custom_request)
    return success_response(serialize_custom_request(custom_request, db=db, detail=True))


def serialize_custom_request(custom_request: CustomRequest, db: Session | None = None, detail: bool = False) -> dict:
    data = {
        "id": custom_request.id,
        "request_no": custom_request.request_no,
        "status": custom_request.status,
        "slice_file_id": custom_request.slice_file_id,
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
                "review_remark": custom_request.review_remark,
                "quotes": [],
            }
        )
        if db is not None:
            quotes = db.scalars(select(Quote).where(Quote.custom_request_id == custom_request.id).order_by(Quote.created_at.desc())).all()
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
