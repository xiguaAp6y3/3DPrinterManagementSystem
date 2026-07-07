from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.errors import AppError


class InventoryService:
    def __init__(self, db: Session):
        self.db = db

    def lock_material(self, material_id: int, weight: float, order_id: int, locked_by: int | None = None) -> None:
        row = self.db.execute(
            text(
                """
                SELECT id, stock_weight, reserved_weight
                FROM dbo.materials WITH (UPDLOCK, HOLDLOCK)
                WHERE id = :material_id
                """
            ),
            {"material_id": material_id},
        ).mappings().first()
        if row is None:
            raise AppError("RESOURCE_NOT_FOUND", "材料不存在", status_code=404)

        available = float(row["stock_weight"]) - float(row["reserved_weight"])
        if available < weight:
            raise AppError(
                "INSUFFICIENT_MATERIAL_STOCK",
                "材料库存不足",
                status_code=409,
                details={"material_id": material_id, "available": available, "required": weight},
            )

        # TODO: update reserved_weight, insert inventory_locks and material_stock_logs.
        return None
