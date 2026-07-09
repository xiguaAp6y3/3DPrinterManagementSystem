-- Encoding policy:
-- 1. Business text columns use NVARCHAR/NCHAR to store Chinese safely as Unicode.
-- 2. String literals containing Chinese must use N'' prefix, for example N'默认分类'.
-- 3. Do not require SQL Server UTF-8 collation; older SQL Server versions may not support *_UTF8 collations.

CREATE SEQUENCE dbo.seq_order_no AS BIGINT START WITH 1 INCREMENT BY 1;
CREATE SEQUENCE dbo.seq_custom_request_no AS BIGINT START WITH 1 INCREMENT BY 1;
CREATE SEQUENCE dbo.seq_quote_no AS BIGINT START WITH 1 INCREMENT BY 1;
CREATE SEQUENCE dbo.seq_print_task_no AS BIGINT START WITH 1 INCREMENT BY 1;
CREATE SEQUENCE dbo.seq_schedule_no AS BIGINT START WITH 1 INCREMENT BY 1;
CREATE SEQUENCE dbo.seq_stock_item_no AS BIGINT START WITH 1 INCREMENT BY 1;
CREATE SEQUENCE dbo.seq_inbound_no AS BIGINT START WITH 1 INCREMENT BY 1;
CREATE SEQUENCE dbo.seq_shipment_no AS BIGINT START WITH 1 INCREMENT BY 1;
CREATE SEQUENCE dbo.seq_outbound_no AS BIGINT START WITH 1 INCREMENT BY 1;
CREATE SEQUENCE dbo.seq_coupon_no AS BIGINT START WITH 1 INCREMENT BY 1;
CREATE SEQUENCE dbo.seq_lottery_record_no AS BIGINT START WITH 1 INCREMENT BY 1;
CREATE SEQUENCE dbo.seq_grant_batch_no AS BIGINT START WITH 1 INCREMENT BY 1;
GO

CREATE TABLE dbo.users (
    id BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    email NVARCHAR(255) NOT NULL,
    password_hash NVARCHAR(255) NOT NULL,
    phone NVARCHAR(30) NULL,
    nickname NVARCHAR(100) NULL,
    avatar_url NVARCHAR(500) NULL,
    status NVARCHAR(50) NOT NULL CONSTRAINT DF_users_status DEFAULT N'active',
    email_verified_at DATETIME2(3) NULL,
    last_login_at DATETIME2(3) NULL,
    deleted_at DATETIME2(3) NULL,
    created_at DATETIME2(3) NOT NULL CONSTRAINT DF_users_created_at DEFAULT SYSUTCDATETIME(),
    updated_at DATETIME2(3) NOT NULL CONSTRAINT DF_users_updated_at DEFAULT SYSUTCDATETIME(),
    CONSTRAINT CK_users_status CHECK (status IN (N'active', N'disabled', N'deleted'))
);

CREATE TABLE dbo.staff_users (
    id BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    username NVARCHAR(100) NOT NULL,
    email NVARCHAR(255) NULL,
    password_hash NVARCHAR(255) NOT NULL,
    display_name NVARCHAR(100) NULL,
    role NVARCHAR(50) NOT NULL CONSTRAINT DF_staff_users_role DEFAULT N'admin',
    status NVARCHAR(50) NOT NULL CONSTRAINT DF_staff_users_status DEFAULT N'active',
    last_login_at DATETIME2(3) NULL,
    deleted_at DATETIME2(3) NULL,
    created_at DATETIME2(3) NOT NULL CONSTRAINT DF_staff_users_created_at DEFAULT SYSUTCDATETIME(),
    updated_at DATETIME2(3) NOT NULL CONSTRAINT DF_staff_users_updated_at DEFAULT SYSUTCDATETIME(),
    CONSTRAINT UQ_staff_users_username UNIQUE (username),
    CONSTRAINT CK_staff_users_role CHECK (role IN (N'super_admin', N'admin', N'production_manager', N'warehouse_manager', N'customer_service')),
    CONSTRAINT CK_staff_users_status CHECK (status IN (N'active', N'disabled', N'deleted'))
);

CREATE TABLE dbo.auth_refresh_tokens (
    id BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    token_hash NVARCHAR(128) NOT NULL,
    subject_type NVARCHAR(50) NOT NULL,
    user_id BIGINT NULL,
    staff_user_id BIGINT NULL,
    expires_at DATETIME2(3) NOT NULL,
    revoked_at DATETIME2(3) NULL,
    created_at DATETIME2(3) NOT NULL CONSTRAINT DF_auth_refresh_tokens_created_at DEFAULT SYSUTCDATETIME(),
    CONSTRAINT UQ_auth_refresh_tokens_token_hash UNIQUE (token_hash),
    CONSTRAINT FK_auth_refresh_tokens_user FOREIGN KEY (user_id) REFERENCES dbo.users(id),
    CONSTRAINT FK_auth_refresh_tokens_staff FOREIGN KEY (staff_user_id) REFERENCES dbo.staff_users(id),
    CONSTRAINT CK_auth_refresh_tokens_subject_type CHECK (subject_type IN (N'app', N'admin')),
    CONSTRAINT CK_auth_refresh_tokens_subject CHECK (
        (subject_type = N'app' AND user_id IS NOT NULL AND staff_user_id IS NULL)
        OR (subject_type = N'admin' AND staff_user_id IS NOT NULL AND user_id IS NULL)
    )
);

CREATE TABLE dbo.product_categories (
    id BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    name NVARCHAR(100) NOT NULL,
    sort_order INT NOT NULL CONSTRAINT DF_product_categories_sort_order DEFAULT 0,
    status NVARCHAR(50) NOT NULL CONSTRAINT DF_product_categories_status DEFAULT N'active',
    created_at DATETIME2(3) NOT NULL CONSTRAINT DF_product_categories_created_at DEFAULT SYSUTCDATETIME(),
    updated_at DATETIME2(3) NOT NULL CONSTRAINT DF_product_categories_updated_at DEFAULT SYSUTCDATETIME()
);

CREATE TABLE dbo.materials (
    id BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    name NVARCHAR(100) NOT NULL,
    material_type NVARCHAR(100) NOT NULL,
    brand NVARCHAR(100) NULL,
    color NVARCHAR(100) NULL,
    diameter DECIMAL(8,2) NULL,
    stock_weight DECIMAL(18,3) NOT NULL CONSTRAINT DF_materials_stock_weight DEFAULT 0,
    reserved_weight DECIMAL(18,3) NOT NULL CONSTRAINT DF_materials_reserved_weight DEFAULT 0,
    safe_stock_weight DECIMAL(18,3) NOT NULL CONSTRAINT DF_materials_safe_stock_weight DEFAULT 0,
    unit_cost DECIMAL(18,2) NULL,
    status NVARCHAR(50) NOT NULL CONSTRAINT DF_materials_status DEFAULT N'active',
    created_at DATETIME2(3) NOT NULL CONSTRAINT DF_materials_created_at DEFAULT SYSUTCDATETIME(),
    updated_at DATETIME2(3) NOT NULL CONSTRAINT DF_materials_updated_at DEFAULT SYSUTCDATETIME(),
    row_version ROWVERSION NOT NULL,
    CONSTRAINT CK_materials_weight CHECK (stock_weight >= 0 AND reserved_weight >= 0 AND reserved_weight <= stock_weight)
);

CREATE TABLE dbo.products (
    id BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    category_id BIGINT NULL,
    name NVARCHAR(200) NOT NULL,
    description NVARCHAR(MAX) NULL,
    cover_image_url NVARCHAR(500) NULL,
    sales_status NVARCHAR(50) NOT NULL CONSTRAINT DF_products_sales_status DEFAULT N'draft',
    production_mode NVARCHAR(50) NOT NULL CONSTRAINT DF_products_production_mode DEFAULT N'make_to_order',
    base_price DECIMAL(18,2) NOT NULL CONSTRAINT DF_products_base_price DEFAULT 0,
    supports_custom_note BIT NOT NULL CONSTRAINT DF_products_supports_custom_note DEFAULT 0,
    sort_order INT NOT NULL CONSTRAINT DF_products_sort_order DEFAULT 0,
    is_deleted BIT NOT NULL CONSTRAINT DF_products_is_deleted DEFAULT 0,
    created_at DATETIME2(3) NOT NULL CONSTRAINT DF_products_created_at DEFAULT SYSUTCDATETIME(),
    updated_at DATETIME2(3) NOT NULL CONSTRAINT DF_products_updated_at DEFAULT SYSUTCDATETIME(),
    row_version ROWVERSION NOT NULL,
    CONSTRAINT FK_products_category FOREIGN KEY (category_id) REFERENCES dbo.product_categories(id),
    CONSTRAINT CK_products_sales_status CHECK (sales_status IN (N'draft', N'on_sale', N'off_sale', N'sold_out', N'archived')),
    CONSTRAINT CK_products_production_mode CHECK (production_mode IN (N'make_to_order'))
);

CREATE TABLE dbo.product_images (
    id BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    product_id BIGINT NOT NULL,
    image_url NVARCHAR(500) NOT NULL,
    image_type NVARCHAR(50) NOT NULL,
    sort_order INT NOT NULL CONSTRAINT DF_product_images_sort_order DEFAULT 0,
    created_at DATETIME2(3) NOT NULL CONSTRAINT DF_product_images_created_at DEFAULT SYSUTCDATETIME(),
    CONSTRAINT FK_product_images_product FOREIGN KEY (product_id) REFERENCES dbo.products(id),
    CONSTRAINT CK_product_images_type CHECK (image_type IN (N'cover', N'detail', N'printed_sample', N'scene'))
);

CREATE TABLE dbo.product_skus (
    id BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    product_id BIGINT NOT NULL,
    material_id BIGINT NULL,
    color NVARCHAR(100) NULL,
    size_label NVARCHAR(100) NULL,
    precision_level NVARCHAR(100) NULL,
    price DECIMAL(18,2) NOT NULL,
    min_quantity INT NOT NULL CONSTRAINT DF_product_skus_min_quantity DEFAULT 1,
    max_quantity INT NULL,
    status NVARCHAR(50) NOT NULL CONSTRAINT DF_product_skus_status DEFAULT N'active',
    created_at DATETIME2(3) NOT NULL CONSTRAINT DF_product_skus_created_at DEFAULT SYSUTCDATETIME(),
    updated_at DATETIME2(3) NOT NULL CONSTRAINT DF_product_skus_updated_at DEFAULT SYSUTCDATETIME(),
    CONSTRAINT FK_product_skus_product FOREIGN KEY (product_id) REFERENCES dbo.products(id),
    CONSTRAINT FK_product_skus_material FOREIGN KEY (material_id) REFERENCES dbo.materials(id),
    CONSTRAINT CK_product_skus_quantity CHECK (min_quantity > 0 AND (max_quantity IS NULL OR max_quantity >= min_quantity)),
    CONSTRAINT CK_product_skus_price CHECK (price >= 0)
);

CREATE TABLE dbo.printers (
    id BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    name NVARCHAR(100) NOT NULL,
    brand NVARCHAR(100) NULL,
    model NVARCHAR(100) NULL,
    printer_type NVARCHAR(100) NULL,
    supported_materials NVARCHAR(500) NULL,
    build_volume NVARCHAR(100) NULL,
    location NVARCHAR(200) NULL,
    status NVARCHAR(50) NOT NULL CONSTRAINT DF_printers_status DEFAULT N'idle',
    current_task_id BIGINT NULL,
    supports_api BIT NOT NULL CONSTRAINT DF_printers_supports_api DEFAULT 0,
    api_endpoint NVARCHAR(500) NULL,
    last_seen_at DATETIME2(3) NULL,
    remark NVARCHAR(1000) NULL,
    created_at DATETIME2(3) NOT NULL CONSTRAINT DF_printers_created_at DEFAULT SYSUTCDATETIME(),
    updated_at DATETIME2(3) NOT NULL CONSTRAINT DF_printers_updated_at DEFAULT SYSUTCDATETIME(),
    row_version ROWVERSION NOT NULL,
    CONSTRAINT CK_printers_status CHECK (status IN (N'idle', N'printing', N'paused', N'completed', N'error', N'offline', N'maintenance'))
);

CREATE TABLE dbo.model_files (
    id BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    custom_request_id BIGINT NULL,
    file_name NVARCHAR(255) NOT NULL,
    file_ext NVARCHAR(50) NOT NULL,
    file_type NVARCHAR(50) NOT NULL,
    file_size BIGINT NOT NULL,
    storage_bucket NVARCHAR(100) NULL,
    storage_key NVARCHAR(500) NOT NULL,
    sha256 NVARCHAR(128) NULL,
    is_slice_file BIT NOT NULL CONSTRAINT DF_model_files_is_slice_file DEFAULT 1,
    printer_profile_summary NVARCHAR(1000) NULL,
    upload_status NVARCHAR(50) NOT NULL CONSTRAINT DF_model_files_upload_status DEFAULT N'stored',
    virus_scan_status NVARCHAR(50) NOT NULL CONSTRAINT DF_model_files_virus_scan_status DEFAULT N'pending',
    analysis_status NVARCHAR(50) NOT NULL CONSTRAINT DF_model_files_analysis_status DEFAULT N'pending',
    owner_type NVARCHAR(50) NOT NULL CONSTRAINT DF_model_files_owner_type DEFAULT N'user',
    owner_id BIGINT NOT NULL,
    created_at DATETIME2(3) NOT NULL CONSTRAINT DF_model_files_created_at DEFAULT SYSUTCDATETIME(),
    deleted_at DATETIME2(3) NULL,
    CONSTRAINT FK_model_files_user FOREIGN KEY (user_id) REFERENCES dbo.users(id),
    CONSTRAINT CK_model_files_size CHECK (file_size > 0)
);

CREATE TABLE dbo.custom_requests (
    id BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    request_no NVARCHAR(50) NOT NULL,
    user_id BIGINT NOT NULL,
    slice_file_id BIGINT NULL,
    requested_print_time DATETIME2(3) NULL,
    preferred_printer_id BIGINT NULL,
    preferred_printer_model NVARCHAR(200) NULL,
    filament_color NVARCHAR(100) NULL,
    filament_type NVARCHAR(100) NULL,
    use_ams BIT NOT NULL,
    plate_count INT NOT NULL,
    status NVARCHAR(50) NOT NULL CONSTRAINT DF_custom_requests_status DEFAULT N'submitted',
    reviewer_id BIGINT NULL,
    reviewed_at DATETIME2(3) NULL,
    review_remark NVARCHAR(1000) NULL,
    created_at DATETIME2(3) NOT NULL CONSTRAINT DF_custom_requests_created_at DEFAULT SYSUTCDATETIME(),
    updated_at DATETIME2(3) NOT NULL CONSTRAINT DF_custom_requests_updated_at DEFAULT SYSUTCDATETIME(),
    row_version ROWVERSION NOT NULL,
    CONSTRAINT UQ_custom_requests_request_no UNIQUE (request_no),
    CONSTRAINT FK_custom_requests_user FOREIGN KEY (user_id) REFERENCES dbo.users(id),
    CONSTRAINT FK_custom_requests_slice_file FOREIGN KEY (slice_file_id) REFERENCES dbo.model_files(id),
    CONSTRAINT FK_custom_requests_preferred_printer FOREIGN KEY (preferred_printer_id) REFERENCES dbo.printers(id),
    CONSTRAINT FK_custom_requests_reviewer FOREIGN KEY (reviewer_id) REFERENCES dbo.staff_users(id),
    CONSTRAINT CK_custom_requests_plate_count CHECK (plate_count > 0),
    CONSTRAINT CK_custom_requests_status CHECK (status IN (N'submitted', N'reviewing', N'need_more_info', N'rejected', N'quote_pending', N'quoted', N'quote_confirmed', N'payment_confirmed', N'scheduled'))
);

ALTER TABLE dbo.model_files
ADD CONSTRAINT FK_model_files_custom_request FOREIGN KEY (custom_request_id) REFERENCES dbo.custom_requests(id);

CREATE TABLE dbo.custom_request_reviews (
    id BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    custom_request_id BIGINT NOT NULL,
    reviewer_id BIGINT NOT NULL,
    from_status NVARCHAR(50) NULL,
    to_status NVARCHAR(50) NOT NULL,
    remark NVARCHAR(1000) NULL,
    created_at DATETIME2(3) NOT NULL CONSTRAINT DF_custom_request_reviews_created_at DEFAULT SYSUTCDATETIME(),
    CONSTRAINT FK_custom_request_reviews_request FOREIGN KEY (custom_request_id) REFERENCES dbo.custom_requests(id),
    CONSTRAINT FK_custom_request_reviews_reviewer FOREIGN KEY (reviewer_id) REFERENCES dbo.staff_users(id)
);

CREATE TABLE dbo.orders (
    id BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    order_no NVARCHAR(50) NOT NULL,
    user_id BIGINT NOT NULL,
    order_type NVARCHAR(50) NOT NULL,
    status NVARCHAR(50) NOT NULL CONSTRAINT DF_orders_status DEFAULT N'submitted',
    total_amount DECIMAL(18,2) NOT NULL CONSTRAINT DF_orders_total_amount DEFAULT 0,
    payment_status NVARCHAR(50) NOT NULL CONSTRAINT DF_orders_payment_status DEFAULT N'unconfirmed',
    payment_confirmed_by BIGINT NULL,
    payment_confirmed_at DATETIME2(3) NULL,
    customer_note NVARCHAR(1000) NULL,
    admin_note NVARCHAR(1000) NULL,
    receiver_name NVARCHAR(100) NULL,
    receiver_phone NVARCHAR(50) NULL,
    receiver_address NVARCHAR(1000) NULL,
    user_coupon_id BIGINT NULL,
    coupon_discount_amount DECIMAL(18,2) NOT NULL CONSTRAINT DF_orders_coupon_discount DEFAULT 0,
    created_at DATETIME2(3) NOT NULL CONSTRAINT DF_orders_created_at DEFAULT SYSUTCDATETIME(),
    updated_at DATETIME2(3) NOT NULL CONSTRAINT DF_orders_updated_at DEFAULT SYSUTCDATETIME(),
    row_version ROWVERSION NOT NULL,
    CONSTRAINT UQ_orders_order_no UNIQUE (order_no),
    CONSTRAINT FK_orders_user FOREIGN KEY (user_id) REFERENCES dbo.users(id),
    CONSTRAINT FK_orders_payment_confirmed_by FOREIGN KEY (payment_confirmed_by) REFERENCES dbo.staff_users(id),
    CONSTRAINT FK_orders_user_coupon FOREIGN KEY (user_coupon_id) REFERENCES dbo.user_coupons(id),
    CONSTRAINT CK_orders_type CHECK (order_type IN (N'listed_product', N'custom')),
    CONSTRAINT CK_orders_status CHECK (status IN (N'submitted', N'reviewing', N'quoted', N'quote_confirmed', N'payment_confirmed', N'scheduled', N'printing', N'post_processing', N'quality_check', N'partially_completed', N'completed', N'partially_inbound', N'in_warehouse', N'ready_to_ship', N'shipping', N'partially_shipped', N'shipped', N'cancelled')),
    CONSTRAINT CK_orders_payment_status CHECK (payment_status IN (N'unconfirmed', N'confirmed', N'cancelled'))
);

CREATE TABLE dbo.quotes (
    id BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    quote_no NVARCHAR(50) NOT NULL,
    custom_request_id BIGINT NULL,
    order_id BIGINT NULL,
    estimated_price DECIMAL(18,2) NULL,
    manual_price DECIMAL(18,2) NOT NULL,
    estimated_days INT NULL,
    material_cost DECIMAL(18,2) NULL,
    machine_cost DECIMAL(18,2) NULL,
    labor_cost DECIMAL(18,2) NULL,
    post_processing_cost DECIMAL(18,2) NULL,
    remark NVARCHAR(1000) NULL,
    status NVARCHAR(50) NOT NULL CONSTRAINT DF_quotes_status DEFAULT N'draft',
    created_by BIGINT NULL,
    confirmed_by_user_at DATETIME2(3) NULL,
    created_at DATETIME2(3) NOT NULL CONSTRAINT DF_quotes_created_at DEFAULT SYSUTCDATETIME(),
    updated_at DATETIME2(3) NOT NULL CONSTRAINT DF_quotes_updated_at DEFAULT SYSUTCDATETIME(),
    row_version ROWVERSION NOT NULL,
    CONSTRAINT UQ_quotes_quote_no UNIQUE (quote_no),
    CONSTRAINT FK_quotes_custom_request FOREIGN KEY (custom_request_id) REFERENCES dbo.custom_requests(id),
    CONSTRAINT FK_quotes_order FOREIGN KEY (order_id) REFERENCES dbo.orders(id),
    CONSTRAINT FK_quotes_created_by FOREIGN KEY (created_by) REFERENCES dbo.staff_users(id),
    CONSTRAINT CK_quotes_status CHECK (status IN (N'draft', N'sent', N'confirmed', N'cancelled')),
    CONSTRAINT CK_quotes_manual_price CHECK (manual_price >= 0)
);

CREATE TABLE dbo.order_items (
    id BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    order_id BIGINT NOT NULL,
    product_id BIGINT NULL,
    sku_id BIGINT NULL,
    custom_request_id BIGINT NULL,
    item_name NVARCHAR(200) NOT NULL,
    unit_price DECIMAL(18,2) NOT NULL,
    quantity INT NOT NULL,
    produced_quantity INT NOT NULL CONSTRAINT DF_order_items_produced_quantity DEFAULT 0,
    inbounded_quantity INT NOT NULL CONSTRAINT DF_order_items_inbounded_quantity DEFAULT 0,
    shipped_quantity INT NOT NULL CONSTRAINT DF_order_items_shipped_quantity DEFAULT 0,
    subtotal DECIMAL(18,2) NOT NULL,
    created_at DATETIME2(3) NOT NULL CONSTRAINT DF_order_items_created_at DEFAULT SYSUTCDATETIME(),
    CONSTRAINT FK_order_items_order FOREIGN KEY (order_id) REFERENCES dbo.orders(id),
    CONSTRAINT FK_order_items_product FOREIGN KEY (product_id) REFERENCES dbo.products(id),
    CONSTRAINT FK_order_items_sku FOREIGN KEY (sku_id) REFERENCES dbo.product_skus(id),
    CONSTRAINT FK_order_items_custom_request FOREIGN KEY (custom_request_id) REFERENCES dbo.custom_requests(id),
    CONSTRAINT CK_order_items_quantity CHECK (quantity > 0 AND produced_quantity >= 0 AND inbounded_quantity >= 0 AND shipped_quantity >= 0),
    CONSTRAINT CK_order_items_amount CHECK (unit_price >= 0 AND subtotal >= 0)
);

CREATE TABLE dbo.print_tasks (
    id BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    task_no NVARCHAR(50) NOT NULL,
    order_id BIGINT NOT NULL,
    order_item_id BIGINT NULL,
    printer_id BIGINT NULL,
    slice_file_id BIGINT NULL,
    material_id BIGINT NULL,
    status NVARCHAR(50) NOT NULL CONSTRAINT DF_print_tasks_status DEFAULT N'pending',
    warehouse_status NVARCHAR(50) NOT NULL CONSTRAINT DF_print_tasks_warehouse_status DEFAULT N'not_required',
    priority INT NOT NULL CONSTRAINT DF_print_tasks_priority DEFAULT 0,
    plate_count INT NOT NULL CONSTRAINT DF_print_tasks_plate_count DEFAULT 1,
    use_ams BIT NOT NULL CONSTRAINT DF_print_tasks_use_ams DEFAULT 0,
    estimated_minutes INT NULL,
    started_at DATETIME2(3) NULL,
    finished_at DATETIME2(3) NULL,
    failure_reason NVARCHAR(1000) NULL,
    created_at DATETIME2(3) NOT NULL CONSTRAINT DF_print_tasks_created_at DEFAULT SYSUTCDATETIME(),
    updated_at DATETIME2(3) NOT NULL CONSTRAINT DF_print_tasks_updated_at DEFAULT SYSUTCDATETIME(),
    row_version ROWVERSION NOT NULL,
    CONSTRAINT UQ_print_tasks_task_no UNIQUE (task_no),
    CONSTRAINT FK_print_tasks_order FOREIGN KEY (order_id) REFERENCES dbo.orders(id),
    CONSTRAINT FK_print_tasks_order_item FOREIGN KEY (order_item_id) REFERENCES dbo.order_items(id),
    CONSTRAINT FK_print_tasks_printer FOREIGN KEY (printer_id) REFERENCES dbo.printers(id),
    CONSTRAINT FK_print_tasks_slice_file FOREIGN KEY (slice_file_id) REFERENCES dbo.model_files(id),
    CONSTRAINT FK_print_tasks_material FOREIGN KEY (material_id) REFERENCES dbo.materials(id),
    CONSTRAINT CK_print_tasks_status CHECK (status IN (N'pending', N'scheduled', N'printing', N'paused', N'completed', N'failed', N'cancelled')),
    CONSTRAINT CK_print_tasks_warehouse_status CHECK (warehouse_status IN (N'not_required', N'pending_inbound', N'inbounded', N'outbounded')),
    CONSTRAINT CK_print_tasks_plate_count CHECK (plate_count > 0)
);

CREATE TABLE dbo.production_schedule_orders (
    id BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    schedule_no NVARCHAR(50) NOT NULL,
    order_id BIGINT NOT NULL,
    status NVARCHAR(50) NOT NULL CONSTRAINT DF_production_schedule_orders_status DEFAULT N'scheduled',
    planned_start_at DATETIME2(3) NOT NULL,
    planned_end_at DATETIME2(3) NOT NULL,
    due_at DATETIME2(3) NULL,
    priority INT NOT NULL CONSTRAINT DF_production_schedule_orders_priority DEFAULT 0,
    created_by BIGINT NULL,
    created_at DATETIME2(3) NOT NULL CONSTRAINT DF_production_schedule_orders_created_at DEFAULT SYSUTCDATETIME(),
    updated_at DATETIME2(3) NOT NULL CONSTRAINT DF_production_schedule_orders_updated_at DEFAULT SYSUTCDATETIME(),
    row_version ROWVERSION NOT NULL,
    CONSTRAINT UQ_production_schedule_orders_schedule_no UNIQUE (schedule_no),
    CONSTRAINT FK_production_schedule_orders_order FOREIGN KEY (order_id) REFERENCES dbo.orders(id),
    CONSTRAINT FK_production_schedule_orders_created_by FOREIGN KEY (created_by) REFERENCES dbo.staff_users(id),
    CONSTRAINT CK_production_schedule_orders_time CHECK (planned_end_at > planned_start_at),
    CONSTRAINT CK_production_schedule_orders_status CHECK (status IN (N'scheduled', N'locked', N'in_progress', N'delayed', N'completed', N'cancelled'))
);

CREATE TABLE dbo.production_schedule_items (
    id BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    schedule_order_id BIGINT NOT NULL,
    print_task_id BIGINT NULL,
    printer_id BIGINT NOT NULL,
    scheduled_start_at DATETIME2(3) NOT NULL,
    scheduled_end_at DATETIME2(3) NOT NULL,
    status NVARCHAR(50) NOT NULL CONSTRAINT DF_production_schedule_items_status DEFAULT N'scheduled',
    sort_order INT NOT NULL CONSTRAINT DF_production_schedule_items_sort_order DEFAULT 0,
    created_at DATETIME2(3) NOT NULL CONSTRAINT DF_production_schedule_items_created_at DEFAULT SYSUTCDATETIME(),
    updated_at DATETIME2(3) NOT NULL CONSTRAINT DF_production_schedule_items_updated_at DEFAULT SYSUTCDATETIME(),
    row_version ROWVERSION NOT NULL,
    CONSTRAINT FK_production_schedule_items_order FOREIGN KEY (schedule_order_id) REFERENCES dbo.production_schedule_orders(id),
    CONSTRAINT FK_production_schedule_items_task FOREIGN KEY (print_task_id) REFERENCES dbo.print_tasks(id),
    CONSTRAINT FK_production_schedule_items_printer FOREIGN KEY (printer_id) REFERENCES dbo.printers(id),
    CONSTRAINT CK_production_schedule_items_time CHECK (scheduled_end_at > scheduled_start_at),
    CONSTRAINT CK_production_schedule_items_status CHECK (status IN (N'scheduled', N'locked', N'in_progress', N'delayed', N'completed', N'cancelled'))
);

CREATE TABLE dbo.printer_status_logs (
    id BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    printer_id BIGINT NOT NULL,
    from_status NVARCHAR(50) NULL,
    to_status NVARCHAR(50) NOT NULL,
    progress DECIMAL(5,2) NULL,
    nozzle_temp DECIMAL(8,2) NULL,
    bed_temp DECIMAL(8,2) NULL,
    remaining_minutes INT NULL,
    changed_by BIGINT NULL,
    raw_payload NVARCHAR(MAX) NULL,
    created_at DATETIME2(3) NOT NULL CONSTRAINT DF_printer_status_logs_created_at DEFAULT SYSUTCDATETIME(),
    CONSTRAINT FK_printer_status_logs_printer FOREIGN KEY (printer_id) REFERENCES dbo.printers(id),
    CONSTRAINT FK_printer_status_logs_changed_by FOREIGN KEY (changed_by) REFERENCES dbo.staff_users(id)
);

CREATE TABLE dbo.finished_goods_inventory (
    id BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    product_id BIGINT NULL,
    sku_id BIGINT NULL,
    order_id BIGINT NULL,
    available_quantity INT NOT NULL CONSTRAINT DF_finished_goods_available DEFAULT 0,
    reserved_quantity INT NOT NULL CONSTRAINT DF_finished_goods_reserved DEFAULT 0,
    in_progress_quantity INT NOT NULL CONSTRAINT DF_finished_goods_in_progress DEFAULT 0,
    warehouse_location NVARCHAR(200) NULL,
    updated_at DATETIME2(3) NOT NULL CONSTRAINT DF_finished_goods_updated_at DEFAULT SYSUTCDATETIME(),
    CONSTRAINT FK_finished_goods_product FOREIGN KEY (product_id) REFERENCES dbo.products(id),
    CONSTRAINT FK_finished_goods_sku FOREIGN KEY (sku_id) REFERENCES dbo.product_skus(id),
    CONSTRAINT FK_finished_goods_order FOREIGN KEY (order_id) REFERENCES dbo.orders(id),
    CONSTRAINT CK_finished_goods_quantity CHECK (available_quantity >= 0 AND reserved_quantity >= 0 AND in_progress_quantity >= 0)
);

CREATE TABLE dbo.warehouses (
    id BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    warehouse_code NVARCHAR(50) NOT NULL,
    name NVARCHAR(100) NOT NULL,
    status NVARCHAR(50) NOT NULL CONSTRAINT DF_warehouses_status DEFAULT N'active',
    remark NVARCHAR(1000) NULL,
    created_at DATETIME2(3) NOT NULL CONSTRAINT DF_warehouses_created_at DEFAULT SYSUTCDATETIME(),
    updated_at DATETIME2(3) NOT NULL CONSTRAINT DF_warehouses_updated_at DEFAULT SYSUTCDATETIME(),
    CONSTRAINT UQ_warehouses_code UNIQUE (warehouse_code),
    CONSTRAINT CK_warehouses_status CHECK (status IN (N'active', N'disabled'))
);

CREATE TABLE dbo.warehouse_locations (
    id BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    warehouse_id BIGINT NOT NULL,
    location_code NVARCHAR(50) NOT NULL,
    name NVARCHAR(100) NULL,
    status NVARCHAR(50) NOT NULL CONSTRAINT DF_warehouse_locations_status DEFAULT N'active',
    remark NVARCHAR(1000) NULL,
    created_at DATETIME2(3) NOT NULL CONSTRAINT DF_warehouse_locations_created_at DEFAULT SYSUTCDATETIME(),
    updated_at DATETIME2(3) NOT NULL CONSTRAINT DF_warehouse_locations_updated_at DEFAULT SYSUTCDATETIME(),
    CONSTRAINT FK_warehouse_locations_warehouse FOREIGN KEY (warehouse_id) REFERENCES dbo.warehouses(id),
    CONSTRAINT UQ_warehouse_locations_code UNIQUE (warehouse_id, location_code),
    CONSTRAINT CK_warehouse_locations_status CHECK (status IN (N'active', N'disabled'))
);

CREATE TABLE dbo.warehouse_stock_items (
    id BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    stock_item_no NVARCHAR(50) NOT NULL,
    warehouse_id BIGINT NOT NULL,
    location_id BIGINT NULL,
    order_id BIGINT NOT NULL,
    order_item_id BIGINT NULL,
    print_task_id BIGINT NULL,
    product_id BIGINT NULL,
    sku_id BIGINT NULL,
    custom_request_id BIGINT NULL,
    quantity INT NOT NULL CONSTRAINT DF_warehouse_stock_items_quantity DEFAULT 1,
    status NVARCHAR(50) NOT NULL CONSTRAINT DF_warehouse_stock_items_status DEFAULT N'available',
    inbounded_at DATETIME2(3) NULL,
    outbounded_at DATETIME2(3) NULL,
    created_by BIGINT NULL,
    created_at DATETIME2(3) NOT NULL CONSTRAINT DF_warehouse_stock_items_created_at DEFAULT SYSUTCDATETIME(),
    updated_at DATETIME2(3) NOT NULL CONSTRAINT DF_warehouse_stock_items_updated_at DEFAULT SYSUTCDATETIME(),
    row_version ROWVERSION NOT NULL,
    CONSTRAINT UQ_warehouse_stock_items_no UNIQUE (stock_item_no),
    CONSTRAINT FK_warehouse_stock_items_warehouse FOREIGN KEY (warehouse_id) REFERENCES dbo.warehouses(id),
    CONSTRAINT FK_warehouse_stock_items_location FOREIGN KEY (location_id) REFERENCES dbo.warehouse_locations(id),
    CONSTRAINT FK_warehouse_stock_items_order FOREIGN KEY (order_id) REFERENCES dbo.orders(id),
    CONSTRAINT FK_warehouse_stock_items_order_item FOREIGN KEY (order_item_id) REFERENCES dbo.order_items(id),
    CONSTRAINT FK_warehouse_stock_items_print_task FOREIGN KEY (print_task_id) REFERENCES dbo.print_tasks(id),
    CONSTRAINT FK_warehouse_stock_items_product FOREIGN KEY (product_id) REFERENCES dbo.products(id),
    CONSTRAINT FK_warehouse_stock_items_sku FOREIGN KEY (sku_id) REFERENCES dbo.product_skus(id),
    CONSTRAINT FK_warehouse_stock_items_custom_request FOREIGN KEY (custom_request_id) REFERENCES dbo.custom_requests(id),
    CONSTRAINT FK_warehouse_stock_items_created_by FOREIGN KEY (created_by) REFERENCES dbo.staff_users(id),
    CONSTRAINT CK_warehouse_stock_items_quantity CHECK (quantity > 0),
    CONSTRAINT CK_warehouse_stock_items_status CHECK (status IN (N'available', N'reserved', N'outbound', N'shipped', N'cancelled'))
);

CREATE TABLE dbo.warehouse_inbound_records (
    id BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    inbound_no NVARCHAR(50) NOT NULL,
    inbound_type NVARCHAR(50) NOT NULL CONSTRAINT DF_warehouse_inbound_records_type DEFAULT N'production_completed',
    warehouse_id BIGINT NOT NULL,
    location_id BIGINT NULL,
    order_id BIGINT NOT NULL,
    order_item_id BIGINT NULL,
    print_task_id BIGINT NULL,
    stock_item_id BIGINT NULL,
    quantity INT NOT NULL CONSTRAINT DF_warehouse_inbound_records_quantity DEFAULT 1,
    operator_id BIGINT NULL,
    remark NVARCHAR(1000) NULL,
    created_at DATETIME2(3) NOT NULL CONSTRAINT DF_warehouse_inbound_records_created_at DEFAULT SYSUTCDATETIME(),
    CONSTRAINT UQ_warehouse_inbound_records_no UNIQUE (inbound_no),
    CONSTRAINT FK_warehouse_inbound_records_warehouse FOREIGN KEY (warehouse_id) REFERENCES dbo.warehouses(id),
    CONSTRAINT FK_warehouse_inbound_records_location FOREIGN KEY (location_id) REFERENCES dbo.warehouse_locations(id),
    CONSTRAINT FK_warehouse_inbound_records_order FOREIGN KEY (order_id) REFERENCES dbo.orders(id),
    CONSTRAINT FK_warehouse_inbound_records_order_item FOREIGN KEY (order_item_id) REFERENCES dbo.order_items(id),
    CONSTRAINT FK_warehouse_inbound_records_print_task FOREIGN KEY (print_task_id) REFERENCES dbo.print_tasks(id),
    CONSTRAINT FK_warehouse_inbound_records_stock_item FOREIGN KEY (stock_item_id) REFERENCES dbo.warehouse_stock_items(id),
    CONSTRAINT FK_warehouse_inbound_records_operator FOREIGN KEY (operator_id) REFERENCES dbo.staff_users(id),
    CONSTRAINT CK_warehouse_inbound_records_quantity CHECK (quantity > 0),
    CONSTRAINT CK_warehouse_inbound_records_type CHECK (inbound_type IN (N'production_completed', N'manual_adjustment', N'return_inbound'))
);

CREATE TABLE dbo.shipments (
    id BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    shipment_no NVARCHAR(50) NOT NULL,
    order_id BIGINT NOT NULL,
    status NVARCHAR(50) NOT NULL CONSTRAINT DF_shipments_status DEFAULT N'ready',
    receiver_name NVARCHAR(100) NULL,
    receiver_phone NVARCHAR(50) NULL,
    receiver_address NVARCHAR(1000) NULL,
    remark NVARCHAR(1000) NULL,
    created_by BIGINT NULL,
    created_at DATETIME2(3) NOT NULL CONSTRAINT DF_shipments_created_at DEFAULT SYSUTCDATETIME(),
    updated_at DATETIME2(3) NOT NULL CONSTRAINT DF_shipments_updated_at DEFAULT SYSUTCDATETIME(),
    CONSTRAINT UQ_shipments_no UNIQUE (shipment_no),
    CONSTRAINT FK_shipments_order FOREIGN KEY (order_id) REFERENCES dbo.orders(id),
    CONSTRAINT FK_shipments_created_by FOREIGN KEY (created_by) REFERENCES dbo.staff_users(id),
    CONSTRAINT CK_shipments_status CHECK (status IN (N'draft', N'ready', N'outbounded', N'cancelled'))
);

CREATE TABLE dbo.shipment_packages (
    id BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    shipment_id BIGINT NOT NULL,
    package_no NVARCHAR(50) NOT NULL,
    carrier_code NVARCHAR(50) NULL,
    carrier_name NVARCHAR(100) NULL,
    tracking_no NVARCHAR(100) NOT NULL,
    status NVARCHAR(50) NOT NULL CONSTRAINT DF_shipment_packages_status DEFAULT N'ready',
    created_at DATETIME2(3) NOT NULL CONSTRAINT DF_shipment_packages_created_at DEFAULT SYSUTCDATETIME(),
    updated_at DATETIME2(3) NOT NULL CONSTRAINT DF_shipment_packages_updated_at DEFAULT SYSUTCDATETIME(),
    CONSTRAINT FK_shipment_packages_shipment FOREIGN KEY (shipment_id) REFERENCES dbo.shipments(id),
    CONSTRAINT CK_shipment_packages_status CHECK (status IN (N'ready', N'outbounded', N'cancelled'))
);

CREATE TABLE dbo.shipment_items (
    id BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    shipment_id BIGINT NOT NULL,
    package_id BIGINT NULL,
    stock_item_id BIGINT NOT NULL,
    order_item_id BIGINT NULL,
    quantity INT NOT NULL CONSTRAINT DF_shipment_items_quantity DEFAULT 1,
    created_at DATETIME2(3) NOT NULL CONSTRAINT DF_shipment_items_created_at DEFAULT SYSUTCDATETIME(),
    CONSTRAINT FK_shipment_items_shipment FOREIGN KEY (shipment_id) REFERENCES dbo.shipments(id),
    CONSTRAINT FK_shipment_items_package FOREIGN KEY (package_id) REFERENCES dbo.shipment_packages(id),
    CONSTRAINT FK_shipment_items_stock_item FOREIGN KEY (stock_item_id) REFERENCES dbo.warehouse_stock_items(id),
    CONSTRAINT FK_shipment_items_order_item FOREIGN KEY (order_item_id) REFERENCES dbo.order_items(id),
    CONSTRAINT CK_shipment_items_quantity CHECK (quantity > 0)
);

CREATE TABLE dbo.warehouse_outbound_records (
    id BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    outbound_no NVARCHAR(50) NOT NULL,
    status NVARCHAR(50) NOT NULL CONSTRAINT DF_warehouse_outbound_records_status DEFAULT N'draft',
    outbound_type NVARCHAR(50) NOT NULL CONSTRAINT DF_warehouse_outbound_records_type DEFAULT N'shipment',
    operator_id BIGINT NULL,
    confirmed_at DATETIME2(3) NULL,
    remark NVARCHAR(1000) NULL,
    created_at DATETIME2(3) NOT NULL CONSTRAINT DF_warehouse_outbound_records_created_at DEFAULT SYSUTCDATETIME(),
    updated_at DATETIME2(3) NOT NULL CONSTRAINT DF_warehouse_outbound_records_updated_at DEFAULT SYSUTCDATETIME(),
    CONSTRAINT UQ_warehouse_outbound_records_no UNIQUE (outbound_no),
    CONSTRAINT FK_warehouse_outbound_records_operator FOREIGN KEY (operator_id) REFERENCES dbo.staff_users(id),
    CONSTRAINT CK_warehouse_outbound_records_status CHECK (status IN (N'draft', N'confirmed', N'cancelled')),
    CONSTRAINT CK_warehouse_outbound_records_type CHECK (outbound_type IN (N'shipment', N'manual_adjustment'))
);

CREATE TABLE dbo.warehouse_outbound_items (
    id BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    outbound_id BIGINT NOT NULL,
    shipment_id BIGINT NOT NULL,
    package_id BIGINT NULL,
    stock_item_id BIGINT NOT NULL,
    quantity INT NOT NULL CONSTRAINT DF_warehouse_outbound_items_quantity DEFAULT 1,
    created_at DATETIME2(3) NOT NULL CONSTRAINT DF_warehouse_outbound_items_created_at DEFAULT SYSUTCDATETIME(),
    CONSTRAINT FK_warehouse_outbound_items_outbound FOREIGN KEY (outbound_id) REFERENCES dbo.warehouse_outbound_records(id),
    CONSTRAINT FK_warehouse_outbound_items_shipment FOREIGN KEY (shipment_id) REFERENCES dbo.shipments(id),
    CONSTRAINT FK_warehouse_outbound_items_package FOREIGN KEY (package_id) REFERENCES dbo.shipment_packages(id),
    CONSTRAINT FK_warehouse_outbound_items_stock_item FOREIGN KEY (stock_item_id) REFERENCES dbo.warehouse_stock_items(id),
    CONSTRAINT CK_warehouse_outbound_items_quantity CHECK (quantity > 0)
);

CREATE TABLE dbo.inventory_locks (
    id BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    lock_type NVARCHAR(50) NOT NULL,
    order_id BIGINT NULL,
    print_task_id BIGINT NULL,
    product_id BIGINT NULL,
    sku_id BIGINT NULL,
    material_id BIGINT NULL,
    quantity INT NULL,
    weight DECIMAL(18,3) NULL,
    status NVARCHAR(50) NOT NULL CONSTRAINT DF_inventory_locks_status DEFAULT N'locked',
    locked_by BIGINT NULL,
    expires_at DATETIME2(3) NULL,
    created_at DATETIME2(3) NOT NULL CONSTRAINT DF_inventory_locks_created_at DEFAULT SYSUTCDATETIME(),
    released_at DATETIME2(3) NULL,
    row_version ROWVERSION NOT NULL,
    CONSTRAINT FK_inventory_locks_order FOREIGN KEY (order_id) REFERENCES dbo.orders(id),
    CONSTRAINT FK_inventory_locks_task FOREIGN KEY (print_task_id) REFERENCES dbo.print_tasks(id),
    CONSTRAINT FK_inventory_locks_product FOREIGN KEY (product_id) REFERENCES dbo.products(id),
    CONSTRAINT FK_inventory_locks_sku FOREIGN KEY (sku_id) REFERENCES dbo.product_skus(id),
    CONSTRAINT FK_inventory_locks_material FOREIGN KEY (material_id) REFERENCES dbo.materials(id),
    CONSTRAINT FK_inventory_locks_locked_by FOREIGN KEY (locked_by) REFERENCES dbo.staff_users(id),
    CONSTRAINT CK_inventory_locks_type CHECK (lock_type IN (N'material', N'finished_good', N'work_in_progress')),
    CONSTRAINT CK_inventory_locks_status CHECK (status IN (N'locked', N'released', N'consumed', N'cancelled')),
    CONSTRAINT CK_inventory_locks_amount CHECK ((quantity IS NULL OR quantity >= 0) AND (weight IS NULL OR weight >= 0))
);

CREATE TABLE dbo.material_stock_logs (
    id BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    material_id BIGINT NOT NULL,
    change_type NVARCHAR(50) NOT NULL,
    change_weight DECIMAL(18,3) NOT NULL,
    before_weight DECIMAL(18,3) NULL,
    after_weight DECIMAL(18,3) NULL,
    related_order_id BIGINT NULL,
    related_task_id BIGINT NULL,
    remark NVARCHAR(1000) NULL,
    created_by BIGINT NULL,
    created_at DATETIME2(3) NOT NULL CONSTRAINT DF_material_stock_logs_created_at DEFAULT SYSUTCDATETIME(),
    CONSTRAINT FK_material_stock_logs_material FOREIGN KEY (material_id) REFERENCES dbo.materials(id),
    CONSTRAINT FK_material_stock_logs_order FOREIGN KEY (related_order_id) REFERENCES dbo.orders(id),
    CONSTRAINT FK_material_stock_logs_task FOREIGN KEY (related_task_id) REFERENCES dbo.print_tasks(id),
    CONSTRAINT FK_material_stock_logs_created_by FOREIGN KEY (created_by) REFERENCES dbo.staff_users(id),
    CONSTRAINT CK_material_stock_logs_type CHECK (change_type IN (N'inbound', N'reserve', N'release', N'consume', N'loss', N'adjust'))
);

CREATE TABLE dbo.idempotency_keys (
    id BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    scope NVARCHAR(150) NOT NULL,
    idempotency_key NVARCHAR(100) NOT NULL,
    request_hash NVARCHAR(128) NOT NULL,
    response_body NVARCHAR(MAX) NULL,
    status_code INT NULL,
    resource_type NVARCHAR(100) NULL,
    resource_id BIGINT NULL,
    created_by_user_id BIGINT NULL,
    created_by_staff_id BIGINT NULL,
    expires_at DATETIME2(3) NOT NULL,
    created_at DATETIME2(3) NOT NULL CONSTRAINT DF_idempotency_keys_created_at DEFAULT SYSUTCDATETIME(),
    CONSTRAINT UQ_idempotency_keys_scope_key UNIQUE (scope, idempotency_key),
    CONSTRAINT FK_idempotency_keys_user FOREIGN KEY (created_by_user_id) REFERENCES dbo.users(id),
    CONSTRAINT FK_idempotency_keys_staff FOREIGN KEY (created_by_staff_id) REFERENCES dbo.staff_users(id)
);

CREATE TABLE dbo.operation_logs (
    id BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    operator_id BIGINT NULL,
    operation_type NVARCHAR(100) NOT NULL,
    target_table NVARCHAR(100) NULL,
    target_id BIGINT NULL,
    before_data NVARCHAR(MAX) NULL,
    after_data NVARCHAR(MAX) NULL,
    remark NVARCHAR(1000) NULL,
    created_at DATETIME2(3) NOT NULL CONSTRAINT DF_operation_logs_created_at DEFAULT SYSUTCDATETIME(),
    CONSTRAINT FK_operation_logs_operator FOREIGN KEY (operator_id) REFERENCES dbo.staff_users(id)
);
GO

-- Coupon templates (admin-defined, no discount upper-bound at DB level; user-issued limits enforced by service layer).
CREATE TABLE dbo.coupon_templates (
    id BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    coupon_no NVARCHAR(50) NOT NULL,
    name NVARCHAR(100) NOT NULL,
    discount_type NVARCHAR(50) NOT NULL,
    discount_value DECIMAL(18,2) NOT NULL,
    min_spend DECIMAL(18,2) NOT NULL CONSTRAINT DF_coupon_templates_min_spend DEFAULT 0,
    max_discount DECIMAL(18,2) NULL,
    scope_type NVARCHAR(50) NOT NULL CONSTRAINT DF_coupon_templates_scope_type DEFAULT N'all',
    scope_category_id BIGINT NULL,
    scope_product_id BIGINT NULL,
    validity_type NVARCHAR(50) NOT NULL,
    valid_days INT NULL,
    fixed_start_at DATETIME2(3) NULL,
    fixed_end_at DATETIME2(3) NULL,
    total_quota BIGINT NULL,
    issued_count BIGINT NOT NULL CONSTRAINT DF_coupon_templates_issued_count DEFAULT 0,
    per_user_limit INT NULL,
    status NVARCHAR(50) NOT NULL CONSTRAINT DF_coupon_templates_status DEFAULT N'active',
    remark NVARCHAR(1000) NULL,
    created_by BIGINT NULL,
    created_at DATETIME2(3) NOT NULL CONSTRAINT DF_coupon_templates_created_at DEFAULT SYSUTCDATETIME(),
    updated_at DATETIME2(3) NOT NULL CONSTRAINT DF_coupon_templates_updated_at DEFAULT SYSUTCDATETIME(),
    row_version ROWVERSION NOT NULL,
    CONSTRAINT UQ_coupon_templates_no UNIQUE (coupon_no),
    CONSTRAINT FK_coupon_templates_category FOREIGN KEY (scope_category_id) REFERENCES dbo.product_categories(id),
    CONSTRAINT FK_coupon_templates_product FOREIGN KEY (scope_product_id) REFERENCES dbo.products(id),
    CONSTRAINT FK_coupon_templates_created_by FOREIGN KEY (created_by) REFERENCES dbo.staff_users(id),
    CONSTRAINT CK_coupon_templates_discount_type CHECK (discount_type IN (N'fixed', N'percentage', N'fixed_no_threshold')),
    CONSTRAINT CK_coupon_templates_scope_type CHECK (scope_type IN (N'all', N'listed_product', N'custom', N'category', N'product')),
    CONSTRAINT CK_coupon_templates_validity_type CHECK (validity_type IN (N'fixed', N'relative')),
    CONSTRAINT CK_coupon_templates_status CHECK (status IN (N'active', N'disabled', N'archived')),
    CONSTRAINT CK_coupon_templates_discount_value CHECK (discount_value >= 0),
    CONSTRAINT CK_coupon_templates_max_discount CHECK (max_discount IS NULL OR max_discount >= 0)
);
GO

-- User coupons (issued instances).
CREATE TABLE dbo.user_coupons (
    id BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    template_id BIGINT NULL,
    coupon_no NVARCHAR(50) NOT NULL,
    name NVARCHAR(100) NOT NULL,
    discount_type NVARCHAR(50) NOT NULL CONSTRAINT DF_user_coupons_discount_type DEFAULT N'percentage',
    discount_value DECIMAL(18,2) NOT NULL,
    min_spend DECIMAL(18,2) NOT NULL CONSTRAINT DF_user_coupons_min_spend DEFAULT 0,
    scope_type NVARCHAR(50) NOT NULL CONSTRAINT DF_user_coupons_scope_type DEFAULT N'all',
    source NVARCHAR(50) NOT NULL CONSTRAINT DF_user_coupons_source DEFAULT N'lottery',
    status NVARCHAR(50) NOT NULL CONSTRAINT DF_user_coupons_status DEFAULT N'unused',
    valid_from DATETIME2(3) NOT NULL,
    valid_until DATETIME2(3) NOT NULL,
    used_at DATETIME2(3) NULL,
    used_order_id BIGINT NULL,
    discount_amount DECIMAL(18,2) NULL,
    revoked_at DATETIME2(3) NULL,
    revoked_by BIGINT NULL,
    revoke_reason NVARCHAR(500) NULL,
    created_by BIGINT NULL,
    created_at DATETIME2(3) NOT NULL CONSTRAINT DF_user_coupons_created_at DEFAULT SYSUTCDATETIME(),
    updated_at DATETIME2(3) NOT NULL CONSTRAINT DF_user_coupons_updated_at DEFAULT SYSUTCDATETIME(),
    row_version ROWVERSION NOT NULL,
    CONSTRAINT UQ_user_coupons_no UNIQUE (coupon_no),
    CONSTRAINT FK_user_coupons_user FOREIGN KEY (user_id) REFERENCES dbo.users(id),
    CONSTRAINT FK_user_coupons_template FOREIGN KEY (template_id) REFERENCES dbo.coupon_templates(id),
    CONSTRAINT FK_user_coupons_order FOREIGN KEY (used_order_id) REFERENCES dbo.orders(id),
    CONSTRAINT FK_user_coupons_revoked_by FOREIGN KEY (revoked_by) REFERENCES dbo.staff_users(id),
    CONSTRAINT FK_user_coupons_created_by FOREIGN KEY (created_by) REFERENCES dbo.staff_users(id),
    CONSTRAINT CK_user_coupons_discount_type CHECK (discount_type IN (N'percentage', N'fixed', N'fixed_no_threshold')),
    CONSTRAINT CK_user_coupons_source CHECK (source IN (N'admin_grant', N'lottery', N'signup_gift', N'promotion')),
    CONSTRAINT CK_user_coupons_status CHECK (status IN (N'unused', N'used', N'expired', N'revoked')),
    CONSTRAINT CK_user_coupons_scope CHECK (scope_type IN (N'all', N'listed_product', N'custom', N'category', N'product')),
    CONSTRAINT CK_user_coupons_time CHECK (valid_until > valid_from),
    CONSTRAINT CK_user_coupons_discount_value CHECK (discount_value >= 0),
    CONSTRAINT CK_user_coupons_discount_amount CHECK (discount_amount IS NULL OR discount_amount >= 0)
);
GO

-- Lottery draw records (tracks every draw, supports idempotency & daily limits).
CREATE TABLE dbo.lottery_records (
    id BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    record_no NVARCHAR(50) NOT NULL,
    user_id BIGINT NOT NULL,
    is_win BIT NOT NULL CONSTRAINT DF_lottery_records_is_win DEFAULT 1,
    prize_name NVARCHAR(100) NOT NULL,
    discount_value DECIMAL(18,2) NULL,
    won_coupon_id BIGINT NULL,
    idempotency_key NVARCHAR(100) NOT NULL,
    client_ip NVARCHAR(50) NULL,
    created_at DATETIME2(3) NOT NULL CONSTRAINT DF_lottery_records_created_at DEFAULT SYSUTCDATETIME(),
    CONSTRAINT UQ_lottery_records_no UNIQUE (record_no),
    CONSTRAINT FK_lottery_records_user FOREIGN KEY (user_id) REFERENCES dbo.users(id),
    CONSTRAINT FK_lottery_records_coupon FOREIGN KEY (won_coupon_id) REFERENCES dbo.user_coupons(id),
    CONSTRAINT CK_lottery_records_win CHECK (
        (is_win = 1 AND discount_value IS NOT NULL)
        OR (is_win = 0 AND discount_value IS NULL)
    )
);
GO

-- Coupon grant batches (admin batch issue tracking).
CREATE TABLE dbo.coupon_grant_batches (
    id BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    batch_no NVARCHAR(50) NOT NULL,
    template_id BIGINT NOT NULL,
    granted_by BIGINT NOT NULL,
    target_type NVARCHAR(50) NOT NULL,
    target_count INT NOT NULL,
    success_count INT NOT NULL CONSTRAINT DF_coupon_grant_batches_success DEFAULT 0,
    remark NVARCHAR(1000) NULL,
    created_at DATETIME2(3) NOT NULL CONSTRAINT DF_coupon_grant_batches_created_at DEFAULT SYSUTCDATETIME(),
    CONSTRAINT UQ_coupon_grant_batches_no UNIQUE (batch_no),
    CONSTRAINT FK_coupon_grant_batches_template FOREIGN KEY (template_id) REFERENCES dbo.coupon_templates(id),
    CONSTRAINT FK_coupon_grant_batches_granted_by FOREIGN KEY (granted_by) REFERENCES dbo.staff_users(id),
    CONSTRAINT CK_coupon_grant_batches_target_type CHECK (target_type IN (N'all_users', N'specified_users', N'single_user')),
    CONSTRAINT CK_coupon_grant_batches_count CHECK (target_count > 0 AND success_count >= 0 AND success_count <= target_count)
);
GO

CREATE INDEX IX_products_status ON dbo.products(sales_status, is_deleted, sort_order);
CREATE UNIQUE INDEX UX_users_email_active ON dbo.users(email) WHERE deleted_at IS NULL;
CREATE UNIQUE INDEX UX_users_phone_active_not_null ON dbo.users(phone) WHERE phone IS NOT NULL AND deleted_at IS NULL;
CREATE UNIQUE INDEX UX_staff_users_email_not_null ON dbo.staff_users(email) WHERE email IS NOT NULL;
CREATE INDEX IX_product_skus_product_status ON dbo.product_skus(product_id, status);
CREATE INDEX IX_product_images_product_type ON dbo.product_images(product_id, image_type, sort_order);
CREATE INDEX IX_auth_refresh_tokens_user ON dbo.auth_refresh_tokens(user_id, expires_at);
CREATE INDEX IX_auth_refresh_tokens_staff ON dbo.auth_refresh_tokens(staff_user_id, expires_at);
CREATE INDEX IX_orders_user_created ON dbo.orders(user_id, created_at DESC);
CREATE INDEX IX_orders_status_payment_created ON dbo.orders(status, payment_status, created_at DESC);
CREATE INDEX IX_custom_requests_user_status_created ON dbo.custom_requests(user_id, status, created_at DESC);
CREATE INDEX IX_custom_requests_status_created ON dbo.custom_requests(status, created_at DESC);
CREATE INDEX IX_quotes_status_created ON dbo.quotes(status, created_at DESC);
CREATE INDEX IX_printers_status ON dbo.printers(status);
CREATE INDEX IX_print_tasks_order_status ON dbo.print_tasks(order_id, status);
CREATE INDEX IX_print_tasks_printer_status ON dbo.print_tasks(printer_id, status);
CREATE INDEX IX_print_tasks_warehouse_status ON dbo.print_tasks(warehouse_status, status);
CREATE INDEX IX_schedule_orders_order_status ON dbo.production_schedule_orders(order_id, status);
CREATE INDEX IX_schedule_items_printer_time ON dbo.production_schedule_items(printer_id, scheduled_start_at, scheduled_end_at);
CREATE INDEX IX_inventory_locks_order_status ON dbo.inventory_locks(order_id, status);
CREATE INDEX IX_inventory_locks_material_status ON dbo.inventory_locks(material_id, status);
CREATE INDEX IX_materials_type_color_status ON dbo.materials(material_type, color, status);
CREATE INDEX IX_warehouse_locations_warehouse_status ON dbo.warehouse_locations(warehouse_id, status);
CREATE INDEX IX_warehouse_stock_items_order_status ON dbo.warehouse_stock_items(order_id, status);
CREATE INDEX IX_warehouse_stock_items_task ON dbo.warehouse_stock_items(print_task_id);
CREATE INDEX IX_warehouse_stock_items_location ON dbo.warehouse_stock_items(warehouse_id, location_id, status);
CREATE INDEX IX_warehouse_inbound_records_order_created ON dbo.warehouse_inbound_records(order_id, created_at DESC);
CREATE INDEX IX_shipments_order_status ON dbo.shipments(order_id, status);
CREATE INDEX IX_shipment_packages_tracking ON dbo.shipment_packages(tracking_no);
CREATE INDEX IX_shipment_items_stock_item ON dbo.shipment_items(stock_item_id);
CREATE INDEX IX_warehouse_outbound_records_status_created ON dbo.warehouse_outbound_records(status, created_at DESC);
CREATE INDEX IX_warehouse_outbound_items_stock_item ON dbo.warehouse_outbound_items(stock_item_id);
CREATE INDEX IX_user_coupons_user_status ON dbo.user_coupons(user_id, status, valid_until DESC);
CREATE INDEX IX_user_coupons_template ON dbo.user_coupons(template_id);
CREATE INDEX IX_orders_user_coupon ON dbo.orders(user_coupon_id);
CREATE INDEX IX_coupon_grant_batches_template ON dbo.coupon_grant_batches(template_id, created_at DESC);
CREATE INDEX IX_lottery_records_user_created ON dbo.lottery_records(user_id, created_at DESC);
CREATE UNIQUE INDEX UX_lottery_records_user_idem ON dbo.lottery_records(user_id, idempotency_key);
GO
