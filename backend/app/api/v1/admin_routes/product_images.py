from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.security import require_admin
from app.db.models.core import Product, ProductImage
from app.db.session import get_db
from app.schemas.response import ApiResponse, success_response
from app.services.db_helpers import product_image_public_url, require_entity, storage_file_exists

router = APIRouter()

ImageType = Literal["cover", "detail", "finished", "printed_sample", "scene"]


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
def update_product_image(image_id: int, payload: ProductImageUpdate, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    image = require_entity(db.get(ProductImage, image_id), "商品图片不存在")
    data = payload.model_dump(exclude_none=True)
    if "image_type" in data:
        image.image_type = "printed_sample" if data["image_type"] == "finished" else data["image_type"]
    if "sort_order" in data:
        image.sort_order = data["sort_order"]
    if image.image_type == "cover":
        product = db.get(Product, image.product_id)
        if product:
            product.cover_image_url = image.image_url
    db.commit()
    db.refresh(image)
    return success_response(serialize_image(image))


@router.delete("/{image_id}", response_model=ApiResponse[ProductImageItem])
def delete_product_image(image_id: int, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    image = require_entity(db.get(ProductImage, image_id), "商品图片不存在")
    data = serialize_image(image)
    db.delete(image)
    db.commit()
    data["status"] = "deleted"
    return success_response(data)


def serialize_image(image: ProductImage) -> dict:
    exists = storage_file_exists(image.image_url)
    return {
        "id": image.id,
        "product_id": image.product_id,
        "image_url": product_image_public_url(image.id) if exists else None,
        "image_type": image.image_type,
        "sort_order": image.sort_order,
        "status": "active" if exists else "missing",
    }
