from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.security import require_admin
from app.schemas.response import ApiResponse, success_response

router = APIRouter()


class DashboardStats(BaseModel):
    pending_custom_reviews: int = 0
    pending_quotes: int = 0
    pending_payment_confirmations: int = 0
    pending_schedules: int = 0
    printing_tasks: int = 0
    error_printers: int = 0
    low_stock_materials: int = 0


@router.get("", response_model=ApiResponse[DashboardStats])
def dashboard(_: dict = Depends(require_admin)):
    return success_response({"pending_custom_reviews": 0, "pending_quotes": 0, "pending_payment_confirmations": 0, "pending_schedules": 0, "printing_tasks": 0, "error_printers": 0, "low_stock_materials": 0})
