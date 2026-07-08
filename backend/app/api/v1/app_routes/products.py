from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.security import require_app_user
from app.db.models.core import Product, ProductImage, ProductSku
from app.db.session import get_db
from app.schemas.response import ApiResponse, PageResponse, paginated_response, success_response
from app.services.db_helpers import paginate, product_image_public_url, require_entity, storage_file_exists, to_float

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
def list_products(page: int = 1, page_size: int = 20, keyword: str | None = None, category_id: int | None = None, sales_status: SalesStatus | None = None, _: dict = Depends(require_app_user), db: Session = Depends(get_db)):
    stmt = select(Product).where(Product.is_deleted == False).order_by(Product.sort_order, Product.id.desc())
    stmt = stmt.where(Product.sales_status == (sales_status or "on_sale"))
    if keyword:
        stmt = stmt.where(or_(Product.name.contains(keyword), Product.description.contains(keyword)))
    if category_id is not None:
        stmt = stmt.where(Product.category_id == category_id)
    items, page, page_size, total = paginate(db, stmt, page, page_size)
    return paginated_response([serialize_product(item, db) for item in items], page, page_size, total)


@router.get("/{product_id}", response_model=ApiResponse[ProductDetail])
def get_product(product_id: int, _: dict = Depends(require_app_user), db: Session = Depends(get_db)):
    product = require_entity(db.get(Product, product_id), "商品不存在")
    if product.is_deleted or product.sales_status != "on_sale":
        require_entity(None, "商品不存在")
    skus = db.scalars(select(ProductSku).where(ProductSku.product_id == product_id, ProductSku.status == "active").order_by(ProductSku.id)).all()
    images = db.scalars(select(ProductImage).where(ProductImage.product_id == product_id).order_by(ProductImage.sort_order, ProductImage.id)).all()
    data = serialize_product(product, db)
    data["description"] = product.description
    data["supports_custom_note"] = product.supports_custom_note
    data["skus"] = [serialize_sku(item) for item in skus]
    data["images"] = [serialize_image(item) for item in images if storage_file_exists(item.image_url)]
    return success_response(data)


@router.get("/{product_id}/images", response_model=ApiResponse[ProductImages])
def list_product_images(product_id: int, _: dict = Depends(require_app_user), db: Session = Depends(get_db)):
    product = require_entity(db.get(Product, product_id), "商品不存在")
    if product.is_deleted or product.sales_status != "on_sale":
        require_entity(None, "商品不存在")
    images = db.scalars(select(ProductImage).where(ProductImage.product_id == product_id).order_by(ProductImage.sort_order, ProductImage.id)).all()
    return success_response({"product_id": product_id, "items": [serialize_image(item) for item in images if storage_file_exists(item.image_url)]})


def serialize_product(product: Product, db: Session | None = None) -> dict:
    return {
        "id": product.id,
        "category_id": product.category_id,
        "name": product.name,
        "cover_image_url": product_image_public_url(find_cover_image_id(db, product) if db else None),
        "sales_status": product.sales_status,
        "production_mode": product.production_mode,
        "base_price": to_float(product.base_price) or 0,
        "created_at": product.created_at,
    }


def serialize_sku(sku: ProductSku) -> dict:
    return {
        "id": sku.id,
        "product_id": sku.product_id,
        "material_id": sku.material_id,
        "color": sku.color,
        "size_label": sku.size_label,
        "precision_level": sku.precision_level,
        "price": to_float(sku.price) or 0,
        "min_quantity": sku.min_quantity,
        "max_quantity": sku.max_quantity,
        "status": sku.status,
    }


def serialize_image(image: ProductImage) -> dict:
    return {
        "id": image.id,
        "product_id": image.product_id,
        "image_url": product_image_public_url(image.id),
        "image_type": image.image_type,
        "sort_order": image.sort_order,
        "created_at": image.created_at,
    }


def find_cover_image_id(db: Session | None, product: Product) -> int | None:
    if db is None:
        return None
    cover = db.scalar(
        select(ProductImage)
        .where(ProductImage.product_id == product.id, ProductImage.image_type == "cover")
        .order_by(ProductImage.sort_order, ProductImage.id)
    )
    if cover and storage_file_exists(cover.image_url):
        return cover.id
    images = db.scalars(select(ProductImage).where(ProductImage.product_id == product.id).order_by(ProductImage.sort_order, ProductImage.id)).all()
    for image in images:
        if storage_file_exists(image.image_url):
            return image.id
    return None
