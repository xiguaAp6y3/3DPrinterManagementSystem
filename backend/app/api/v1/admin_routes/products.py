from datetime import datetime
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AppError
from app.core.security import require_admin
from app.core.time import utc8_now
from app.db.models.core import Product, ProductImage, ProductSku
from app.db.session import get_db
from app.schemas.response import ApiResponse, PageResponse, paginated_response, success_response
from app.services.db_helpers import paginate, product_image_public_url, require_entity, safe_storage_name, storage_file_exists, to_float

router = APIRouter()

SalesStatus = Literal["draft", "on_sale", "off_sale", "sold_out", "archived"]
SkuStatus = Literal["active", "inactive"]
ImageType = Literal["cover", "detail", "finished", "printed_sample", "scene"]


class ProductCreate(BaseModel):
    category_id: int | None = None
    name: str
    description: str | None = None
    sales_status: SalesStatus = "draft"
    production_mode: str = "make_to_order"
    supports_custom_note: bool = False


class ProductUpdate(BaseModel):
    category_id: int | None = None
    name: str | None = None
    description: str | None = None
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
    has_active_sku: bool = False
    active_sku_count: int = 0
    total_sale_stock_quantity: int = 0
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
    sale_stock_quantity: int = Field(default=0, ge=0)
    min_quantity: int = Field(default=1, gt=0)
    max_quantity: int | None = None
    status: SkuStatus = "active"


class ProductSkuItem(ProductSkuCreate):
    id: int | None = None
    product_id: int
    fulfillment_hint: str = "make_to_order"


class ProductSkuUpdate(BaseModel):
    material_id: int | None = None
    color: str | None = None
    size_label: str | None = None
    precision_level: str | None = None
    price: float | None = Field(default=None, ge=0)
    sale_stock_quantity: int | None = Field(default=None, ge=0)
    min_quantity: int | None = Field(default=None, gt=0)
    max_quantity: int | None = None
    status: SkuStatus | None = None


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
def list_products(page: int = 1, page_size: int = 20, keyword: str | None = None, category_id: int | None = None, sales_status: SalesStatus | None = None, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    stmt = select(Product).where(Product.is_deleted == False).order_by(Product.sort_order, Product.id.desc())
    if keyword:
        stmt = stmt.where(or_(Product.name.contains(keyword), Product.description.contains(keyword)))
    if category_id is not None:
        stmt = stmt.where(Product.category_id == category_id)
    if sales_status:
        stmt = stmt.where(Product.sales_status == sales_status)
    items, page, page_size, total = paginate(db, stmt, page, page_size)
    return paginated_response([serialize_product(item, db) for item in items], page, page_size, total)


@router.post("", response_model=ApiResponse[ProductItem])
def create_product(payload: ProductCreate, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    if payload.sales_status == "on_sale":
        raise AppError("PRODUCT_HAS_NO_ACTIVE_SKU", "商品至少需要一个有效 SKU 才能上架", 409)
    product = Product(**payload.model_dump(), base_price=0)
    db.add(product)
    db.commit()
    db.refresh(product)
    return success_response(serialize_product(product, db))


@router.get("/{product_id}", response_model=ApiResponse[ProductItem])
def get_product(product_id: int, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    product = require_entity(db.get(Product, product_id), "商品不存在")
    if product.is_deleted:
        require_entity(None, "商品不存在")
    return success_response(serialize_product(product, db))


@router.patch("/{product_id}", response_model=ApiResponse[ProductItem])
def update_product(product_id: int, payload: ProductUpdate, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    product = require_entity(db.get(Product, product_id), "商品不存在")
    if payload.sales_status == "on_sale":
        require_active_sku(db, product.id)
    for key, value in payload.model_dump(exclude_none=True).items():
        setattr(product, key, value)
    db.commit()
    db.refresh(product)
    return success_response(serialize_product(product, db))


@router.post("/{product_id}/images", response_model=ApiResponse[ProductImageItem])
def upload_product_image(product_id: int, image_type: ImageType = "detail", sort_order: int = 0, file: UploadFile = File(...), _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    product = require_entity(db.get(Product, product_id), "商品不存在")
    stored_type = normalize_image_type(image_type)
    directory = settings.upload_root / "product_images" / str(product_id)
    directory.mkdir(parents=True, exist_ok=True)
    filename = f"{utc8_now():%Y%m%d%H%M%S%f}_{safe_storage_name(file.filename or 'image')}"
    storage_path = directory / filename
    content = file.file.read()
    storage_path.write_bytes(content)
    storage_key = str(storage_path.as_posix())
    image = ProductImage(product_id=product.id, image_url=storage_key, image_type=stored_type, sort_order=sort_order)
    db.add(image)
    if stored_type == "cover":
        product.cover_image_url = storage_key
    db.commit()
    db.refresh(image)
    return success_response(serialize_image(image, file_name=file.filename))


@router.get("/{product_id}/images", response_model=ApiResponse[ProductImageList])
def list_product_images(product_id: int, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    require_entity(db.get(Product, product_id), "商品不存在")
    images = db.scalars(select(ProductImage).where(ProductImage.product_id == product_id).order_by(ProductImage.sort_order, ProductImage.id)).all()
    return success_response({"product_id": product_id, "items": [serialize_image(item) for item in images]})


@router.patch("/{product_id}/sales-status", response_model=ApiResponse[ProductItem])
def update_sales_status(product_id: int, payload: SalesStatusUpdate, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    product = require_entity(db.get(Product, product_id), "商品不存在")
    if payload.sales_status == "on_sale":
        require_active_sku(db, product.id)
    product.sales_status = payload.sales_status
    db.commit()
    db.refresh(product)
    return success_response(serialize_product(product, db))


@router.get("/{product_id}/skus", response_model=ApiResponse[ProductSkuList])
def list_skus(product_id: int, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    require_entity(db.get(Product, product_id), "商品不存在")
    skus = db.scalars(select(ProductSku).where(ProductSku.product_id == product_id).order_by(ProductSku.id)).all()
    return success_response({"product_id": product_id, "items": [serialize_sku(item) for item in skus]})


@router.post("/{product_id}/skus", response_model=ApiResponse[ProductSkuItem])
def create_sku(product_id: int, payload: ProductSkuCreate, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    require_entity(db.get(Product, product_id), "商品不存在")
    sku = ProductSku(product_id=product_id, **payload.model_dump())
    db.add(sku)
    db.flush()
    sync_product_base_price(db, product_id)
    db.commit()
    db.refresh(sku)
    return success_response(serialize_sku(sku))


@router.patch("/skus/{sku_id}", response_model=ApiResponse[ProductSkuItem])
def update_sku(sku_id: int, payload: ProductSkuUpdate, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    sku = require_entity(db.get(ProductSku, sku_id), "商品 SKU 不存在")
    for key, value in payload.model_dump(exclude_none=True).items():
        setattr(sku, key, value)
    db.flush()
    sync_product_base_price(db, sku.product_id)
    product = require_entity(db.get(Product, sku.product_id), "商品不存在")
    if product.sales_status == "on_sale":
        require_active_sku(db, product.id)
    db.commit()
    db.refresh(sku)
    return success_response(serialize_sku(sku))


def normalize_image_type(image_type: str) -> str:
    return "printed_sample" if image_type == "finished" else image_type


def serialize_product(product: Product, db: Session | None = None) -> dict:
    active_sku_count = 0
    total_sale_stock_quantity = 0
    if db is not None:
        active_sku_count = db.scalar(
            select(func.count()).select_from(ProductSku).where(
                ProductSku.product_id == product.id,
                ProductSku.status == "active",
            )
        ) or 0
        total_sale_stock_quantity = db.scalar(
            select(func.coalesce(func.sum(ProductSku.sale_stock_quantity), 0)).where(
                ProductSku.product_id == product.id,
                ProductSku.status == "active",
            )
        ) or 0
    return {
        "id": product.id,
        "category_id": product.category_id,
        "name": product.name,
        "description": product.description,
        "cover_image_url": product_image_public_url(find_cover_image_id(db, product) if db else None),
        "sales_status": product.sales_status,
        "production_mode": product.production_mode,
        "base_price": to_float(product.base_price) or 0,
        "has_active_sku": active_sku_count > 0,
        "active_sku_count": active_sku_count,
        "total_sale_stock_quantity": int(total_sale_stock_quantity),
        "supports_custom_note": product.supports_custom_note,
        "sort_order": product.sort_order,
        "is_deleted": product.is_deleted,
        "created_at": product.created_at,
        "updated_at": product.updated_at,
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
        "sale_stock_quantity": sku.sale_stock_quantity,
        "fulfillment_hint": "in_stock" if sku.sale_stock_quantity > 0 else "make_to_order",
        "min_quantity": sku.min_quantity,
        "max_quantity": sku.max_quantity,
        "status": sku.status,
    }


def sync_product_base_price(db: Session, product_id: int) -> float:
    product = require_entity(db.get(Product, product_id), "商品不存在")
    minimum_price = db.scalar(
        select(func.min(ProductSku.price)).where(
            ProductSku.product_id == product_id,
            ProductSku.status == "active",
        )
    )
    product.base_price = minimum_price if minimum_price is not None else 0
    return to_float(product.base_price) or 0


def require_active_sku(db: Session, product_id: int) -> None:
    product = require_entity(db.get(Product, product_id), "商品不存在")
    if product.is_deleted:
        raise AppError("PRODUCT_DELETED", "已删除商品不能上架", 409)
    active_sku_id = db.scalar(
        select(ProductSku.id).where(
            ProductSku.product_id == product_id,
            ProductSku.status == "active",
        )
    )
    if active_sku_id is None:
        raise AppError("PRODUCT_HAS_NO_ACTIVE_SKU", "商品至少需要一个有效 SKU 才能上架", 409)


def serialize_image(image: ProductImage, file_name: str | None = None) -> dict:
    exists = storage_file_exists(image.image_url)
    return {
        "id": image.id,
        "product_id": image.product_id,
        "image_url": product_image_public_url(image.id) if exists else None,
        "file_name": file_name or Path(image.image_url).name,
        "image_type": image.image_type,
        "sort_order": image.sort_order,
        "status": "active" if exists else "missing",
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
