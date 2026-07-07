from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.security import require_app_user
from app.schemas.response import ApiResponse, PageResponse, paginated_response, success_response

router = APIRouter()

SalesStatus = Literal["draft", "on_sale", "off_sale", "sold_out", "archived"]


class ProductListItem(BaseModel):
    id: int | None = None
    category_id: int | None = None
    name: str | None = None
    cover_image_url: str | None = None
    sales_status: SalesStatus | str = "on_sale"
    production_mode: str = "make_to_order"
    base_price: float = 0
    created_at: datetime | None = None


class ProductDetail(ProductListItem):
    description: str | None = None
    supports_custom_note: bool = False
    skus: list[dict] = Field(default_factory=list)
    images: list[dict] = Field(default_factory=list)


class ProductImages(BaseModel):
    product_id: int
    items: list[dict] = Field(default_factory=list)


@router.get("", response_model=ApiResponse[PageResponse[ProductListItem]])
def list_products(page: int = 1, page_size: int = 20, keyword: str | None = None, category_id: int | None = None, sales_status: SalesStatus | None = None, _: dict = Depends(require_app_user)):
    return paginated_response([], page, page_size, 0)


@router.get("/{product_id}", response_model=ApiResponse[ProductDetail])
def get_product(product_id: int, _: dict = Depends(require_app_user)):
    return success_response({"id": product_id, "skus": [], "images": [], "production_mode": "make_to_order"})


@router.get("/{product_id}/images", response_model=ApiResponse[ProductImages])
def list_product_images(product_id: int, _: dict = Depends(require_app_user)):
    return success_response({"product_id": product_id, "items": []})
