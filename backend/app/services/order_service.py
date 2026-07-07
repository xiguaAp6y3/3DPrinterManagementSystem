from sqlalchemy.orm import Session


class OrderService:
    def __init__(self, db: Session):
        self.db = db

    def create_listed_product_order(self, user_id: int, items: list[dict], customer_note: str | None = None) -> dict:
        # TODO: validate SKU, calculate amount, create orders and order_items in one transaction.
        return {"order_no": "OD-PENDING", "status": "submitted", "payment_status": "unconfirmed"}

    def confirm_offline_payment(self, order_id: int, staff_user_id: int, remark: str | None = None) -> dict:
        # TODO: verify current state, update payment_status, write operation_logs.
        return {"id": order_id, "payment_status": "confirmed", "status": "payment_confirmed"}
