from typing import Any, Literal

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


class ProductImageUpdate(BaseModel):
    image_type: ImageType | None = None
    sort_order: int | None = None


@router.get("", response_model=ApiResponse[PageResponse[dict[str, Any]]])
def list_products(page: int = 1, page_size: int = 20, keyword: str | None = None, category_id: int | None = None, sales_status: SalesStatus | None = None, _: dict = Depends(require_admin)):
    return paginated_response([], page, page_size, 0)


@router.post("", response_model=ApiResponse[dict[str, Any]])
def create_product(payload: ProductCreate, _: dict = Depends(require_admin)):
    return success_response({"id": None, **payload.model_dump()})


@router.patch("/{product_id}", response_model=ApiResponse[dict[str, Any]])
def update_product(product_id: int, payload: ProductCreate, _: dict = Depends(require_admin)):
    return success_response({"id": product_id, **payload.model_dump()})


@router.post("/{product_id}/images", response_model=ApiResponse[dict[str, Any]])
async def upload_product_image(product_id: int, image_type: ImageType = "detail", sort_order: int = 0, file: UploadFile = File(...), _: dict = Depends(require_admin)):
    return success_response({"product_id": product_id, "file_name": file.filename, "image_type": image_type, "sort_order": sort_order})


@router.get("/{product_id}/images", response_model=ApiResponse[dict[str, Any]])
def list_product_images(product_id: int, _: dict = Depends(require_admin)):
    return success_response({"product_id": product_id, "items": []})


@router.patch("/product-images/{image_id}", response_model=ApiResponse[dict[str, Any]])
def update_product_image(image_id: int, payload: ProductImageUpdate, _: dict = Depends(require_admin)):
    return success_response({"id": image_id, **payload.model_dump(exclude_none=True)})


@router.delete("/product-images/{image_id}", response_model=ApiResponse[dict[str, Any]])
def delete_product_image(image_id: int, _: dict = Depends(require_admin)):
    return success_response({"id": image_id, "status": "deleted"})


@router.patch("/{product_id}/sales-status", response_model=ApiResponse[dict[str, Any]])
def update_sales_status(product_id: int, payload: SalesStatusUpdate, _: dict = Depends(require_admin)):
    return success_response({"id": product_id, "sales_status": payload.sales_status})


@router.get("/{product_id}/skus", response_model=ApiResponse[dict[str, Any]])
def list_skus(product_id: int, _: dict = Depends(require_admin)):
    return success_response({"product_id": product_id, "items": []})


@router.post("/{product_id}/skus", response_model=ApiResponse[dict[str, Any]])
def create_sku(product_id: int, payload: ProductSkuCreate, _: dict = Depends(require_admin)):
    return success_response({"id": None, "product_id": product_id, **payload.model_dump()})


@router.patch("/skus/{sku_id}", response_model=ApiResponse[dict[str, Any]])
def update_sku(sku_id: int, payload: ProductSkuCreate, _: dict = Depends(require_admin)):
    return success_response({"id": sku_id, **payload.model_dump()})
