from sqlalchemy.orm import Session

from app.core.errors import AppError


class ScheduleService:
    def __init__(self, db: Session):
        self.db = db

    def create_order_schedule(self, order_id: int, items: list[dict], material_locks: list[dict]) -> None:
        if not items:
            raise AppError("VALIDATION_ERROR", "排期至少需要一个明细", status_code=422)
        # TODO: transaction steps:
        # 1. lock order row and verify payment_status = confirmed.
        # 2. verify printer status and item time overlap.
        # 3. lock material rows through InventoryService.
        # 4. create production_schedule_orders and production_schedule_items.
        # 5. update order status to scheduled.
        return None
