from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import require_admin
from app.db.models.core import CustomRequest, Material, Order, PrintTask, Printer
from app.db.session import get_db
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
def dashboard(_: dict = Depends(require_admin), db: Session = Depends(get_db)):
    return success_response(
        {
            "pending_custom_reviews": db.scalar(select(func.count()).select_from(CustomRequest).where(CustomRequest.status.in_(["submitted", "reviewing"]))) or 0,
            "pending_quotes": db.scalar(select(func.count()).select_from(CustomRequest).where(CustomRequest.status == "quote_pending")) or 0,
            "pending_payment_confirmations": db.scalar(select(func.count()).select_from(Order).where(Order.payment_status == "unconfirmed", Order.status.in_(["submitted", "quote_confirmed"]))) or 0,
            "pending_schedules": db.scalar(select(func.count()).select_from(Order).where(Order.payment_status == "confirmed", Order.status == "payment_confirmed")) or 0,
            "printing_tasks": db.scalar(select(func.count()).select_from(PrintTask).where(PrintTask.status == "printing")) or 0,
            "error_printers": db.scalar(select(func.count()).select_from(Printer).where(Printer.status == "error")) or 0,
            "low_stock_materials": db.scalar(select(func.count()).select_from(Material).where(Material.stock_weight <= Material.safe_stock_weight, Material.status == "active")) or 0,
        }
    )
