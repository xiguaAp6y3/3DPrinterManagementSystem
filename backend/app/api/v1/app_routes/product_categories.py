from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.security import require_app_user
from app.schemas.response import ApiResponse, PageResponse, paginated_response

router = APIRouter()


class ProductCategoryItem(BaseModel):
    id: int | None = None
    name: str | None = None
    sort_order: int = 0
    status: str = "active"


@router.get("", response_model=ApiResponse[PageResponse[ProductCategoryItem]])
def list_product_categories(page: int = 1, page_size: int = 100, _: dict = Depends(require_app_user)):
    return paginated_response([], page, page_size, 0)
