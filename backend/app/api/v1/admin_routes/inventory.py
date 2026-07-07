from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field

from app.core.errors import AppError
from app.core.security import require_admin
from app.schemas.response import paginated_response, success_response

router = APIRouter()


class MaterialCreate(BaseModel):
    name: str
    material_type: str
    brand: str | None = None
    color: str | None = None
    diameter: float | None = None
    stock_weight: float = Field(default=0, ge=0)
    safe_stock_weight: float = Field(default=0, ge=0)
    unit_cost: float | None = None


class MaterialStockLogCreate(BaseModel):
    change_type: str
    change_weight: float
    remark: str | None = None


@router.get("/overview")
def overview(_: dict = Depends(require_admin)):
    return success_response({"low_stock_materials": 0, "locked_materials": 0})


@router.get("/materials")
def list_materials(page: int = 1, page_size: int = 20, _: dict = Depends(require_admin)):
    return paginated_response([], page, page_size, 0)


@router.post("/materials")
def create_material(payload: MaterialCreate, _: dict = Depends(require_admin)):
    return success_response({"id": None, **payload.model_dump()})


@router.post("/materials/{material_id}/stock-logs")
def create_stock_log(
    material_id: int,
    payload: MaterialStockLogCreate,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    _: dict = Depends(require_admin),
):
    if not idempotency_key:
        raise AppError("IDEMPOTENCY_KEY_REQUIRED", "库存变更必须提供 Idempotency-Key")
    return success_response({"material_id": material_id, **payload.model_dump()})


@router.get("/locks")
def list_locks(page: int = 1, page_size: int = 20, _: dict = Depends(require_admin)):
    return paginated_response([], page, page_size, 0)


@router.get("/finished-goods")
def list_finished_goods(page: int = 1, page_size: int = 20, _: dict = Depends(require_admin)):
    return paginated_response([], page, page_size, 0)
