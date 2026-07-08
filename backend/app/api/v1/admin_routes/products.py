from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel, Field

from app.core.security import require_admin
from app.schemas.response import ApiResponse, PageResponse, paginated_response, success_response

router = APIRouter()

SalesStatus = Literal["draft", "on_sale", "off_sale", "sold_out", "archived"]
SkuStatus = Literal["active", "inactive"]
ImageType = Literal["cover", "detail", "finished", "scene"]


class ProductCreate(BaseModel):
    category_id: int | None = None
    name: str
    description: str | None = None
    base_price: float = 0
    sales_status: SalesStatus = "draft"
    production_mode: str = "make_to_order"
    supports_custom_note: bool = False


class ProductUpdate(BaseModel):
    category_id: int | None = None
    name: str | None = None
    description: str | None = None
    base_price: float | None = None
    sales_status: SalesStatus | None = None
    production_mode: str | None = None
    supports_custom_note: bool | None = None


class ProductItem(BaseModel):
    id: int | None = None
    category_id: int | None = None
    name: str | None = None
    description: str | None = None
    cover_image_url: str | None = None
    sales_status: SalesStatus = "draft"
    production_mode: str = "make_to_order"
    base_price: float = 0
    supports_custom_note: bool = False
    sort_order: int = 0
    is_deleted: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SalesStatusUpdate(BaseModel):
    sales_status: SalesStatus


class ProductSkuCreate(BaseModel):
    material_id: int | None = None
    color: str | None = None
    size_label: str | None = None
    precision_level: str | None = None
    price: float = Field(ge=0)
    min_quantity: int = Field(default=1, gt=0)
    max_quantity: int | None = None
    status: SkuStatus = "active"


class ProductSkuItem(ProductSkuCreate):
    id: int | None = None
    product_id: int


class ProductImageItem(BaseModel):
    id: int | None = None
    product_id: int | None = None
    image_url: str | None = None
    file_name: str | None = None
    image_type: ImageType | str = "detail"
    sort_order: int = 0
    status: str | None = None
    created_at: datetime | None = None


class ProductImageList(BaseModel):
    product_id: int
    items: list[ProductImageItem]


class ProductSkuList(BaseModel):
    product_id: int
    items: list[ProductSkuItem]


@router.get("", response_model=ApiResponse[PageResponse[ProductItem]])
def list_products(page: int = 1, page_size: int = 20, keyword: str | None = None, category_id: int | None = None, sales_status: SalesStatus | None = None, _: dict = Depends(require_admin)):
    return paginated_response([], page, page_size, 0)


@router.post("", response_model=ApiResponse[ProductItem])
def create_product(payload: ProductCreate, _: dict = Depends(require_admin)):
    return success_response({"id": None, **payload.model_dump()})


@router.get("/{product_id}", response_model=ApiResponse[ProductItem])
def get_product(product_id: int, _: dict = Depends(require_admin)):
    return success_response({"id": product_id, "sales_status": "draft", "production_mode": "make_to_order"})


@router.patch("/{product_id}", response_model=ApiResponse[ProductItem])
def update_product(product_id: int, payload: ProductUpdate, _: dict = Depends(require_admin)):
    return success_response({"id": product_id, **payload.model_dump(exclude_none=True)})


@router.post("/{product_id}/images", response_model=ApiResponse[ProductImageItem])
async def upload_product_image(product_id: int, image_type: ImageType = "detail", sort_order: int = 0, file: UploadFile = File(...), _: dict = Depends(require_admin)):
    return success_response({"product_id": product_id, "file_name": file.filename, "image_type": image_type, "sort_order": sort_order})


@router.get("/{product_id}/images", response_model=ApiResponse[ProductImageList])
def list_product_images(product_id: int, _: dict = Depends(require_admin)):
    return success_response({"product_id": product_id, "items": []})


@router.patch("/{product_id}/sales-status", response_model=ApiResponse[ProductItem])
def update_sales_status(product_id: int, payload: SalesStatusUpdate, _: dict = Depends(require_admin)):
    return success_response({"id": product_id, "sales_status": payload.sales_status})


@router.get("/{product_id}/skus", response_model=ApiResponse[ProductSkuList])
def list_skus(product_id: int, _: dict = Depends(require_admin)):
    return success_response({"product_id": product_id, "items": []})


@router.post("/{product_id}/skus", response_model=ApiResponse[ProductSkuItem])
def create_sku(product_id: int, payload: ProductSkuCreate, _: dict = Depends(require_admin)):
    return success_response({"id": None, "product_id": product_id, **payload.model_dump()})


@router.patch("/skus/{sku_id}", response_model=ApiResponse[ProductSkuItem])
def update_sku(sku_id: int, payload: ProductSkuCreate, _: dict = Depends(require_admin)):
    return success_response({"id": sku_id, "product_id": 0, **payload.model_dump()})
