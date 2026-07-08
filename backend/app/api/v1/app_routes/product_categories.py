from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_app_user
from app.db.models.core import ProductCategory
from app.db.session import get_db
from app.schemas.response import ApiResponse, PageResponse, paginated_response
from app.services.db_helpers import paginate

router = APIRouter()


class ProductCategoryItem(BaseModel):
    id: int | None = None
    name: str | None = None
    sort_order: int = 0
    status: str = "active"


@router.get("", response_model=ApiResponse[PageResponse[ProductCategoryItem]])
def list_product_categories(page: int = 1, page_size: int = 100, _: dict = Depends(require_app_user), db: Session = Depends(get_db)):
    stmt = select(ProductCategory).where(ProductCategory.status == "active").order_by(ProductCategory.sort_order, ProductCategory.id)
    items, page, page_size, total = paginate(db, stmt, page, page_size)
    return paginated_response(
        [{"id": item.id, "name": item.name, "sort_order": item.sort_order, "status": item.status} for item in items],
        page,
        page_size,
        total,
    )
