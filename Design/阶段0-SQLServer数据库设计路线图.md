# 阶段0：SQL Server 数据库设计路线图

## 1. 设计目标

本路线图用于指导 3D 打印农场管理系统阶段1的 SQL Server 数据库设计。

阶段1数据库需要支撑以下核心闭环：

- 上架商品下单后生产。
- 个性化定制提交切片文件。
- 管理员审核定制需求。
- 系统预计报价 + 管理员人工确认报价。
- 线下支付或人工收款确认。
- 以订单为单位排期。
- 一笔订单拆分为多个打印任务。
- 打印机状态由人工维护。
- 材料库存、成品库存、在制品库存、库存锁定。
- 阶段1不接在线支付和物流系统。

## 2. 数据库设计原则

- 使用 SQL Server 作为核心业务数据库。
- 所有核心表使用 `BIGINT IDENTITY(1,1)` 作为主键。
- 金额字段使用 `DECIMAL(18,2)`。
- 重量字段使用 `DECIMAL(18,3)`，单位默认克。
- 状态字段使用 `NVARCHAR(50)`，阶段1先用 CHECK 约束控制，后续可升级为字典表。
- 时间字段统一使用 `DATETIME2(3)`。
- 业务编号使用独立字段，例如 `order_no`、`task_no`、`quote_no`。
- 表必须包含 `created_at`、`updated_at`，重要业务表增加 `created_by`、`updated_by`。
- 触发器只做数据库一致性兜底，不替代后端业务服务。
- 删除优先使用软删除字段 `is_deleted`，避免直接物理删除业务数据。

## 3. Schema 划分建议

建议使用默认 `dbo` 即可。若后续系统复杂，可再拆分：

- `sales`：商品、订单、报价。
- `production`：打印机、打印任务、排期。
- `inventory`：库存、库存锁定、库存流水。
- `audit`：日志、审计。

阶段1建议先用 `dbo`，降低 Django / FastAPI 接入复杂度。

## 4. 核心实体关系

```text
users
  |
  | 1:N
  v
orders ---- order_items
  |             |
  |             +---- products / product_skus
  |             |
  |             +---- custom_requests
  |
  +---- quotes
  |
  +---- production_schedules
  |
  +---- print_tasks ---- printers
                         |
                         +---- printer_status_logs

products ---- product_skus
    |
    +---- product_images

custom_requests ---- model_files
        |
        +---- custom_request_reviews

materials ---- material_stock_logs
materials ---- inventory_locks
product_skus ---- finished_goods_inventory
orders ---- inventory_locks
```

## 5. 表设计路线

### 5.1 用户与员工

#### `users` 客户表

用途：手机 APP 客户账号。

字段建议：

- `id BIGINT IDENTITY PRIMARY KEY`
- `phone NVARCHAR(30) NOT NULL`
- `nickname NVARCHAR(100) NULL`
- `avatar_url NVARCHAR(500) NULL`
- `status NVARCHAR(50) NOT NULL DEFAULT 'active'`
- `created_at DATETIME2(3) NOT NULL`
- `updated_at DATETIME2(3) NOT NULL`

约束：

- `phone` 唯一。
- `status` 可选：`active`、`disabled`。

#### `staff_users` 员工表

用途：电脑端内部管理账号。

字段建议：

- `id BIGINT IDENTITY PRIMARY KEY`
- `username NVARCHAR(100) NOT NULL`
- `password_hash NVARCHAR(255) NOT NULL`
- `display_name NVARCHAR(100) NULL`
- `role NVARCHAR(50) NOT NULL`
- `status NVARCHAR(50) NOT NULL DEFAULT 'active'`
- `last_login_at DATETIME2(3) NULL`
- `created_at DATETIME2(3) NOT NULL`
- `updated_at DATETIME2(3) NOT NULL`

角色建议：

- `admin`：统一管理员。
- `operator`：生产操作员。
- `viewer`：只读。

阶段1可以只实现 `admin`。

## 6. 上架商品销售表

### 6.1 `product_categories` 商品分类表

字段建议：

- `id BIGINT IDENTITY PRIMARY KEY`
- `name NVARCHAR(100) NOT NULL`
- `sort_order INT NOT NULL DEFAULT 0`
- `status NVARCHAR(50) NOT NULL DEFAULT 'active'`
- `created_at DATETIME2(3) NOT NULL`
- `updated_at DATETIME2(3) NOT NULL`

### 6.2 `products` 上架商品表

用途：后台上架商品，客户 APP 浏览购买。

字段建议：

- `id BIGINT IDENTITY PRIMARY KEY`
- `category_id BIGINT NULL`
- `name NVARCHAR(200) NOT NULL`
- `description NVARCHAR(MAX) NULL`
- `cover_image_url NVARCHAR(500) NULL`
- `sales_status NVARCHAR(50) NOT NULL DEFAULT 'draft'`
- `production_mode NVARCHAR(50) NOT NULL DEFAULT 'make_to_order'`
- `base_price DECIMAL(18,2) NOT NULL DEFAULT 0`
- `supports_custom_note BIT NOT NULL DEFAULT 0`
- `sort_order INT NOT NULL DEFAULT 0`
- `is_deleted BIT NOT NULL DEFAULT 0`
- `created_at DATETIME2(3) NOT NULL`
- `updated_at DATETIME2(3) NOT NULL`

状态：

- `draft`：草稿。
- `on_sale`：销售中。
- `off_sale`：已下架。
- `sold_out`：售罄。
- `archived`：归档。

生产模式：

- `make_to_order`：下单后生产，阶段1默认。

### 6.3 `product_images` 商品图片表

用途：商品封面图、详情图、打印成品图、场景图。

字段建议：

- `id BIGINT IDENTITY PRIMARY KEY`
- `product_id BIGINT NOT NULL`
- `image_url NVARCHAR(500) NOT NULL`
- `image_type NVARCHAR(50) NOT NULL`
- `sort_order INT NOT NULL DEFAULT 0`
- `created_at DATETIME2(3) NOT NULL`

图片类型：

- `cover`：封面图。
- `detail`：详情图。
- `printed_sample`：打印成品图。
- `scene`：场景图。

### 6.4 `product_skus` 商品规格表

用途：上架商品的材料、颜色、尺寸、精度、价格。

字段建议：

- `id BIGINT IDENTITY PRIMARY KEY`
- `product_id BIGINT NOT NULL`
- `material_id BIGINT NULL`
- `color NVARCHAR(100) NULL`
- `size_label NVARCHAR(100) NULL`
- `precision_level NVARCHAR(100) NULL`
- `price DECIMAL(18,2) NOT NULL`
- `min_quantity INT NOT NULL DEFAULT 1`
- `max_quantity INT NULL`
- `status NVARCHAR(50) NOT NULL DEFAULT 'active'`
- `created_at DATETIME2(3) NOT NULL`
- `updated_at DATETIME2(3) NOT NULL`

说明：

- 阶段1上架商品下单后生产，因此 `product_skus` 不作为现货库存来源。
- 成品库存仍保留在 `finished_goods_inventory`，用于生产完成入库和后续扩展现货销售。

## 7. 个性化定制表

### 7.1 `custom_requests` 定制需求表

用途：客户提交切片文件和打印要求。

字段建议：

- `id BIGINT IDENTITY PRIMARY KEY`
- `request_no NVARCHAR(50) NOT NULL`
- `user_id BIGINT NOT NULL`
- `slice_file_id BIGINT NULL`
- `requested_print_time DATETIME2(3) NULL`
- `preferred_printer_id BIGINT NULL`
- `preferred_printer_model NVARCHAR(200) NULL`
- `filament_color NVARCHAR(100) NULL`
- `filament_type NVARCHAR(100) NULL`
- `use_ams BIT NOT NULL`
- `plate_count INT NOT NULL`
- `status NVARCHAR(50) NOT NULL DEFAULT 'submitted'`
- `reviewer_id BIGINT NULL`
- `reviewed_at DATETIME2(3) NULL`
- `review_remark NVARCHAR(1000) NULL`
- `created_at DATETIME2(3) NOT NULL`
- `updated_at DATETIME2(3) NOT NULL`

状态：

- `submitted`：已提交。
- `reviewing`：审核中。
- `need_more_info`：需补充信息。
- `rejected`：不可制作。
- `quote_pending`：待报价。
- `quoted`：已报价。
- `quote_confirmed`：报价已确认。
- `payment_confirmed`：收款已确认。
- `scheduled`：已排期。

约束：

- `plate_count > 0`。
- `use_ams` 必填。
- `slice_file_id` 在提交审核前必须存在，后端负责校验。

### 7.2 `model_files` 模型/切片文件表

用途：存储切片文件、后续兼容模型文件。

字段建议：

- `id BIGINT IDENTITY PRIMARY KEY`
- `user_id BIGINT NOT NULL`
- `custom_request_id BIGINT NULL`
- `file_name NVARCHAR(255) NOT NULL`
- `file_ext NVARCHAR(50) NOT NULL`
- `file_type NVARCHAR(50) NOT NULL`
- `file_size BIGINT NOT NULL`
- `storage_url NVARCHAR(500) NOT NULL`
- `checksum NVARCHAR(128) NULL`
- `is_slice_file BIT NOT NULL DEFAULT 1`
- `printer_profile_summary NVARCHAR(1000) NULL`
- `analysis_status NVARCHAR(50) NOT NULL DEFAULT 'pending'`
- `created_at DATETIME2(3) NOT NULL`

阶段1支持：

- `.gcode`
- `.3mf`
- `.bgcode`
- `.zip`

### 7.3 `custom_request_reviews` 定制审核记录表

用途：保留管理员审核轨迹。

字段建议：

- `id BIGINT IDENTITY PRIMARY KEY`
- `custom_request_id BIGINT NOT NULL`
- `reviewer_id BIGINT NOT NULL`
- `from_status NVARCHAR(50) NULL`
- `to_status NVARCHAR(50) NOT NULL`
- `remark NVARCHAR(1000) NULL`
- `created_at DATETIME2(3) NOT NULL`

说明：

- 每次审核、退回、驳回、通过都写入一条记录。
- 不建议用触发器自动写全部审核记录，审核动作应由后端显式写入，便于备注和权限控制。

## 8. 报价与订单表

### 8.1 `quotes` 报价表

用途：系统预计报价和管理员人工确认报价。

字段建议：

- `id BIGINT IDENTITY PRIMARY KEY`
- `quote_no NVARCHAR(50) NOT NULL`
- `custom_request_id BIGINT NULL`
- `order_id BIGINT NULL`
- `estimated_price DECIMAL(18,2) NULL`
- `manual_price DECIMAL(18,2) NOT NULL`
- `estimated_days INT NULL`
- `material_cost DECIMAL(18,2) NULL`
- `machine_cost DECIMAL(18,2) NULL`
- `labor_cost DECIMAL(18,2) NULL`
- `post_processing_cost DECIMAL(18,2) NULL`
- `remark NVARCHAR(1000) NULL`
- `status NVARCHAR(50) NOT NULL DEFAULT 'draft'`
- `created_by BIGINT NULL`
- `confirmed_by_user_at DATETIME2(3) NULL`
- `created_at DATETIME2(3) NOT NULL`
- `updated_at DATETIME2(3) NOT NULL`

状态：

- `draft`：草稿。
- `sent`：已发送客户。
- `confirmed`：客户已确认。
- `cancelled`：已取消。

### 8.2 `orders` 订单表

用途：上架商品订单和定制订单共用。

字段建议：

- `id BIGINT IDENTITY PRIMARY KEY`
- `order_no NVARCHAR(50) NOT NULL`
- `user_id BIGINT NOT NULL`
- `order_type NVARCHAR(50) NOT NULL`
- `status NVARCHAR(50) NOT NULL DEFAULT 'submitted'`
- `total_amount DECIMAL(18,2) NOT NULL DEFAULT 0`
- `payment_status NVARCHAR(50) NOT NULL DEFAULT 'unconfirmed'`
- `payment_confirmed_by BIGINT NULL`
- `payment_confirmed_at DATETIME2(3) NULL`
- `customer_note NVARCHAR(1000) NULL`
- `admin_note NVARCHAR(1000) NULL`
- `created_at DATETIME2(3) NOT NULL`
- `updated_at DATETIME2(3) NOT NULL`

订单类型：

- `listed_product`：上架商品。
- `custom`：个性化定制。

订单状态：

- `submitted`：已提交。
- `reviewing`：审核中。
- `quoted`：已报价。
- `quote_confirmed`：报价已确认。
- `payment_confirmed`：收款已确认。
- `scheduled`：已排期。
- `printing`：打印中。
- `post_processing`：后处理中。
- `quality_check`：质检中。
- `completed`：已完成。
- `cancelled`：已取消。

支付状态：

- `unconfirmed`：未确认。
- `confirmed`：已确认。
- `cancelled`：已取消。

### 8.3 `order_items` 订单明细表

字段建议：

- `id BIGINT IDENTITY PRIMARY KEY`
- `order_id BIGINT NOT NULL`
- `product_id BIGINT NULL`
- `sku_id BIGINT NULL`
- `custom_request_id BIGINT NULL`
- `item_name NVARCHAR(200) NOT NULL`
- `unit_price DECIMAL(18,2) NOT NULL`
- `quantity INT NOT NULL`
- `subtotal DECIMAL(18,2) NOT NULL`
- `created_at DATETIME2(3) NOT NULL`

约束：

- `quantity > 0`。
- 上架商品明细必须有关联 `product_id` 和 `sku_id`。
- 定制明细必须有关联 `custom_request_id`。
- `subtotal = unit_price * quantity` 建议由后端计算，触发器只做校验或修正兜底。

## 9. 打印机与生产排期表

### 9.1 `printers` 打印机表

字段建议：

- `id BIGINT IDENTITY PRIMARY KEY`
- `name NVARCHAR(100) NOT NULL`
- `brand NVARCHAR(100) NULL`
- `model NVARCHAR(100) NULL`
- `printer_type NVARCHAR(100) NULL`
- `supported_materials NVARCHAR(500) NULL`
- `build_volume NVARCHAR(100) NULL`
- `location NVARCHAR(200) NULL`
- `status NVARCHAR(50) NOT NULL DEFAULT 'idle'`
- `current_task_id BIGINT NULL`
- `supports_api BIT NOT NULL DEFAULT 0`
- `api_endpoint NVARCHAR(500) NULL`
- `last_seen_at DATETIME2(3) NULL`
- `remark NVARCHAR(1000) NULL`
- `created_at DATETIME2(3) NOT NULL`
- `updated_at DATETIME2(3) NOT NULL`

状态：

- `idle`
- `printing`
- `paused`
- `completed`
- `error`
- `offline`
- `maintenance`

### 9.2 `print_tasks` 打印任务表

用途：一笔订单可拆分为多个打印任务。

字段建议：

- `id BIGINT IDENTITY PRIMARY KEY`
- `task_no NVARCHAR(50) NOT NULL`
- `order_id BIGINT NOT NULL`
- `order_item_id BIGINT NULL`
- `printer_id BIGINT NULL`
- `slice_file_id BIGINT NULL`
- `material_id BIGINT NULL`
- `status NVARCHAR(50) NOT NULL DEFAULT 'pending'`
- `priority INT NOT NULL DEFAULT 0`
- `plate_count INT NOT NULL DEFAULT 1`
- `use_ams BIT NOT NULL DEFAULT 0`
- `estimated_minutes INT NULL`
- `started_at DATETIME2(3) NULL`
- `finished_at DATETIME2(3) NULL`
- `failure_reason NVARCHAR(1000) NULL`
- `created_at DATETIME2(3) NOT NULL`
- `updated_at DATETIME2(3) NOT NULL`

状态：

- `pending`：待处理。
- `scheduled`：已排期。
- `printing`：打印中。
- `paused`：暂停。
- `completed`：已完成。
- `failed`：失败。
- `cancelled`：已取消。

### 9.3 `production_schedules` 生产排期表

用途：排期以订单为单位，但可关联多个打印任务。

字段建议：

- `id BIGINT IDENTITY PRIMARY KEY`
- `order_id BIGINT NOT NULL`
- `print_task_id BIGINT NULL`
- `printer_id BIGINT NULL`
- `scheduled_start_at DATETIME2(3) NOT NULL`
- `scheduled_end_at DATETIME2(3) NOT NULL`
- `due_at DATETIME2(3) NULL`
- `priority INT NOT NULL DEFAULT 0`
- `status NVARCHAR(50) NOT NULL DEFAULT 'scheduled'`
- `locked_by BIGINT NULL`
- `locked_at DATETIME2(3) NULL`
- `created_at DATETIME2(3) NOT NULL`
- `updated_at DATETIME2(3) NOT NULL`

约束：

- `scheduled_end_at > scheduled_start_at`。
- 同一打印机同一时间段不能排重叠任务，此规则建议由后端事务校验，数据库可用触发器兜底。

### 9.4 `printer_status_logs` 打印机状态日志表

用途：记录人工维护状态变化，后续兼容设备自动上报。

字段建议：

- `id BIGINT IDENTITY PRIMARY KEY`
- `printer_id BIGINT NOT NULL`
- `from_status NVARCHAR(50) NULL`
- `to_status NVARCHAR(50) NOT NULL`
- `progress DECIMAL(5,2) NULL`
- `nozzle_temp DECIMAL(8,2) NULL`
- `bed_temp DECIMAL(8,2) NULL`
- `remaining_minutes INT NULL`
- `changed_by BIGINT NULL`
- `raw_payload NVARCHAR(MAX) NULL`
- `created_at DATETIME2(3) NOT NULL`

## 10. 库存表

### 10.1 `materials` 材料库存表

字段建议：

- `id BIGINT IDENTITY PRIMARY KEY`
- `name NVARCHAR(100) NOT NULL`
- `material_type NVARCHAR(100) NOT NULL`
- `brand NVARCHAR(100) NULL`
- `color NVARCHAR(100) NULL`
- `diameter DECIMAL(8,2) NULL`
- `stock_weight DECIMAL(18,3) NOT NULL DEFAULT 0`
- `reserved_weight DECIMAL(18,3) NOT NULL DEFAULT 0`
- `safe_stock_weight DECIMAL(18,3) NOT NULL DEFAULT 0`
- `unit_cost DECIMAL(18,2) NULL`
- `status NVARCHAR(50) NOT NULL DEFAULT 'active'`
- `created_at DATETIME2(3) NOT NULL`
- `updated_at DATETIME2(3) NOT NULL`

### 10.2 `finished_goods_inventory` 成品库存表

用途：记录生产完成后的成品库存或待发货成品。

字段建议：

- `id BIGINT IDENTITY PRIMARY KEY`
- `product_id BIGINT NULL`
- `sku_id BIGINT NULL`
- `order_id BIGINT NULL`
- `available_quantity INT NOT NULL DEFAULT 0`
- `reserved_quantity INT NOT NULL DEFAULT 0`
- `in_progress_quantity INT NOT NULL DEFAULT 0`
- `warehouse_location NVARCHAR(200) NULL`
- `updated_at DATETIME2(3) NOT NULL`

### 10.3 `inventory_locks` 库存锁定表

用途：排期或生产前锁定材料、成品、在制品。

字段建议：

- `id BIGINT IDENTITY PRIMARY KEY`
- `lock_type NVARCHAR(50) NOT NULL`
- `order_id BIGINT NULL`
- `print_task_id BIGINT NULL`
- `product_id BIGINT NULL`
- `sku_id BIGINT NULL`
- `material_id BIGINT NULL`
- `quantity INT NULL`
- `weight DECIMAL(18,3) NULL`
- `status NVARCHAR(50) NOT NULL DEFAULT 'locked'`
- `locked_by BIGINT NULL`
- `expires_at DATETIME2(3) NULL`
- `created_at DATETIME2(3) NOT NULL`
- `released_at DATETIME2(3) NULL`

锁定类型：

- `material`：材料。
- `finished_good`：成品。
- `work_in_progress`：在制品。

状态：

- `locked`
- `released`
- `consumed`
- `cancelled`

### 10.4 `material_stock_logs` 材料库存流水表

字段建议：

- `id BIGINT IDENTITY PRIMARY KEY`
- `material_id BIGINT NOT NULL`
- `change_type NVARCHAR(50) NOT NULL`
- `change_weight DECIMAL(18,3) NOT NULL`
- `before_weight DECIMAL(18,3) NULL`
- `after_weight DECIMAL(18,3) NULL`
- `related_order_id BIGINT NULL`
- `related_task_id BIGINT NULL`
- `remark NVARCHAR(1000) NULL`
- `created_by BIGINT NULL`
- `created_at DATETIME2(3) NOT NULL`

变更类型：

- `inbound`：入库。
- `reserve`：锁定。
- `release`：释放。
- `consume`：消耗。
- `loss`：损耗。
- `adjust`：调整。

## 11. 审计与日志表

### 11.1 `operation_logs` 操作日志表

用途：记录后台关键操作。

字段建议：

- `id BIGINT IDENTITY PRIMARY KEY`
- `operator_id BIGINT NULL`
- `operation_type NVARCHAR(100) NOT NULL`
- `target_table NVARCHAR(100) NULL`
- `target_id BIGINT NULL`
- `before_data NVARCHAR(MAX) NULL`
- `after_data NVARCHAR(MAX) NULL`
- `remark NVARCHAR(1000) NULL`
- `created_at DATETIME2(3) NOT NULL`

需要记录的操作：

- 定制审核。
- 报价确认。
- 收款确认。
- 排期调整。
- 打印机状态修改。
- 库存调整。
- 商品上下架。

## 12. 触发器设计路线

### 12.1 触发器使用边界

适合使用触发器：

- 自动更新 `updated_at`。
- 记录关键状态变化日志。
- 防止库存出现负数。
- 打印机状态变化自动写日志。
- 排期重叠的数据库兜底校验。

不建议使用触发器：

- 复杂报价计算。
- 复杂排期算法。
- 自动创建完整订单流程。
- 跨多个业务服务的长事务。

这些逻辑应由 FastAPI / Django 服务层实现。

### 12.2 触发器清单

#### `trg_products_set_updated_at`

触发时机：

- `AFTER UPDATE ON products`

作用：

- 自动更新 `products.updated_at`。

#### `trg_orders_set_updated_at`

触发时机：

- `AFTER UPDATE ON orders`

作用：

- 自动更新 `orders.updated_at`。

#### `trg_custom_requests_set_updated_at`

触发时机：

- `AFTER UPDATE ON custom_requests`

作用：

- 自动更新 `custom_requests.updated_at`。

#### `trg_printers_status_log`

触发时机：

- `AFTER UPDATE ON printers`

作用：

- 当 `printers.status` 变化时，自动写入 `printer_status_logs`。

注意：

- `changed_by` 建议由后端通过 `SESSION_CONTEXT('staff_user_id')` 传入。

#### `trg_materials_no_negative_stock`

触发时机：

- `AFTER UPDATE ON materials`

作用：

- 防止 `stock_weight < 0`。
- 防止 `reserved_weight < 0`。
- 防止 `reserved_weight > stock_weight`。

#### `trg_inventory_locks_material_reserve`

触发时机：

- `AFTER INSERT ON inventory_locks`

作用：

- 当插入 `lock_type = 'material'` 且 `status = 'locked'` 时，增加 `materials.reserved_weight`。
- 写入 `material_stock_logs`。

注意：

- 释放、消耗库存建议通过后端服务显式执行，触发器只处理基础一致性。

#### `trg_production_schedule_no_overlap`

触发时机：

- `AFTER INSERT, UPDATE ON production_schedules`

作用：

- 防止同一打印机的有效排期时间重叠。

有效状态：

- `scheduled`
- `locked`
- `in_progress`

#### `trg_order_payment_confirmed_log`

触发时机：

- `AFTER UPDATE ON orders`

作用：

- 当 `payment_status` 从 `unconfirmed` 变为 `confirmed` 时，写入 `operation_logs`。

#### `trg_product_sales_status_log`

触发时机：

- `AFTER UPDATE ON products`

作用：

- 当 `sales_status` 变化时，写入 `operation_logs`。

## 13. 触发器示例草案

### 13.1 防止材料库存为负

```sql
CREATE TRIGGER trg_materials_no_negative_stock
ON dbo.materials
AFTER UPDATE
AS
BEGIN
    SET NOCOUNT ON;

    IF EXISTS (
        SELECT 1
        FROM inserted
        WHERE stock_weight < 0
           OR reserved_weight < 0
           OR reserved_weight > stock_weight
    )
    BEGIN
        THROW 50001, N'Material stock is invalid.', 1;
    END
END;
```

### 13.2 打印机状态变化日志

```sql
CREATE TRIGGER trg_printers_status_log
ON dbo.printers
AFTER UPDATE
AS
BEGIN
    SET NOCOUNT ON;

    INSERT INTO dbo.printer_status_logs (
        printer_id,
        from_status,
        to_status,
        changed_by,
        created_at
    )
    SELECT
        i.id,
        d.status,
        i.status,
        TRY_CAST(SESSION_CONTEXT(N'staff_user_id') AS BIGINT),
        SYSUTCDATETIME()
    FROM inserted i
    INNER JOIN deleted d ON i.id = d.id
    WHERE ISNULL(i.status, '') <> ISNULL(d.status, '');
END;
```

### 13.3 防止同一打印机排期重叠

```sql
CREATE TRIGGER trg_production_schedule_no_overlap
ON dbo.production_schedules
AFTER INSERT, UPDATE
AS
BEGIN
    SET NOCOUNT ON;

    IF EXISTS (
        SELECT 1
        FROM inserted i
        INNER JOIN dbo.production_schedules s
            ON s.printer_id = i.printer_id
           AND s.id <> i.id
           AND s.status IN ('scheduled', 'locked', 'in_progress')
           AND i.status IN ('scheduled', 'locked', 'in_progress')
           AND i.scheduled_start_at < s.scheduled_end_at
           AND i.scheduled_end_at > s.scheduled_start_at
        WHERE i.printer_id IS NOT NULL
    )
    BEGIN
        THROW 50002, N'Printer schedule time overlaps.', 1;
    END
END;
```

## 14. 索引设计路线

### 14.1 唯一索引

- `users.phone`
- `staff_users.username`
- `orders.order_no`
- `quotes.quote_no`
- `print_tasks.task_no`
- `custom_requests.request_no`

### 14.2 常用查询索引

商品：

- `products(sales_status, is_deleted, sort_order)`
- `product_skus(product_id, status)`
- `product_images(product_id, image_type, sort_order)`

定制：

- `custom_requests(user_id, status, created_at DESC)`
- `custom_requests(status, created_at DESC)`
- `custom_request_reviews(custom_request_id, created_at DESC)`

订单：

- `orders(user_id, created_at DESC)`
- `orders(status, created_at DESC)`
- `orders(order_type, status, created_at DESC)`
- `order_items(order_id)`

生产：

- `printers(status)`
- `print_tasks(order_id, status)`
- `print_tasks(printer_id, status)`
- `production_schedules(printer_id, scheduled_start_at, scheduled_end_at)`
- `production_schedules(order_id)`

库存：

- `materials(material_type, color, status)`
- `inventory_locks(order_id, status)`
- `inventory_locks(material_id, status)`
- `material_stock_logs(material_id, created_at DESC)`

## 15. 视图设计路线

### 15.1 `vw_admin_order_overview`

用途：电脑端订单列表。

包含：

- 订单号。
- 客户信息。
- 订单类型。
- 订单状态。
- 收款状态。
- 总金额。
- 是否已排期。
- 打印任务数量。
- 创建时间。

### 15.2 `vw_printer_dashboard`

用途：打印机集中看板。

包含：

- 打印机信息。
- 当前状态。
- 当前任务。
- 当前订单。
- 今日排期数量。
- 是否异常。

### 15.3 `vw_inventory_overview`

用途：库存中心总览。

包含：

- 材料库存。
- 已锁定重量。
- 可用重量。
- 安全库存。
- 低库存标记。

### 15.4 `vw_sales_overview`

用途：销售状态看板。

包含：

- 上架商品数量。
- 销售中商品数量。
- 下架商品数量。
- 定制需求数量。
- 待审核数量。
- 待报价数量。

## 16. 存储过程设计路线

阶段1不强制使用存储过程，优先由后端服务层控制事务。

可选存储过程：

- `sp_confirm_order_payment`：人工确认收款。
- `sp_lock_material_inventory`：锁定材料库存。
- `sp_release_inventory_lock`：释放库存锁定。
- `sp_consume_material_inventory`：打印完成或失败后消耗材料。
- `sp_create_print_tasks_for_order`：根据订单生成打印任务。

建议：

- 如果后端团队熟悉 SQL Server，可用存储过程封装库存强一致操作。
- 如果后端团队更熟悉 Python，库存操作可以放在服务层事务中，数据库保留触发器兜底。

## 17. 阶段1建表顺序

建议顺序：

1. `users`
2. `staff_users`
3. `product_categories`
4. `materials`
5. `products`
6. `product_images`
7. `product_skus`
8. `printers`
9. `model_files`
10. `custom_requests`
11. `custom_request_reviews`
12. `quotes`
13. `orders`
14. `order_items`
15. `print_tasks`
16. `production_schedules`
17. `finished_goods_inventory`
18. `inventory_locks`
19. `material_stock_logs`
20. `printer_status_logs`
21. `operation_logs`

原因：

- 先建基础主数据。
- 再建销售、定制、报价。
- 再建订单和生产。
- 最后建库存流水、状态日志和审计。

## 18. 阶段1迁移路线

### 第1步：基础结构

- 创建数据库。
- 创建基础表。
- 创建主键、外键、默认值。
- 创建状态 CHECK 约束。

### 第2步：业务主表

- 创建商品、SKU、图片。
- 创建定制需求、文件、审核记录。
- 创建报价、订单、订单明细。

### 第3步：生产与库存

- 创建打印机、打印任务、生产排期。
- 创建材料库存、成品库存、库存锁定、库存流水。

### 第4步：触发器与索引

- 创建库存保护触发器。
- 创建打印机状态日志触发器。
- 创建排期防重叠触发器。
- 创建常用查询索引。

### 第5步：视图与测试数据

- 创建后台看板视图。
- 初始化管理员账号。
- 初始化打印机样例数据。
- 初始化材料样例数据。
- 初始化上架商品样例数据。

## 19. 关键事务设计

### 19.1 上架商品下单后生产

事务步骤：

1. 校验商品 `sales_status = 'on_sale'`。
2. 校验 SKU 可用。
3. 创建 `orders`。
4. 创建 `order_items`。
5. 订单状态为 `submitted`。
6. 等待管理员确认收款。

### 19.2 定制需求提交

事务步骤：

1. 写入 `model_files`。
2. 写入 `custom_requests`。
3. 回写 `custom_requests.slice_file_id`。
4. 状态为 `submitted`。

### 19.3 管理员审核定制需求

事务步骤：

1. 更新 `custom_requests.status`。
2. 写入 `custom_request_reviews`。
3. 如通过审核，状态改为 `quote_pending`。

### 19.4 报价确认与收款确认

报价事务：

1. 写入 `quotes`。
2. 管理员确认 `manual_price`。
3. 客户确认报价后，状态改为 `confirmed`。

收款确认事务：

1. 更新 `orders.payment_status = 'confirmed'`。
2. 更新 `orders.status = 'payment_confirmed'`。
3. 写入 `operation_logs`。

### 19.5 排期与库存锁定

事务步骤：

1. 校验订单已收款确认。
2. 校验打印机可用。
3. 校验排期不重叠。
4. 校验材料可用库存。
5. 写入 `production_schedules`。
6. 写入 `print_tasks`。
7. 写入 `inventory_locks`。
8. 更新订单状态为 `scheduled`。

并发要求：

- 库存锁定、库存释放、库存消耗、成品入库、发货预留、出库确认必须由后端服务层显式事务控制。
- 材料行、成品库存件行、订单行、排期时间窗口必须在事务内使用 SQL Server 行锁保护。
- 管理端多人编辑场景使用 `row_version` 乐观锁，避免后提交覆盖先提交。
- 关键写接口必须使用 `Idempotency-Key`，同一 key 重试返回第一次处理结果。
- 不使用 Python 全局锁或线程锁保证库存、订单、出库等跨请求一致性。
- 详细方案见 `Design/后端并发事务与锁设计方案.md`。

## 20. 数据库验收标准

阶段0数据库设计通过标准：

- 表结构能覆盖上架商品和个性化定制两条销售线。
- 定制表单字段已经落到 `custom_requests`。
- 切片文件已经落到 `model_files`。
- 报价支持预计报价和人工报价。
- 订单支持人工收款确认。
- 排期以订单为单位，并支持一单多任务。
- 打印机状态可人工维护并记录日志。
- 库存支持材料、成品、在制品和库存锁定。
- 触发器边界清晰，没有把复杂业务流程塞进数据库。
- 阶段1可以据此开始编写迁移脚本。

## 21. 下一步

1. 根据本路线图输出 SQL Server ER 图。
2. 根据表设计输出第一版 `CREATE TABLE` 脚本。
3. 根据触发器清单输出第一版触发器脚本。
4. 用样例数据验证上架商品下单、定制审核、报价、收款确认、排期、库存锁定。
5. 再根据 FastAPI / Django ORM 适配情况微调字段命名和外键策略。
