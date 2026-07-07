from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.security import require_admin
from app.schemas.response import ApiResponse, PageResponse, paginated_response, success_response

router = APIRouter()


class ProductCategoryUpsert(BaseModel):
    name: str
    sort_order: int = 0
    status: str = "active"


class ProductCategoryItem(ProductCategoryUpsert):
    id: int | None = None


@router.get("", response_model=ApiResponse[PageResponse[ProductCategoryItem]])
def list_product_categories(page: int = 1, page_size: int = 100, status: str | None = None, _: dict = Depends(require_admin)):
    return paginated_response([], page, page_size, 0)


@router.post("", response_model=ApiResponse[ProductCategoryItem])
def create_product_category(payload: ProductCategoryUpsert, _: dict = Depends(require_admin)):
    return success_response({"id": None, **payload.model_dump()})


@router.patch("/{category_id}", response_model=ApiResponse[ProductCategoryItem])
def update_product_category(category_id: int, payload: ProductCategoryUpsert, _: dict = Depends(require_admin)):
    return success_response({"id": category_id, **payload.model_dump()})
