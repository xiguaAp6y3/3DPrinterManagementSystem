from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models.core import Order, WarehouseStockItem


def sync_order_shipping_status(db: Session, order_id: int) -> str | None:
    order = db.get(Order, order_id)
    if order is None:
        return None

    db.flush()
    total_items = db.scalar(
        select(func.count())
        .select_from(WarehouseStockItem)
        .where(WarehouseStockItem.order_id == order_id)
    ) or 0
    shipped_items = db.scalar(
        select(func.count())
        .select_from(WarehouseStockItem)
        .where(
            WarehouseStockItem.order_id == order_id,
            WarehouseStockItem.status == "shipped",
        )
    ) or 0

    if total_items and shipped_items >= total_items:
        order.status = "shipped"
    elif shipped_items > 0:
        order.status = "partially_shipped"

    return order.status
