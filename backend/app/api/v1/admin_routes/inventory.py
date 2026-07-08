from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field

from app.core.security import require_admin
from app.schemas.response import ApiResponse, PageResponse, paginated_response, success_response

router = APIRouter()

MaterialChangeType = Literal["inbound", "adjustment", "consume", "release", "loss"]
LockStatus = Literal["locked", "released", "consumed", "expired"]


class MaterialCreate(BaseModel):
    name: str
    material_type: str
    brand: str | None = None
    color: str | None = None
    diameter: float | None = None
    stock_weight: float = Field(default=0, ge=0)
    safe_stock_weight: float = Field(default=0, ge=0)
    unit_cost: float | None = None


class MaterialUpdate(BaseModel):
    name: str | None = None
    material_type: str | None = None
    brand: str | None = None
    color: str | None = None
    diameter: float | None = None
    safe_stock_weight: float | None = Field(default=None, ge=0)
    unit_cost: float | None = None
    status: str | None = None


class MaterialStockLogCreate(BaseModel):
    change_type: MaterialChangeType
    change_weight: float
    remark: str | None = None


class MaterialLossCreate(BaseModel):
    weight: float = Field(gt=0)
    related_order_id: int | None = None
    related_task_id: int | None = None
    remark: str | None = None


class MaterialInfo(BaseModel):
    id: int | None = None
    name: str | None = None
    material_type: str | None = None
    brand: str | None = None
    color: str | None = None
    diameter: float | None = None
    stock_weight: float = 0
    reserved_weight: float = 0
    safe_stock_weight: float = 0
    unit_cost: float | None = None
    status: str = "active"


class InventoryOverview(BaseModel):
    low_stock_materials: int = 0
    locked_materials: int = 0
    material_sku_count: int = 0
    finished_goods_sku_count: int = 0
    in_progress_quantity: int = 0


class InventoryLockInfo(BaseModel):
    id: int | None = None
    lock_type: str | None = None
    order_id: int | None = None
    print_task_id: int | None = None
    material_id: int | None = None
    quantity: int | None = None
    weight: float | None = None
    status: LockStatus | str = "locked"


class MaterialStockLogItem(BaseModel):
    id: int | None = None
    material_id: int
    change_type: MaterialChangeType | str
    change_weight: float
    before_weight: float | None = None
    after_weight: float | None = None
    related_order_id: int | None = None
    related_task_id: int | None = None
    remark: str | None = None
    created_by: int | None = None
    created_at: datetime | None = None


class FinishedGoodsInventoryItem(BaseModel):
    id: int | None = None
    product_id: int | None = None
    sku_id: int | None = None
    order_id: int | None = None
    available_quantity: int = 0
    reserved_quantity: int = 0
    in_progress_quantity: int = 0
    warehouse_location: str | None = None
    updated_at: datetime | None = None


@router.get("/overview", response_model=ApiResponse[InventoryOverview])
def overview(_: dict = Depends(require_admin)):
    return success_response({"low_stock_materials": 0, "locked_materials": 0, "material_sku_count": 0, "finished_goods_sku_count": 0, "in_progress_quantity": 0})


@router.get("/materials", response_model=ApiResponse[PageResponse[MaterialInfo]])
def list_materials(page: int = 1, page_size: int = 20, keyword: str | None = None, material_type: str | None = None, color: str | None = None, status: str | None = None, _: dict = Depends(require_admin)):
    return paginated_response([], page, page_size, 0)


@router.post("/materials", response_model=ApiResponse[MaterialInfo])
def create_material(payload: MaterialCreate, _: dict = Depends(require_admin)):
    return success_response({"id": None, **payload.model_dump(), "reserved_weight": 0, "status": "active"})


@router.get("/materials/{material_id}", response_model=ApiResponse[MaterialInfo])
def get_material(material_id: int, _: dict = Depends(require_admin)):
    return success_response({"id": material_id, "stock_weight": 0, "reserved_weight": 0, "safe_stock_weight": 0, "status": "active"})


@router.patch("/materials/{material_id}", response_model=ApiResponse[MaterialInfo])
def update_material(material_id: int, payload: MaterialUpdate, _: dict = Depends(require_admin)):
    return success_response({"id": material_id, **payload.model_dump(exclude_none=True)})


@router.get("/materials/{material_id}/stock-logs", response_model=ApiResponse[PageResponse[MaterialStockLogItem]])
def list_material_stock_logs(material_id: int, page: int = 1, page_size: int = 20, change_type: MaterialChangeType | None = None, _: dict = Depends(require_admin)):
    return paginated_response([], page, page_size, 0)


@router.post("/materials/{material_id}/stock-logs", response_model=ApiResponse[MaterialStockLogItem])
def create_stock_log(material_id: int, payload: MaterialStockLogCreate, idempotency_key: str = Header(alias="Idempotency-Key"), _: dict = Depends(require_admin)):
    return success_response({"material_id": material_id, **payload.model_dump()})


@router.post("/materials/{material_id}/loss", response_model=ApiResponse[MaterialStockLogItem])
def create_material_loss(material_id: int, payload: MaterialLossCreate, idempotency_key: str = Header(alias="Idempotency-Key"), _: dict = Depends(require_admin)):
    return success_response({"material_id": material_id, "change_type": "loss", "change_weight": -payload.weight, **payload.model_dump()})


@router.get("/locks", response_model=ApiResponse[PageResponse[InventoryLockInfo]])
def list_locks(page: int = 1, page_size: int = 20, status: LockStatus | None = None, material_id: int | None = None, order_id: int | None = None, _: dict = Depends(require_admin)):
    return paginated_response([], page, page_size, 0)


@router.post("/locks/{lock_id}/release", response_model=ApiResponse[InventoryLockInfo])
def release_lock(lock_id: int, idempotency_key: str = Header(alias="Idempotency-Key"), _: dict = Depends(require_admin)):
    return success_response({"id": lock_id, "status": "released"})


@router.post("/locks/{lock_id}/consume", response_model=ApiResponse[InventoryLockInfo])
def consume_lock(lock_id: int, idempotency_key: str = Header(alias="Idempotency-Key"), _: dict = Depends(require_admin)):
    return success_response({"id": lock_id, "status": "consumed"})


@router.get("/finished-goods", response_model=ApiResponse[PageResponse[FinishedGoodsInventoryItem]])
def list_finished_goods(page: int = 1, page_size: int = 20, _: dict = Depends(require_admin)):
    return paginated_response([], page, page_size, 0)
