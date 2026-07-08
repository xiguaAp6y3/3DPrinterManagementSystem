from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_admin
from app.db.models.core import ProductCategory
from app.db.session import get_db
from app.schemas.response import ApiResponse, PageResponse, paginated_response, success_response
from app.services.db_helpers import paginate, require_entity

router = APIRouter()


class ProductCategoryUpsert(BaseModel):
    name: str
    sort_order: int = 0
    status: str = "active"


class ProductCategoryItem(ProductCategoryUpsert):
    id: int | None = None


@router.get("", response_model=ApiResponse[PageResponse[ProductCategoryItem]])
def list_product_categories(page: int = 1, page_size: int = 100, status: str | None = None, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    stmt = select(ProductCategory).order_by(ProductCategory.sort_order, ProductCategory.id)
    if status:
        stmt = stmt.where(ProductCategory.status == status)
    items, page, page_size, total = paginate(db, stmt, page, page_size)
    return paginated_response([serialize_category(item) for item in items], page, page_size, total)


@router.post("", response_model=ApiResponse[ProductCategoryItem])
def create_product_category(payload: ProductCategoryUpsert, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    category = ProductCategory(**payload.model_dump())
    db.add(category)
    db.commit()
    db.refresh(category)
    return success_response(serialize_category(category))


@router.patch("/{category_id}", response_model=ApiResponse[ProductCategoryItem])
def update_product_category(category_id: int, payload: ProductCategoryUpsert, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    category = require_entity(db.get(ProductCategory, category_id), "商品分类不存在")
    for key, value in payload.model_dump().items():
        setattr(category, key, value)
    db.commit()
    db.refresh(category)
    return success_response(serialize_category(category))


def serialize_category(category: ProductCategory) -> dict:
    return {
        "id": category.id,
        "name": category.name,
        "sort_order": category.sort_order,
        "status": category.status,
    }
