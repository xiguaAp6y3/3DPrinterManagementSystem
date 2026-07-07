from typing import Any

from fastapi import APIRouter, Depends

from app.core.security import require_admin
from app.schemas.response import ApiResponse, success_response

router = APIRouter()


@router.get("", response_model=ApiResponse[dict[str, Any]])
def dashboard(_: dict = Depends(require_admin)):
    return success_response({"pending_custom_reviews": 0, "pending_quotes": 0, "pending_payment_confirmations": 0, "pending_schedules": 0, "printing_tasks": 0, "error_printers": 0, "low_stock_materials": 0})
