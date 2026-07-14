from sqlalchemy.orm import Session

from app.db.models.core import OrderItem, ProductSku
from app.services.db_helpers import to_float


def sku_label(sku: ProductSku | None) -> str | None:
    if sku is None:
        return None
    parts = [sku.color, sku.size_label, sku.precision_level]
    return " / ".join(str(part) for part in parts if part) or f"SKU #{sku.id}"


def serialize_order_item(db: Session, item: OrderItem) -> dict:
    sku = db.get(ProductSku, item.sku_id) if item.sku_id else None
    return {
        "id": item.id,
        "product_id": item.product_id,
        "sku_id": item.sku_id,
        "sku_label": sku_label(sku),
        "custom_request_id": item.custom_request_id,
        "item_name": item.item_name,
        "unit_price": to_float(item.unit_price) or 0,
        "quantity": item.quantity,
        "produced_quantity": item.produced_quantity,
        "inbounded_quantity": item.inbounded_quantity,
        "shipped_quantity": item.shipped_quantity,
        "subtotal": to_float(item.subtotal) or 0,
        "fulfillment_mode": item.fulfillment_mode,
    }
