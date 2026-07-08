from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.security import require_admin
from app.schemas.response import ApiResponse, success_response

router = APIRouter()

ImageType = Literal["cover", "detail", "finished", "scene"]


class ProductImageUpdate(BaseModel):
    image_type: ImageType | None = None
    sort_order: int | None = None


class ProductImageItem(BaseModel):
    id: int
    product_id: int | None = None
    image_url: str | None = None
    image_type: ImageType | str | None = None
    sort_order: int = 0
    status: str | None = None


@router.patch("/{image_id}", response_model=ApiResponse[ProductImageItem])
def update_product_image(image_id: int, payload: ProductImageUpdate, _: dict = Depends(require_admin)):
    return success_response({"id": image_id, **payload.model_dump(exclude_none=True)})


@router.delete("/{image_id}", response_model=ApiResponse[ProductImageItem])
def delete_product_image(image_id: int, _: dict = Depends(require_admin)):
    return success_response({"id": image_id, "status": "deleted"})
