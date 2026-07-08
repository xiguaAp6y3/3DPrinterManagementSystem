from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db.models.core import Product, ProductImage
from app.db.session import get_db
from app.services.db_helpers import require_entity, resolve_storage_path

router = APIRouter()


@router.get("/{image_id}")
def get_public_product_image(image_id: int, db: Session = Depends(get_db)):
    image = require_entity(db.get(ProductImage, image_id), "商品图片不存在")
    product = require_entity(db.get(Product, image.product_id), "商品不存在")
    if product.is_deleted:
        require_entity(None, "商品图片不存在")

    path = resolve_storage_path(image.image_url)
    if not path.exists() or not path.is_file():
        require_entity(None, "图片文件不存在")
    return FileResponse(path)
