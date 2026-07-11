# 已过时：后端 API 与数据库详细设计路线图

> 文档状态：历史阶段路线图。当前端口、仓库发货、优惠券、账号体系和 API 契约以 `Design/全流程系统与API设计文档.md` 及当前 OpenAPI 为准。

## 1. 文档目标

本文件面向后端和数据库开发，基于阶段0已确认需求，设计阶段1可落地的 API 与 SQL Server 数据库路线。

阶段1目标：

- 本地运行 Python 后端服务。
- 使用 Caddy 将外部请求映射到本地后端 API。
- 使用 SQL Server 作为核心数据库。
- 支撑 Flutter 手机 APP 客户侧。
- 支撑电脑端内部管理系统。
- 支撑上架商品下单后生产。
- 支撑个性化定制提交切片文件。
- 支撑管理员审核、报价、线下收款确认、订单排期、打印任务、库存管理。
- 阶段1不接在线支付、不接物流、不接打印机自动控制。

## 2. 后端服务边界

### 2.1 推荐服务结构

阶段1建议先做一个 FastAPI 主服务，Django Admin 可作为后续补充。

```text
backend/
  app/
    main.py
    api/
      app_routes/
      admin_routes/
    core/
      config.py
      security.py
      errors.py
    db/
      session.py
      models/
      migrations/
    services/
      product_service.py
      custom_request_service.py
      order_service.py
      quote_service.py
      schedule_service.py
      inventory_service.py
      printer_service.py
      file_service.py
    schemas/
    utils/
  scripts/
  tests/
```

建议阶段1先统一使用 FastAPI：

- APP API：`/api/v1/app/*`
- 管理端 API：`/api/v1/admin/*`
- 文件 API：`/api/files/*`
- 健康检查：`/health`

Django 的定位：

- 后续可用于 Django Admin、内部配置后台、数据修复后台。
- 阶段1不强制引入，避免 FastAPI 与 Django 双 ORM 迁移冲突。

### 2.2 本地运行端口

建议：

```text
FastAPI 本地端口：127.0.0.1:8000
SQL Server：127.0.0.1:1433 或局域网 SQL Server
Caddy 对外端口：80 / 443
```

本地启动命令示例：

```powershell
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

## 3. Caddy API 暴露方案

### 3.1 Caddy 反向代理目标

外部访问：

```text
https://api.example.com
```

映射到本地：

```text
127.0.0.1:8000
```

### 3.2 Caddyfile 草案

```caddyfile
api.example.com {
    encode gzip

    header {
        Strict-Transport-Security "max-age=31536000;"
        X-Content-Type-Options "nosniff"
        X-Frame-Options "DENY"
        Referrer-Policy "strict-origin-when-cross-origin"
    }

    request_body {
        max_size 300MB
    }

    log {
        output file ./logs/access.log
        format json
    }

    @api path /api/*
    reverse_proxy @api 127.0.0.1:8000

    @files path /files/*
    reverse_proxy @files 127.0.0.1:8000 {
        transport http {
            read_timeout 10m
            write_timeout 10m
        }
    }

    @health path /health
    reverse_proxy @health 127.0.0.1:8000
}
```

### 3.3 CORS 策略

如果 Flutter Web 或调试端需要跨域，后端配置 CORS：

```text
允许来源：
- http://localhost:*
- http://127.0.0.1:*
- https://你的前端域名

允许方法：
- GET
- POST
- PATCH
- PUT
- DELETE
- OPTIONS

允许 Header：
- Authorization
- Content-Type
- X-Request-Id
```

生产环境不要使用 `allow_origins=["*"]` 搭配凭证。

## 4. API 通用规范

### 4.1 路径命名

```text
/api/v1/app/...    客户 APP API
/api/v1/admin/...  内部管理 API
/api/files/...     文件访问或上传相关 API
/health            健康检查
```

### 4.2 响应结构

成功响应：

```json
{
  "code": "OK",
  "message": "success",
  "data": {}
}
```

分页响应：

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "items": [],
    "page": 1,
    "page_size": 20,
    "total": 0
  }
}
```

失败响应：

```json
{
  "code": "VALIDATION_ERROR",
  "message": "切片文件不能为空",
  "details": {}
}
```

### 4.3 HTTP 状态码

- `200`：成功。
- `201`：创建成功。
- `400`：参数错误。
- `401`：未登录或 token 无效。
- `403`：无权限。
- `404`：资源不存在。
- `409`：状态冲突，例如排期重叠、库存不足。
- `422`：字段校验失败。
- `500`：服务端错误。

### 4.4 认证方式

阶段1建议使用 JWT：

```text
Authorization: Bearer <token>
```

Token 分类：

- 客户 token：访问 `/api/v1/app/*`
- 管理员 token：访问 `/api/v1/admin/*`

不要混用客户和管理员 token。

### 4.5 幂等要求

关键写接口必须支持幂等，客户端通过 Header 传入：

```text
Idempotency-Key: uuid
```

必须强制幂等的接口：

- 创建上架商品订单。
- 创建定制需求。
- 客户确认报价。
- 管理员确认收款。
- 创建排期。
- 创建打印任务。
- 库存入库、锁定、释放、消耗。

后端规则：

- 相同用户、相同接口、相同 `Idempotency-Key` 返回第一次处理结果。
- 相同 key 但请求体 hash 不同，返回 `409 IDEMPOTENCY_KEY_CONFLICT`。
- 幂等记录建议保存 24 到 72 小时。

### 4.6 请求追踪

建议所有请求支持：

```text
X-Request-Id: 客户端生成或 Caddy/后端生成
```

后端日志必须记录：

- `request_id`
- `method`
- `path`
- `user_id`
- `staff_user_id`
- `status_code`
- `duration_ms`

## 5. APP 端 API 设计

### 5.1 客户登录

```text
POST /api/v1/app/auth/login
```

阶段1可先使用手机号 + 验证码模拟登录。

请求：

```json
{
  "phone": "13800000000",
  "code": "123456"
}
```

响应：

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "access_token": "jwt",
    "token_type": "Bearer",
    "user": {
      "id": 1,
      "phone": "13800000000",
      "nickname": "用户"
    }
  }
}
```

### 5.2 上架商品列表

```text
GET /api/v1/app/products
```

查询参数：

```text
category_id
keyword
page
page_size
```

规则：

- 只返回 `sales_status = on_sale`。
- 只返回 `production_mode = make_to_order`。

响应核心字段：

```json
{
  "items": [
    {
      "id": 1,
      "name": "龙形摆件",
      "cover_image_url": "https://...",
      "base_price": 99.00,
      "sales_status": "on_sale",
      "production_mode": "make_to_order"
    }
  ],
  "page": 1,
  "page_size": 20,
  "total": 1
}
```

### 5.3 上架商品详情

```text
GET /api/v1/app/products/{product_id}
```

响应包含：

- 商品基本信息。
- 展示图。
- SKU 列表。
- 下单后生产说明。

### 5.4 商品图片

```text
GET /api/v1/app/products/{product_id}/images
```

响应：

```json
{
  "items": [
    {
      "id": 1,
      "image_url": "https://...",
      "image_type": "cover",
      "sort_order": 0
    }
  ]
}
```

### 5.5 创建上架商品订单

```text
POST /api/v1/app/orders/listed-product
```

请求：

```json
{
  "order_type": "listed_product",
  "items": [
    {
      "sku_id": 10,
      "quantity": 2,
      "custom_note": "希望颜色偏深"
    }
  ],
  "customer_note": "不急"
}
```

后端规则：

- 校验 SKU 存在且启用。
- 校验商品为销售中。
- 校验 `Idempotency-Key`。
- 生成订单。
- 订单状态为 `submitted`。
- 支付状态为 `unconfirmed`。
- 不扣成品库存。
- 暂不自动排期。

响应：

```json
{
  "order_no": "OD202607070001",
  "status": "submitted",
  "payment_status": "unconfirmed",
  "total_amount": 198.00
}
```

### 5.6 上传切片文件

```text
POST /api/v1/app/files/upload
```

请求类型：

```text
multipart/form-data
```

字段：

- `file`：必填。
- `file_usage`：`slice_file`。

支持格式：

- `.gcode`
- `.3mf`
- `.bgcode`
- `.zip`
- `.stl`
- `.obj`
- `.step`
- `.stp`
- `.fbx`

限制建议：

- 阶段1单文件最大 300 MB，Caddy 和 FastAPI 必须保持一致。
- 后续增加分片上传。
- 用户最多有 10 个待处理状态的表单。
- 文件不直接暴露真实存储路径。
- 下载必须走鉴权接口或短期签名 URL。

响应：

```json
{
  "file_id": 1001,
  "file_name": "part.3mf",
  "file_ext": ".3mf",
  "file_size": 1024000,
  "is_slice_file": true
}
```

### 5.7 创建个性化定制需求

```text
POST /api/v1/app/custom-requests
```

请求：

```json
{
  "slice_file_id": 1001,
  "requested_print_time": "2026-07-10T10:00:00",
  "preferred_printer_id": 3,
  "preferred_printer_model": "Bambu Lab X1C",
  "filament_color": "黑色",
  "filament_type": "PLA",
  "use_ams": true,
  "plate_count": 2
}
```

必填：

- `slice_file_id`
- `use_ams`
- `plate_count`

后端规则：

- 校验文件归属当前用户。
- 校验文件类型为切片文件。
- 校验 `Idempotency-Key`。
- `plate_count > 0`。
- 创建定制需求，状态为 `submitted`。

响应：

```json
{
  "id": 2001,
  "request_no": "CR202607070001",
  "status": "submitted"
}
```

### 5.8 定制需求详情

```text
GET /api/v1/app/custom-requests/{id}
```

规则：

- 客户只能查看自己的定制需求。

### 5.9 客户补充定制信息

```text
PATCH /api/v1/app/custom-requests/{id}
```

允许状态：

- `need_more_info`

可更新字段：

- `slice_file_id`
- `requested_print_time`
- `preferred_printer_id`
- `preferred_printer_model`
- `filament_color`
- `filament_type`
- `use_ams`
- `plate_count`

更新后状态：

- `submitted`

### 5.10 报价详情

```text
GET /api/v1/app/quotes/{quote_id}
```

规则：

- 只能查看自己的报价。

### 5.11 客户确认报价

```text
POST /api/v1/app/quotes/{quote_id}/confirm
```

后端规则：

- 报价状态必须为 `sent`。
- 校验 `Idempotency-Key`。
- 更新报价状态为 `confirmed`。
- 定制需求状态更新为 `quote_confirmed`。
- 如订单未创建，可创建定制订单。
- 订单支付状态仍为 `unconfirmed`，等待管理员线下收款确认。

## 6. 管理端 API 设计

### 6.1 管理员登录

```text
POST /api/v1/admin/auth/login
```

请求：

```json
{
  "username": "admin",
  "password": "password"
}
```

响应：

```json
{
  "access_token": "jwt",
  "token_type": "Bearer",
  "staff_user": {
    "id": 1,
    "username": "admin",
    "role": "admin"
  }
}
```

### 6.2 后台总览

```text
GET /api/v1/admin/dashboard
```

返回：

- 待审核定制数。
- 待报价数。
- 待收款确认订单数。
- 待排期订单数。
- 打印中任务数。
- 异常打印机数。
- 低库存材料数。

### 6.3 商品管理

#### 商品列表

```text
GET /api/v1/admin/products
```

查询参数：

- `keyword`
- `sales_status`
- `category_id`
- `page`
- `page_size`

#### 创建商品

```text
POST /api/v1/admin/products
```

请求：

```json
{
  "category_id": 1,
  "name": "龙形摆件",
  "description": "下单后生产",
  "base_price": 99.00,
  "sales_status": "draft",
  "production_mode": "make_to_order",
  "supports_custom_note": true
}
```

#### 更新商品

```text
PATCH /api/v1/admin/products/{product_id}
```

#### 上传商品图片

```text
POST /api/v1/admin/products/{product_id}/images
```

请求：

```text
multipart/form-data
file
image_type=cover/detail/printed_sample/scene
sort_order=0
```

#### 修改销售状态

```text
PATCH /api/v1/admin/products/{product_id}/sales-status
```

请求：

```json
{
  "sales_status": "on_sale"
}
```

#### SKU 管理

```text
GET    /api/v1/admin/products/{product_id}/skus
POST   /api/v1/admin/products/{product_id}/skus
PATCH  /api/v1/admin/product-skus/{sku_id}
```

SKU 请求：

```json
{
  "material_id": 1,
  "color": "黑色",
  "size_label": "15cm",
  "precision_level": "0.16mm",
  "price": 99.00,
  "min_quantity": 1,
  "max_quantity": 99,
  "status": "active"
}
```

### 6.4 定制审核

#### 定制需求列表

```text
GET /api/v1/admin/custom-requests
```

查询参数：

- `status`
- `keyword`
- `created_from`
- `created_to`
- `page`
- `page_size`

#### 定制需求详情

```text
GET /api/v1/admin/custom-requests/{id}
```

返回：

- 客户信息。
- 切片文件。
- AMS。
- 盘数。
- 指定打印机/型号。
- 指定耗材颜色/类型。
- 审核记录。
- 报价记录。
- 关联订单。

#### 审核定制需求

```text
PATCH /api/v1/admin/custom-requests/{id}/review
```

请求：

```json
{
  "action": "approve",
  "remark": "文件可打印"
}
```

动作：

- `start_review`：开始审核，状态改为 `reviewing`。
- `need_more_info`：需要补充信息。
- `reject`：不可制作。
- `approve`：审核通过，进入 `quote_pending`。

后端规则：

- 只有管理员可操作。
- 每次操作写入 `custom_request_reviews`。

### 6.5 报价管理

#### 创建报价

```text
POST /api/v1/admin/custom-requests/{id}/quote
```

请求：

```json
{
  "estimated_price": 120.00,
  "manual_price": 150.00,
  "estimated_days": 3,
  "material_cost": 40.00,
  "machine_cost": 30.00,
  "labor_cost": 50.00,
  "post_processing_cost": 30.00,
  "remark": "按两盘打印估算"
}
```

后端规则：

- 定制需求状态必须为 `quote_pending` 或 `quoted`。
- 创建报价状态为 `sent`。
- 定制需求状态更新为 `quoted`。

#### 报价列表

```text
GET /api/v1/admin/quotes
```

#### 报价详情

```text
GET /api/v1/admin/quotes/{quote_id}
```

### 6.6 订单管理

#### 订单列表

```text
GET /api/v1/admin/orders
```

查询参数：

- `order_type`
- `status`
- `payment_status`
- `keyword`
- `page`
- `page_size`

#### 订单详情

```text
GET /api/v1/admin/orders/{order_id}
```

#### 修改订单状态

```text
PATCH /api/v1/admin/orders/{order_id}/status
```

请求：

```json
{
  "status": "reviewing",
  "remark": "开始处理"
}
```

#### 人工确认收款

```text
POST /api/v1/admin/orders/{order_id}/payment-confirm
```

请求：

```json
{
  "remark": "已线下收款"
}
```

后端规则：

- 更新 `payment_status = confirmed`。
- 校验 `Idempotency-Key`。
- 更新 `payment_confirmed_by`。
- 更新 `payment_confirmed_at`。
- 订单状态更新为 `payment_confirmed`。
- 写入 `operation_logs`。
- 收款确认后才允许排期。

### 6.7 打印机管理

```text
GET    /api/v1/admin/printers
POST   /api/v1/admin/printers
GET    /api/v1/admin/printers/{printer_id}
PATCH  /api/v1/admin/printers/{printer_id}
PATCH  /api/v1/admin/printers/{printer_id}/status
```

修改打印机状态：

```json
{
  "status": "idle",
  "remark": "人工确认空闲"
}
```

状态变化：

- 后端写操作日志。
- 数据库触发器写 `printer_status_logs`。

### 6.8 排期管理

#### 排期列表

```text
GET /api/v1/admin/production-schedule-orders
```

查询参数：

- `printer_id`
- `order_id`
- `status`
- `start_date`
- `end_date`

#### 创建排期

```text
POST /api/v1/admin/production-schedule-orders
```

请求：

```json
{
  "order_id": 3001,
  "planned_start_at": "2026-07-10T10:00:00",
  "planned_end_at": "2026-07-10T18:00:00",
  "due_at": "2026-07-11T18:00:00",
  "priority": 10,
  "items": [
    {
      "print_task_id": 5001,
      "printer_id": 1,
      "scheduled_start_at": "2026-07-10T10:00:00",
      "scheduled_end_at": "2026-07-10T14:00:00"
    }
  ],
  "material_locks": [
    {
      "material_id": 1,
      "weight": 250.5
    }
  ]
}
```

后端规则：

- 订单必须 `payment_status = confirmed`。
- 校验 `Idempotency-Key`。
- 校验打印机非 `maintenance`、`offline`。
- 校验同打印机时间不重叠。
- 校验材料可用库存。
- 创建 `production_schedule_orders`。
- 创建 `production_schedule_items`。
- 创建或关联 `print_tasks`。
- 创建 `inventory_locks`。
- 更新订单状态为 `scheduled`。

#### 更新排期

```text
PATCH /api/v1/admin/production-schedule-orders/{schedule_order_id}
```

### 6.9 打印任务管理

```text
GET   /api/v1/admin/print-tasks
POST  /api/v1/admin/print-tasks
PATCH /api/v1/admin/print-tasks/{task_id}/status
```

打印任务状态更新：

```json
{
  "status": "printing",
  "remark": "开始打印"
}
```

规则：

- 状态改为 `printing` 时，打印机状态可同步改为 `printing`。
- 状态改为 `completed` 时，进入质检或成品入库。
- 状态改为 `failed` 时，记录失败原因，库存可记录损耗。

### 6.10 库存管理

#### 库存总览

```text
GET /api/v1/admin/inventory/overview
```

#### 材料列表

```text
GET /api/v1/admin/inventory/materials
```

#### 创建材料

```text
POST /api/v1/admin/inventory/materials
```

请求：

```json
{
  "name": "PLA 黑色",
  "material_type": "PLA",
  "brand": "Bambu",
  "color": "黑色",
  "diameter": 1.75,
  "stock_weight": 1000,
  "safe_stock_weight": 200,
  "unit_cost": 0.08
}
```

#### 材料入库/调整

```text
POST /api/v1/admin/inventory/materials/{material_id}/stock-logs
```

请求：

```json
{
  "change_type": "inbound",
  "change_weight": 1000,
  "remark": "采购入库"
}
```

#### 库存锁定列表

```text
GET /api/v1/admin/inventory/locks
```

#### 成品库存

```text
GET /api/v1/admin/inventory/finished-goods
```

## 7. 状态流转设计

### 7.1 定制需求状态

```text
submitted
  -> reviewing
  -> need_more_info -> submitted
  -> rejected
  -> quote_pending
  -> quoted
  -> quote_confirmed
  -> payment_confirmed
  -> scheduled
```

### 7.2 订单状态

```text
submitted
  -> reviewing
  -> quoted
  -> quote_confirmed
  -> payment_confirmed
  -> scheduled
  -> printing
  -> post_processing
  -> quality_check
  -> completed
  -> cancelled
```

### 7.3 打印任务状态

```text
pending
  -> scheduled
  -> printing
  -> paused
  -> completed
  -> failed
  -> cancelled
```

### 7.4 打印机状态

```text
idle
printing
paused
completed
error
offline
maintenance
```

阶段1由管理员人工维护。

## 8. 数据库表清单

### 8.1 基础表

- `users`
- `staff_users`
- `operation_logs`

### 8.2 商品表

- `product_categories`
- `products`
- `product_images`
- `product_skus`

### 8.3 定制与文件表

- `model_files`
- `custom_requests`
- `custom_request_reviews`
- `quotes`

### 8.4 订单表

- `orders`
- `order_items`

### 8.5 生产表

- `printers`
- `print_tasks`
- `production_schedule_orders`
- `production_schedule_items`
- `printer_status_logs`

### 8.6 库存表

- `materials`
- `finished_goods_inventory`
- `inventory_locks`
- `material_stock_logs`
- `idempotency_keys`

## 9. 核心字段设计

### 9.1 `custom_requests`

必须包含：

- `slice_file_id`
- `requested_print_time`
- `preferred_printer_id`
- `preferred_printer_model`
- `filament_color`
- `filament_type`
- `use_ams`
- `plate_count`
- `status`
- `reviewer_id`
- `reviewed_at`
- `review_remark`

约束：

- `use_ams` 不允许为空。
- `plate_count > 0`。
- 提交时必须有关联切片文件。

### 9.2 `orders`

必须包含：

- `order_no`
- `user_id`
- `order_type`
- `status`
- `total_amount`
- `payment_status`
- `payment_confirmed_by`
- `payment_confirmed_at`

说明：

- 阶段1没有在线支付流水表。
- 收款由管理员确认。

### 9.3 `production_schedule_orders`

必须包含：

- `order_id`
- `schedule_no`
- `planned_start_at`
- `planned_end_at`
- `due_at`
- `priority`
- `status`
- `created_by`
- `row_version`

约束：

- `planned_end_at > planned_start_at`。
- 一个订单同一时间只允许有一个有效排期主表。

### 9.4 `production_schedule_items`

必须包含：

- `schedule_order_id`
- `print_task_id`
- `printer_id`
- `scheduled_start_at`
- `scheduled_end_at`
- `status`
- `sort_order`
- `row_version`

约束：

- `scheduled_end_at > scheduled_start_at`。
- 同一打印机不能有重叠的有效排期明细。

### 9.5 `inventory_locks`

必须包含：

- `lock_type`
- `order_id`
- `print_task_id`
- `material_id`
- `quantity`
- `weight`
- `status`

说明：

- 上架商品和定制订单排期前都可以锁定材料。
- 阶段1重点锁定材料库存。

### 9.6 `idempotency_keys`

必须包含：

- `scope`
- `idempotency_key`
- `request_hash`
- `response_body`
- `status_code`
- `resource_type`
- `resource_id`
- `created_by_user_id`
- `created_by_staff_id`
- `expires_at`

唯一索引：

- `(scope, idempotency_key)`

用途：

- 防止重复下单。
- 防止重复确认报价。
- 防止重复确认收款。
- 防止重复创建排期和库存锁定。

## 10. 触发器设计

### 10.1 触发器边界

触发器负责：

- 数据一致性兜底。
- 状态变化日志。
- 防止负库存。
- 防止排期重叠。
- 自动更新时间。

触发器不负责：

- 报价计算。
- 自动排产。
- 订单创建。
- 审核业务判断。
- 文件解析。

### 10.2 必做触发器

#### `trg_materials_no_negative_stock`

作用：

- 防止 `stock_weight < 0`。
- 防止 `reserved_weight < 0`。
- 防止 `reserved_weight > stock_weight`。

#### `trg_printers_status_log`

作用：

- 当打印机状态变化时写入 `printer_status_logs`。

#### `trg_production_schedule_no_overlap`

作用：

- 防止 `production_schedule_items` 中同一打印机同一时间段排期重叠。

#### `trg_orders_payment_confirm_log`

作用：

- 当订单 `payment_status` 从 `unconfirmed` 变为 `confirmed` 时写入 `operation_logs`。

### 10.3 可选触发器

- `trg_products_sales_status_log`
- `trg_custom_requests_status_log`
- `trg_print_tasks_status_log`
- `trg_updated_at_common`

如果 ORM 层统一维护 `updated_at`，可不做通用 `updated_at` 触发器。

## 11. 索引设计

### 11.1 唯一索引

- `users(phone)`
- `staff_users(username)`
- `orders(order_no)`
- `quotes(quote_no)`
- `print_tasks(task_no)`
- `custom_requests(request_no)`

### 11.2 查询索引

APP 常用：

- `products(sales_status, is_deleted, sort_order)`
- `product_skus(product_id, status)`
- `product_images(product_id, image_type, sort_order)`
- `orders(user_id, created_at DESC)`
- `custom_requests(user_id, status, created_at DESC)`

管理端常用：

- `orders(status, payment_status, created_at DESC)`
- `orders(order_type, status, created_at DESC)`
- `custom_requests(status, created_at DESC)`
- `quotes(status, created_at DESC)`
- `printers(status)`
- `print_tasks(order_id, status)`
- `print_tasks(printer_id, status)`
- `production_schedule_orders(order_id, status)`
- `production_schedule_items(printer_id, scheduled_start_at, scheduled_end_at)`
- `idempotency_keys(scope, idempotency_key)`
- `inventory_locks(order_id, status)`
- `materials(material_type, color, status)`

## 12. 数据库迁移路线

### 12.1 第1批：基础账号与商品

- `users`
- `staff_users`
- `product_categories`
- `products`
- `product_images`
- `product_skus`

### 12.2 第2批：文件与定制

- `model_files`
- `custom_requests`
- `custom_request_reviews`
- `quotes`

### 12.3 第3批：订单

- `orders`
- `order_items`

### 12.4 第4批：生产

- `printers`
- `print_tasks`
- `production_schedule_orders`
- `production_schedule_items`
- `printer_status_logs`

### 12.5 第5批：库存与审计

- `materials`
- `finished_goods_inventory`
- `inventory_locks`
- `material_stock_logs`
- `operation_logs`
- `idempotency_keys`

### 12.6 第6批：触发器、索引、视图

- 库存保护触发器。
- 打印机状态日志触发器。
- 排期重叠保护触发器。
- 常用查询索引。
- 管理端看板视图。

## 13. 关键事务设计

### 13.1 上架商品下单

事务：

1. 查询 SKU 并加锁。
2. 校验商品销售中。
3. 计算订单金额。
4. 创建订单。
5. 创建订单明细。
6. 返回订单号。

不做：

- 不扣现货库存。
- 不自动排期。
- 不在线支付。

### 13.2 定制需求提交

事务：

1. 校验切片文件归属。
2. 创建定制需求。
3. 关联 `slice_file_id`。
4. 状态为 `submitted`。

### 13.3 定制审核

事务：

1. 校验管理员权限。
2. 更新定制需求状态。
3. 写入审核记录。
4. 必要时写操作日志。

### 13.4 报价确认

事务：

1. 管理员创建报价。
2. 客户确认报价。
3. 创建或更新订单。
4. 订单保持 `payment_status = unconfirmed`。

### 13.5 人工收款确认

事务：

1. 校验订单存在。
2. 校验当前状态允许确认收款。
3. 更新 `payment_status = confirmed`。
4. 更新 `payment_confirmed_by` 和 `payment_confirmed_at`。
5. 更新订单状态为 `payment_confirmed`。
6. 写操作日志。

### 13.6 排期和库存锁定

事务：

1. 校验订单已收款确认。
2. 校验打印机状态。
3. 校验排期时间不重叠。
4. 校验材料可用重量。
5. 使用 `UPDLOCK, HOLDLOCK` 锁定材料行。
6. 创建排期主表 `production_schedule_orders`。
7. 创建排期明细 `production_schedule_items`。
8. 创建或关联打印任务。
9. 创建库存锁定。
10. 更新材料 `reserved_weight`。
11. 更新订单状态为 `scheduled`。

## 14. 强一致性补充规则

### 14.1 库存锁定必须加数据库行锁

锁定材料库存时，后端服务层必须在同一事务中执行行锁查询：

```sql
SELECT *
FROM dbo.materials WITH (UPDLOCK, HOLDLOCK)
WHERE id = @material_id;
```

然后检查：

```text
stock_weight - reserved_weight >= request_weight
```

再更新 `reserved_weight` 并写入 `inventory_locks`、`material_stock_logs`。

### 14.2 状态变更必须通过状态机

所有状态更新必须经过服务层状态机校验，禁止接口直接任意 PATCH 状态。

非法状态迁移统一返回：

```text
409 INVALID_STATE_TRANSITION
```

### 14.3 核心表建议增加乐观锁

以下表建议增加：

```text
row_version ROWVERSION
```

适用表：

- `orders`
- `custom_requests`
- `quotes`
- `printers`
- `print_tasks`
- `production_schedule_orders`
- `production_schedule_items`
- `materials`
- `inventory_locks`

### 14.4 触发器边界收紧

阶段1不建议使用触发器统一维护所有表的 `updated_at`，避免 SQL Server 触发器递归、ORM 行版本混乱和排查困难。

阶段1必做触发器只保留：

- 防负库存。
- 打印机状态日志。
- 排期明细重叠兜底。
- 关键状态审计。

## 15. 后端开发顺序

### 第1阶段：基础工程

- FastAPI 项目初始化。
- SQL Server 连接。
- Alembic 迁移。
- JWT 认证。
- 统一响应结构。
- 统一错误处理。
- Caddy 反向代理验证。

### 第2阶段：商品与文件

- 商品分类。
- 商品管理。
- 商品图片上传。
- SKU 管理。
- APP 商品列表和详情。
- 切片文件上传。

### 第3阶段：定制与报价

- 定制需求提交。
- 管理员审核。
- 审核记录。
- 报价创建。
- 客户确认报价。

### 第4阶段：订单与收款确认

- 上架商品订单。
- 定制订单。
- 订单列表和详情。
- 人工收款确认。
- 操作日志。

### 第5阶段：打印机、排期、库存

- 打印机管理。
- 打印机状态人工维护。
- 材料库存管理。
- 排期管理。
- 打印任务管理。
- 库存锁定。

## 16. Caddy 联调验收

本地后端：

```text
http://127.0.0.1:8000/health
```

Caddy 暴露：

```text
https://api.example.com/health
https://api.example.com/api/v1/app/products
https://api.example.com/api/v1/admin/dashboard
```

验收标准：

- Caddy 能反代 `/api/*` 到 FastAPI。
- HTTPS 可用。
- 文件上传可通过 Caddy。
- 大文件上传限制已明确。
- 后端日志能看到真实请求来源。
- Flutter APP 能通过公网 API 调用。

## 17. 接口验收用例

### 16.1 上架商品闭环

1. 管理员创建商品。
2. 管理员上传商品图。
3. 管理员创建 SKU。
4. 管理员上架商品。
5. APP 查询商品列表。
6. APP 创建订单。
7. 重复提交同一个 `Idempotency-Key` 不会产生重复订单。
8. 管理员确认收款。
9. 管理员创建排期主表和排期明细。
10. 管理员创建打印任务。

### 16.2 定制闭环

1. APP 上传切片文件。
2. APP 创建定制需求。
3. 管理员审核通过。
4. 管理员创建报价。
5. APP 确认报价。
6. 管理员确认收款。
7. 管理员创建排期主表和排期明细。
8. 管理员推进打印任务状态。

### 16.3 库存闭环

1. 管理员创建材料。
2. 管理员材料入库。
3. 排期时锁定材料。
4. 打印完成后消耗材料。
5. 打印失败后记录损耗。
6. 库存不能出现负数。
7. 并发排期不能超锁材料库存。

## 18. 阶段1交付物

- FastAPI 后端工程。
- SQL Server 建表脚本。
- SQL Server 触发器脚本。
- Alembic 迁移脚本。
- API OpenAPI 文档。
- Caddyfile。
- Postman / Apifox 接口集合。
- 初始化数据脚本。
- 后端部署说明。

## 19. 下一步

建议后续按以下顺序继续产出：

1. `SQLServer建表脚本.sql`
2. `SQLServer触发器脚本.sql`
3. `API接口清单-Apifox导入版.md`
4. `Caddyfile`
5. `FastAPI项目结构与开发任务拆分.md`

## 20. 扩展路线：账号、仓库、发货出库

根据后续新增需求，阶段1需要追加以下扩展：

- APP 登录从手机号验证码 Demo 改为邮箱 + 密码。
- APP 支持客户自行注册。
- 后台支持客户账号增删改查、禁用、重置密码。
- 后台支持管理员账号增删改查、禁用、重置密码。
- 增加仓库和库位管理。
- 商品生产完成后支持转移入库。
- 订单全部商品生产并入库后，状态自动变为 `ready_to_ship`。
- 一个订单支持一个或多个快递单号。
- 填写快递单后支持批量出库。

详细设计见：

```text
Design/仓库管理与账号体系扩展路线图.md
```

## 21. 并发、事务与锁设计补充

后端进入多用户访问后，性能和数据安全不能主要依赖 Python 多线程解决。阶段1应采用以下原则：

- FastAPI / Uvicorn 负责 HTTP 并发。
- SQL Server 事务、行锁、唯一约束、`rowversion` 和幂等表负责核心数据一致性。
- Python 线程或后台任务只处理图片缩略图、文件扫描、通知、报表、设备轮询等非关键长耗时任务。
- 库存、排期、入库、发货、出库、收款确认等关键写接口必须使用短事务。
- 关键写接口必须使用 `Idempotency-Key`，防止 Flutter 重试、用户连点、Caddy 超时重放造成重复写入。
- 成品库存件预留、材料库存锁定、出库确认必须使用数据库行锁，不使用 Python 内存锁。
- 管理端多人编辑商品、SKU、打印机、订单备注等资料时使用 `rowversion` 做乐观锁。

优先落地顺序：

1. 新增统一事务 helper，把关键写接口逐步迁移到 service 层。
2. 新增 `idempotency_keys` 表和幂等服务。
3. 给材料库存、成品库存件、排期时间窗口补 SQL Server 行锁。
4. 给核心管理表补 `rowversion` 更新校验。
5. 增加 SQL Server 死锁 1205 的有限重试和日志。
6. 将图片处理、文件扫描、报表导出、设备轮询迁移到后台任务。

详细设计见：

```text
Design/后端并发事务与锁设计方案.md
```
