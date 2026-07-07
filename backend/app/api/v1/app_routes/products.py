from fastapi import APIRouter, Depends

from app.core.security import require_app_user
from app.schemas.response import paginated_response, success_response

router = APIRouter()


@router.get("")
def list_products(page: int = 1, page_size: int = 20, _: dict = Depends(require_app_user)):
    return paginated_response([], page, page_size, 0)


@router.get("/{product_id}")
def get_product(product_id: int, _: dict = Depends(require_app_user)):
    return success_response({"id": product_id, "skus": [], "images": [], "production_mode": "make_to_order"})


@router.get("/{product_id}/images")
def list_product_images(product_id: int, _: dict = Depends(require_app_user)):
    return success_response({"product_id": product_id, "items": []})
