from sqlalchemy import BigInteger, Boolean, DateTime, FetchedValue, ForeignKey, Index, Integer, LargeBinary, Numeric, Unicode as String, UnicodeText as Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.session import Base


class TimestampMixin:
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=False), server_default=func.sysutcdatetime())
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=False),
        server_default=func.sysutcdatetime(),
        onupdate=func.sysutcdatetime(),
    )


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(30), index=True)
    nickname: Mapped[str | None] = mapped_column(String(100))
    avatar_url: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(50), default="active")
    email_verified_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=False))
    last_login_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=False))
    deleted_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=False))
    __table_args__ = (
        Index("UX_users_email_active", "email", unique=True, mssql_where=deleted_at.is_(None)),
        Index("UX_users_phone_active_not_null", "phone", unique=True, mssql_where=phone.is_not(None) & deleted_at.is_(None)),
    )


class StaffUser(Base, TimestampMixin):
    __tablename__ = "staff_users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(255), index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str | None] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(50), default="admin")
    status: Mapped[str] = mapped_column(String(50), default="active")
    last_login_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=False))
    deleted_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=False))


class AuthRefreshToken(Base):
    __tablename__ = "auth_refresh_tokens"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    subject_type: Mapped[str] = mapped_column(String(50), index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    staff_user_id: Mapped[int | None] = mapped_column(ForeignKey("staff_users.id"), index=True)
    expires_at: Mapped[DateTime] = mapped_column(DateTime(timezone=False), index=True)
    revoked_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=False))
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=False), server_default=func.sysutcdatetime())


class ProductCategory(Base, TimestampMixin):
    __tablename__ = "product_categories"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(50), default="active")


class Product(Base, TimestampMixin):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("product_categories.id"))
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    cover_image_url: Mapped[str | None] = mapped_column(String(500))
    sales_status: Mapped[str] = mapped_column(String(50), default="draft", index=True)
    production_mode: Mapped[str] = mapped_column(String(50), default="make_to_order")
    base_price: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    supports_custom_note: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    row_version: Mapped[bytes | None] = mapped_column(LargeBinary(8), server_default=FetchedValue(), server_onupdate=FetchedValue())

    skus = relationship("ProductSku", back_populates="product")
    images = relationship("ProductImage", back_populates="product")


class ProductImage(Base):
    __tablename__ = "product_images"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    image_url: Mapped[str] = mapped_column(String(500))
    image_type: Mapped[str] = mapped_column(String(50))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=False), server_default=func.sysutcdatetime())

    product = relationship("Product", back_populates="images")


class ProductSku(Base, TimestampMixin):
    __tablename__ = "product_skus"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    material_id: Mapped[int | None] = mapped_column(ForeignKey("materials.id"))
    color: Mapped[str | None] = mapped_column(String(100))
    size_label: Mapped[str | None] = mapped_column(String(100))
    precision_level: Mapped[str | None] = mapped_column(String(100))
    price: Mapped[float] = mapped_column(Numeric(18, 2))
    min_quantity: Mapped[int] = mapped_column(Integer, default=1)
    max_quantity: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(50), default="active", index=True)

    product = relationship("Product", back_populates="skus")


class ModelFile(Base):
    __tablename__ = "model_files"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    custom_request_id: Mapped[int | None] = mapped_column(ForeignKey("custom_requests.id"))
    file_name: Mapped[str] = mapped_column(String(255))
    file_ext: Mapped[str] = mapped_column(String(50))
    file_type: Mapped[str] = mapped_column(String(50))
    file_size: Mapped[int] = mapped_column(BigInteger)
    storage_bucket: Mapped[str | None] = mapped_column(String(100))
    storage_key: Mapped[str] = mapped_column(String(500))
    sha256: Mapped[str | None] = mapped_column(String(128))
    is_slice_file: Mapped[bool] = mapped_column(Boolean, default=True)
    printer_profile_summary: Mapped[str | None] = mapped_column(String(1000))
    upload_status: Mapped[str] = mapped_column(String(50), default="stored")
    virus_scan_status: Mapped[str] = mapped_column(String(50), default="pending")
    analysis_status: Mapped[str] = mapped_column(String(50), default="pending")
    owner_type: Mapped[str] = mapped_column(String(50), default="user")
    owner_id: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=False), server_default=func.sysutcdatetime())
    deleted_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=False))


class CustomRequest(Base, TimestampMixin):
    __tablename__ = "custom_requests"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    request_no: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    slice_file_id: Mapped[int | None] = mapped_column(ForeignKey("model_files.id"))
    requested_print_time: Mapped[DateTime | None] = mapped_column(DateTime(timezone=False))
    preferred_printer_id: Mapped[int | None] = mapped_column(ForeignKey("printers.id"))
    preferred_printer_model: Mapped[str | None] = mapped_column(String(200))
    filament_color: Mapped[str | None] = mapped_column(String(100))
    filament_type: Mapped[str | None] = mapped_column(String(100))
    use_ams: Mapped[bool] = mapped_column(Boolean)
    plate_count: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(50), default="submitted", index=True)
    reviewer_id: Mapped[int | None] = mapped_column(ForeignKey("staff_users.id"))
    reviewed_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=False))
    review_remark: Mapped[str | None] = mapped_column(String(1000))
    row_version: Mapped[bytes | None] = mapped_column(LargeBinary(8), server_default=FetchedValue(), server_onupdate=FetchedValue())


class CustomRequestReview(Base):
    __tablename__ = "custom_request_reviews"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    custom_request_id: Mapped[int] = mapped_column(ForeignKey("custom_requests.id"), index=True)
    reviewer_id: Mapped[int] = mapped_column(ForeignKey("staff_users.id"))
    from_status: Mapped[str | None] = mapped_column(String(50))
    to_status: Mapped[str] = mapped_column(String(50))
    remark: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=False), server_default=func.sysutcdatetime())


class Quote(Base, TimestampMixin):
    __tablename__ = "quotes"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    quote_no: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    custom_request_id: Mapped[int | None] = mapped_column(ForeignKey("custom_requests.id"))
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"))
    estimated_price: Mapped[float | None] = mapped_column(Numeric(18, 2))
    manual_price: Mapped[float] = mapped_column(Numeric(18, 2))
    estimated_days: Mapped[int | None] = mapped_column(Integer)
    material_cost: Mapped[float | None] = mapped_column(Numeric(18, 2))
    machine_cost: Mapped[float | None] = mapped_column(Numeric(18, 2))
    labor_cost: Mapped[float | None] = mapped_column(Numeric(18, 2))
    post_processing_cost: Mapped[float | None] = mapped_column(Numeric(18, 2))
    remark: Mapped[str | None] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(50), default="draft", index=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("staff_users.id"))
    confirmed_by_user_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=False))
    row_version: Mapped[bytes | None] = mapped_column(LargeBinary(8), server_default=FetchedValue(), server_onupdate=FetchedValue())


class Order(Base, TimestampMixin):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    order_no: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    order_type: Mapped[str] = mapped_column(String(50), index=True)
    status: Mapped[str] = mapped_column(String(50), default="submitted", index=True)
    total_amount: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    payment_status: Mapped[str] = mapped_column(String(50), default="unconfirmed", index=True)
    payment_confirmed_by: Mapped[int | None] = mapped_column(ForeignKey("staff_users.id"))
    payment_confirmed_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=False))
    customer_note: Mapped[str | None] = mapped_column(String(1000))
    admin_note: Mapped[str | None] = mapped_column(String(1000))
    receiver_name: Mapped[str | None] = mapped_column(String(100))
    receiver_phone: Mapped[str | None] = mapped_column(String(50))
    receiver_address: Mapped[str | None] = mapped_column(String(1000))
    row_version: Mapped[bytes | None] = mapped_column(LargeBinary(8), server_default=FetchedValue(), server_onupdate=FetchedValue())


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"))
    sku_id: Mapped[int | None] = mapped_column(ForeignKey("product_skus.id"))
    custom_request_id: Mapped[int | None] = mapped_column(ForeignKey("custom_requests.id"))
    item_name: Mapped[str] = mapped_column(String(200))
    unit_price: Mapped[float] = mapped_column(Numeric(18, 2))
    quantity: Mapped[int] = mapped_column(Integer)
    produced_quantity: Mapped[int] = mapped_column(Integer, default=0)
    inbounded_quantity: Mapped[int] = mapped_column(Integer, default=0)
    shipped_quantity: Mapped[int] = mapped_column(Integer, default=0)
    subtotal: Mapped[float] = mapped_column(Numeric(18, 2))
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=False), server_default=func.sysutcdatetime())


class Printer(Base, TimestampMixin):
    __tablename__ = "printers"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100))
    brand: Mapped[str | None] = mapped_column(String(100))
    model: Mapped[str | None] = mapped_column(String(100))
    printer_type: Mapped[str | None] = mapped_column(String(100))
    supported_materials: Mapped[str | None] = mapped_column(String(500))
    build_volume: Mapped[str | None] = mapped_column(String(100))
    location: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(50), default="idle", index=True)
    current_task_id: Mapped[int | None] = mapped_column(BigInteger)
    supports_api: Mapped[bool] = mapped_column(Boolean, default=False)
    api_endpoint: Mapped[str | None] = mapped_column(String(500))
    last_seen_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=False))
    remark: Mapped[str | None] = mapped_column(String(1000))
    row_version: Mapped[bytes | None] = mapped_column(LargeBinary(8), server_default=FetchedValue(), server_onupdate=FetchedValue())


class PrintTask(Base, TimestampMixin):
    __tablename__ = "print_tasks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    task_no: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    order_item_id: Mapped[int | None] = mapped_column(ForeignKey("order_items.id"))
    printer_id: Mapped[int | None] = mapped_column(ForeignKey("printers.id"), index=True)
    slice_file_id: Mapped[int | None] = mapped_column(ForeignKey("model_files.id"))
    material_id: Mapped[int | None] = mapped_column(ForeignKey("materials.id"))
    status: Mapped[str] = mapped_column(String(50), default="pending", index=True)
    warehouse_status: Mapped[str] = mapped_column(String(50), default="not_required", index=True)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    plate_count: Mapped[int] = mapped_column(Integer, default=1)
    use_ams: Mapped[bool] = mapped_column(Boolean, default=False)
    estimated_minutes: Mapped[int | None] = mapped_column(Integer)
    started_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=False))
    finished_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=False))
    failure_reason: Mapped[str | None] = mapped_column(String(1000))
    row_version: Mapped[bytes | None] = mapped_column(LargeBinary(8), server_default=FetchedValue(), server_onupdate=FetchedValue())


class ProductionScheduleOrder(Base, TimestampMixin):
    __tablename__ = "production_schedule_orders"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    schedule_no: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    status: Mapped[str] = mapped_column(String(50), default="scheduled", index=True)
    planned_start_at: Mapped[DateTime] = mapped_column(DateTime(timezone=False))
    planned_end_at: Mapped[DateTime] = mapped_column(DateTime(timezone=False))
    due_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=False))
    priority: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("staff_users.id"))
    row_version: Mapped[bytes | None] = mapped_column(LargeBinary(8), server_default=FetchedValue(), server_onupdate=FetchedValue())


class ProductionScheduleItem(Base, TimestampMixin):
    __tablename__ = "production_schedule_items"
    __table_args__ = {"implicit_returning": False}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    schedule_order_id: Mapped[int] = mapped_column(ForeignKey("production_schedule_orders.id"), index=True)
    print_task_id: Mapped[int | None] = mapped_column(ForeignKey("print_tasks.id"))
    printer_id: Mapped[int] = mapped_column(ForeignKey("printers.id"), index=True)
    scheduled_start_at: Mapped[DateTime] = mapped_column(DateTime(timezone=False))
    scheduled_end_at: Mapped[DateTime] = mapped_column(DateTime(timezone=False))
    status: Mapped[str] = mapped_column(String(50), default="scheduled", index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    row_version: Mapped[bytes | None] = mapped_column(LargeBinary(8), server_default=FetchedValue(), server_onupdate=FetchedValue())


class PrinterStatusLog(Base):
    __tablename__ = "printer_status_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    printer_id: Mapped[int] = mapped_column(ForeignKey("printers.id"), index=True)
    from_status: Mapped[str | None] = mapped_column(String(50))
    to_status: Mapped[str] = mapped_column(String(50))
    progress: Mapped[float | None] = mapped_column(Numeric(5, 2))
    nozzle_temp: Mapped[float | None] = mapped_column(Numeric(8, 2))
    bed_temp: Mapped[float | None] = mapped_column(Numeric(8, 2))
    remaining_minutes: Mapped[int | None] = mapped_column(Integer)
    changed_by: Mapped[int | None] = mapped_column(ForeignKey("staff_users.id"))
    raw_payload: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=False), server_default=func.sysutcdatetime())


class Material(Base, TimestampMixin):
    __tablename__ = "materials"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100))
    material_type: Mapped[str] = mapped_column(String(100), index=True)
    brand: Mapped[str | None] = mapped_column(String(100))
    color: Mapped[str | None] = mapped_column(String(100), index=True)
    diameter: Mapped[float | None] = mapped_column(Numeric(8, 2))
    stock_weight: Mapped[float] = mapped_column(Numeric(18, 3), default=0)
    reserved_weight: Mapped[float] = mapped_column(Numeric(18, 3), default=0)
    safe_stock_weight: Mapped[float] = mapped_column(Numeric(18, 3), default=0)
    unit_cost: Mapped[float | None] = mapped_column(Numeric(18, 2))
    status: Mapped[str] = mapped_column(String(50), default="active", index=True)
    row_version: Mapped[bytes | None] = mapped_column(LargeBinary(8), server_default=FetchedValue(), server_onupdate=FetchedValue())


class FinishedGoodsInventory(Base):
    __tablename__ = "finished_goods_inventory"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"))
    sku_id: Mapped[int | None] = mapped_column(ForeignKey("product_skus.id"))
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"))
    available_quantity: Mapped[int] = mapped_column(Integer, default=0)
    reserved_quantity: Mapped[int] = mapped_column(Integer, default=0)
    in_progress_quantity: Mapped[int] = mapped_column(Integer, default=0)
    warehouse_location: Mapped[str | None] = mapped_column(String(200))
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=False), server_default=func.sysutcdatetime())


class Warehouse(Base, TimestampMixin):
    __tablename__ = "warehouses"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    warehouse_code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(50), default="active", index=True)
    remark: Mapped[str | None] = mapped_column(String(1000))


class WarehouseLocation(Base, TimestampMixin):
    __tablename__ = "warehouse_locations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"), index=True)
    location_code: Mapped[str] = mapped_column(String(50), index=True)
    name: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(50), default="active", index=True)
    remark: Mapped[str | None] = mapped_column(String(1000))


class WarehouseStockItem(Base, TimestampMixin):
    __tablename__ = "warehouse_stock_items"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    stock_item_no: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"), index=True)
    location_id: Mapped[int | None] = mapped_column(ForeignKey("warehouse_locations.id"), index=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    order_item_id: Mapped[int | None] = mapped_column(ForeignKey("order_items.id"))
    print_task_id: Mapped[int | None] = mapped_column(ForeignKey("print_tasks.id"), index=True)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"))
    sku_id: Mapped[int | None] = mapped_column(ForeignKey("product_skus.id"))
    custom_request_id: Mapped[int | None] = mapped_column(ForeignKey("custom_requests.id"))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(50), default="available", index=True)
    inbounded_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=False))
    outbounded_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=False))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("staff_users.id"))
    row_version: Mapped[bytes | None] = mapped_column(LargeBinary(8), server_default=FetchedValue(), server_onupdate=FetchedValue())


class WarehouseInboundRecord(Base):
    __tablename__ = "warehouse_inbound_records"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    inbound_no: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    inbound_type: Mapped[str] = mapped_column(String(50), default="production_completed")
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"), index=True)
    location_id: Mapped[int | None] = mapped_column(ForeignKey("warehouse_locations.id"))
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    order_item_id: Mapped[int | None] = mapped_column(ForeignKey("order_items.id"))
    print_task_id: Mapped[int | None] = mapped_column(ForeignKey("print_tasks.id"), index=True)
    stock_item_id: Mapped[int | None] = mapped_column(ForeignKey("warehouse_stock_items.id"))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    operator_id: Mapped[int | None] = mapped_column(ForeignKey("staff_users.id"))
    remark: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=False), server_default=func.sysutcdatetime())


class Shipment(Base, TimestampMixin):
    __tablename__ = "shipments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    shipment_no: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    status: Mapped[str] = mapped_column(String(50), default="ready", index=True)
    receiver_name: Mapped[str | None] = mapped_column(String(100))
    receiver_phone: Mapped[str | None] = mapped_column(String(50))
    receiver_address: Mapped[str | None] = mapped_column(String(1000))
    remark: Mapped[str | None] = mapped_column(String(1000))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("staff_users.id"))


class ShipmentPackage(Base, TimestampMixin):
    __tablename__ = "shipment_packages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    shipment_id: Mapped[int] = mapped_column(ForeignKey("shipments.id"), index=True)
    package_no: Mapped[str] = mapped_column(String(50), index=True)
    carrier_code: Mapped[str | None] = mapped_column(String(50))
    carrier_name: Mapped[str | None] = mapped_column(String(100))
    tracking_no: Mapped[str] = mapped_column(String(100), index=True)
    status: Mapped[str] = mapped_column(String(50), default="ready", index=True)


class ShipmentItem(Base):
    __tablename__ = "shipment_items"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    shipment_id: Mapped[int] = mapped_column(ForeignKey("shipments.id"), index=True)
    package_id: Mapped[int | None] = mapped_column(ForeignKey("shipment_packages.id"))
    stock_item_id: Mapped[int] = mapped_column(ForeignKey("warehouse_stock_items.id"), index=True)
    order_item_id: Mapped[int | None] = mapped_column(ForeignKey("order_items.id"))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=False), server_default=func.sysutcdatetime())


class WarehouseOutboundRecord(Base, TimestampMixin):
    __tablename__ = "warehouse_outbound_records"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    outbound_no: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(50), default="draft", index=True)
    outbound_type: Mapped[str] = mapped_column(String(50), default="shipment")
    operator_id: Mapped[int | None] = mapped_column(ForeignKey("staff_users.id"))
    confirmed_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=False))
    remark: Mapped[str | None] = mapped_column(String(1000))


class WarehouseOutboundItem(Base):
    __tablename__ = "warehouse_outbound_items"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    outbound_id: Mapped[int] = mapped_column(ForeignKey("warehouse_outbound_records.id"), index=True)
    shipment_id: Mapped[int] = mapped_column(ForeignKey("shipments.id"), index=True)
    package_id: Mapped[int | None] = mapped_column(ForeignKey("shipment_packages.id"))
    stock_item_id: Mapped[int] = mapped_column(ForeignKey("warehouse_stock_items.id"), index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=False), server_default=func.sysutcdatetime())


class InventoryLock(Base):
    __tablename__ = "inventory_locks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    lock_type: Mapped[str] = mapped_column(String(50))
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"), index=True)
    print_task_id: Mapped[int | None] = mapped_column(ForeignKey("print_tasks.id"))
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"))
    sku_id: Mapped[int | None] = mapped_column(ForeignKey("product_skus.id"))
    material_id: Mapped[int | None] = mapped_column(ForeignKey("materials.id"), index=True)
    quantity: Mapped[int | None] = mapped_column(Integer)
    weight: Mapped[float | None] = mapped_column(Numeric(18, 3))
    status: Mapped[str] = mapped_column(String(50), default="locked", index=True)
    locked_by: Mapped[int | None] = mapped_column(ForeignKey("staff_users.id"))
    expires_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=False))
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=False), server_default=func.sysutcdatetime())
    released_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=False))
    row_version: Mapped[bytes | None] = mapped_column(LargeBinary(8), server_default=FetchedValue(), server_onupdate=FetchedValue())


class MaterialStockLog(Base):
    __tablename__ = "material_stock_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id"), index=True)
    change_type: Mapped[str] = mapped_column(String(50))
    change_weight: Mapped[float] = mapped_column(Numeric(18, 3))
    before_weight: Mapped[float | None] = mapped_column(Numeric(18, 3))
    after_weight: Mapped[float | None] = mapped_column(Numeric(18, 3))
    related_order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"))
    related_task_id: Mapped[int | None] = mapped_column(ForeignKey("print_tasks.id"))
    remark: Mapped[str | None] = mapped_column(String(1000))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("staff_users.id"))
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=False), server_default=func.sysutcdatetime())


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    scope: Mapped[str] = mapped_column(String(150), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(100), index=True)
    request_hash: Mapped[str] = mapped_column(String(128))
    response_body: Mapped[str | None] = mapped_column(Text)
    status_code: Mapped[int | None] = mapped_column(Integer)
    resource_type: Mapped[str | None] = mapped_column(String(100))
    resource_id: Mapped[int | None] = mapped_column(BigInteger)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_by_staff_id: Mapped[int | None] = mapped_column(ForeignKey("staff_users.id"))
    expires_at: Mapped[DateTime] = mapped_column(DateTime(timezone=False))
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=False), server_default=func.sysutcdatetime())


class OperationLog(Base):
    __tablename__ = "operation_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    operator_id: Mapped[int | None] = mapped_column(ForeignKey("staff_users.id"))
    operation_type: Mapped[str] = mapped_column(String(100))
    target_table: Mapped[str | None] = mapped_column(String(100))
    target_id: Mapped[int | None] = mapped_column(BigInteger)
    before_data: Mapped[str | None] = mapped_column(Text)
    after_data: Mapped[str | None] = mapped_column(Text)
    remark: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=False), server_default=func.sysutcdatetime())


class UserCoupon(Base, TimestampMixin):
    __tablename__ = "user_coupons"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    coupon_no: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    discount_type: Mapped[str] = mapped_column(String(50), default="percentage")
    discount_value: Mapped[float] = mapped_column(Numeric(18, 2))
    min_spend: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    scope_type: Mapped[str] = mapped_column(String(50), default="all")
    source: Mapped[str] = mapped_column(String(50), default="lottery")
    status: Mapped[str] = mapped_column(String(50), default="unused", index=True)
    valid_from: Mapped[DateTime] = mapped_column(DateTime(timezone=False))
    valid_until: Mapped[DateTime] = mapped_column(DateTime(timezone=False))
    used_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=False))
    used_order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"))
    discount_amount: Mapped[float | None] = mapped_column(Numeric(18, 2))
    revoked_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=False))
    revoked_by: Mapped[int | None] = mapped_column(ForeignKey("staff_users.id"))
    revoke_reason: Mapped[str | None] = mapped_column(String(500))
    row_version: Mapped[bytes | None] = mapped_column(LargeBinary(8), server_default=FetchedValue(), server_onupdate=FetchedValue())


class LotteryRecord(Base):
    __tablename__ = "lottery_records"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    record_no: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    is_win: Mapped[bool] = mapped_column(Boolean, default=True)
    prize_name: Mapped[str] = mapped_column(String(100))
    discount_value: Mapped[float | None] = mapped_column(Numeric(18, 2))
    won_coupon_id: Mapped[int | None] = mapped_column(ForeignKey("user_coupons.id"))
    idempotency_key: Mapped[str] = mapped_column(String(100))
    client_ip: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=False), server_default=func.sysutcdatetime())
