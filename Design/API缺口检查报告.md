# API 缺口检查报告

检查对象：`D:/openapi.json`  
检查时间：2026-07-07  
当前 API 标题：`3D Print Farm API`  
当前 API 版本：`0.1.0`

## 1. 总体结论

当前 OpenAPI 已经能反映阶段1后端的主要接口骨架，说明 FastAPI 文档导出是可用的。

但它还不是一份适合前端直接联调或交付的完整 API 文档，主要问题是：

- 已暴露 40 个接口，但所有 `200` 响应 schema 都是空对象。
- 关键写接口虽然有 `Idempotency-Key`，但 OpenAPI 中标记为非必填。
- 管理端缺少定制审核、报价管理、打印任务管理等核心接口。
- 客户端缺少订单列表/详情、定制需求列表等查询接口。
- 多数列表接口只有分页参数，缺少状态、关键词、时间范围等筛选参数。
- 文件接口只有上传，没有下载、访问鉴权、文件详情接口。
- 状态更新接口过于通用，OpenAPI 没有约束允许的状态枚举。

当前状态适合继续后端开发，但不建议直接交给 APP/管理端前端作为最终接口契约。

## 2. 当前已暴露接口概览

### 2.1 客户 APP 端

| Method | Path | 说明 |
|---|---|---|
| POST | `/api/v1/app/auth/login` | 客户登录 |
| GET | `/api/v1/app/products` | 上架商品列表 |
| GET | `/api/v1/app/products/{product_id}` | 上架商品详情 |
| GET | `/api/v1/app/products/{product_id}/images` | 商品图片 |
| POST | `/api/v1/app/orders/listed-product` | 创建上架商品订单 |
| POST | `/api/v1/app/files/upload` | 上传切片/模型文件 |
| POST | `/api/v1/app/custom-requests` | 创建定制需求 |
| GET | `/api/v1/app/custom-requests/{request_id}` | 定制需求详情 |
| PATCH | `/api/v1/app/custom-requests/{request_id}` | 补充定制需求 |
| GET | `/api/v1/app/quotes/{quote_id}` | 报价详情 |
| POST | `/api/v1/app/quotes/{quote_id}/confirm` | 客户确认报价 |

### 2.2 管理端

| Method | Path | 说明 |
|---|---|---|
| POST | `/api/v1/admin/auth/login` | 管理员登录 |
| GET | `/api/v1/admin/dashboard` | 后台总览 |
| GET | `/api/v1/admin/products` | 商品列表 |
| POST | `/api/v1/admin/products` | 创建商品 |
| PATCH | `/api/v1/admin/products/{product_id}` | 更新商品 |
| POST | `/api/v1/admin/products/{product_id}/images` | 上传商品图片 |
| PATCH | `/api/v1/admin/products/{product_id}/sales-status` | 修改销售状态 |
| GET | `/api/v1/admin/products/{product_id}/skus` | SKU 列表 |
| POST | `/api/v1/admin/products/{product_id}/skus` | 创建 SKU |
| PATCH | `/api/v1/admin/products/skus/{sku_id}` | 更新 SKU |
| GET | `/api/v1/admin/orders` | 订单列表 |
| GET | `/api/v1/admin/orders/{order_id}` | 订单详情 |
| PATCH | `/api/v1/admin/orders/{order_id}/status` | 修改订单状态 |
| POST | `/api/v1/admin/orders/{order_id}/payment-confirm` | 人工确认收款 |
| GET | `/api/v1/admin/printers` | 打印机列表 |
| POST | `/api/v1/admin/printers` | 创建打印机 |
| GET | `/api/v1/admin/printers/{printer_id}` | 打印机详情 |
| PATCH | `/api/v1/admin/printers/{printer_id}` | 更新打印机 |
| PATCH | `/api/v1/admin/printers/{printer_id}/status` | 修改打印机状态 |
| GET | `/api/v1/admin/production-schedule-orders` | 排期列表 |
| POST | `/api/v1/admin/production-schedule-orders` | 创建排期 |
| PATCH | `/api/v1/admin/production-schedule-orders/{schedule_order_id}` | 更新排期 |
| GET | `/api/v1/admin/inventory/overview` | 库存总览 |
| GET | `/api/v1/admin/inventory/materials` | 材料列表 |
| POST | `/api/v1/admin/inventory/materials` | 创建材料 |
| POST | `/api/v1/admin/inventory/materials/{material_id}/stock-logs` | 材料库存变更 |
| GET | `/api/v1/admin/inventory/locks` | 库存锁定列表 |
| GET | `/api/v1/admin/inventory/finished-goods` | 成品库存列表 |

### 2.3 系统接口

| Method | Path | 说明 |
|---|---|---|
| GET | `/health` | 健康检查 |

## 3. P0 缺口：阶段1闭环必须补

### 3.1 管理端缺少定制审核接口

当前缺少：

```text
GET   /api/v1/admin/custom-requests
GET   /api/v1/admin/custom-requests/{request_id}
PATCH /api/v1/admin/custom-requests/{request_id}/review
```

影响：

- 管理员无法查看客户提交的定制需求。
- 管理员无法执行审核、驳回、要求补充信息、审核通过。
- 定制流程无法进入报价阶段。

建议优先实现。

### 3.2 管理端缺少报价管理接口

当前缺少：

```text
POST /api/v1/admin/custom-requests/{request_id}/quote
GET  /api/v1/admin/quotes
GET  /api/v1/admin/quotes/{quote_id}
```

影响：

- 无法由管理员创建人工报价。
- 无法查看报价历史。
- 客户确认报价接口没有完整前置来源。

### 3.3 管理端缺少打印任务管理接口

当前缺少：

```text
GET   /api/v1/admin/print-tasks
POST  /api/v1/admin/print-tasks
GET   /api/v1/admin/print-tasks/{task_id}
PATCH /api/v1/admin/print-tasks/{task_id}/status
```

影响：

- 排期后无法管理具体打印任务。
- 无法推进 `pending -> scheduled -> printing -> completed/failed`。
- 打印农场管理核心链路断开。

### 3.4 客户端缺少订单查询接口

当前缺少：

```text
GET /api/v1/app/orders
GET /api/v1/app/orders/{order_no}
```

影响：

- 客户创建订单后无法在 APP 查询订单列表。
- 客户无法查看订单状态、收款确认状态、排期和生产进度。

### 3.5 客户端缺少定制需求列表接口

当前缺少：

```text
GET /api/v1/app/custom-requests
```

影响：

- 客户只能按 ID 查单条定制需求。
- APP 的“我的定制”页面无法实现。

## 4. P1 缺口：建议尽快补

### 4.1 商品分类接口缺失

建议增加：

```text
GET  /api/v1/app/product-categories
GET  /api/v1/admin/product-categories
POST /api/v1/admin/product-categories
PATCH /api/v1/admin/product-categories/{category_id}
```

影响：

- 商品商城无法按分类展示。
- 管理端无法维护分类。

### 4.2 商品图片缺少管理接口

当前只有上传，没有列表、排序、删除。

建议增加：

```text
GET    /api/v1/admin/products/{product_id}/images
PATCH  /api/v1/admin/product-images/{image_id}
DELETE /api/v1/admin/product-images/{image_id}
```

### 4.3 文件缺少详情、下载、删除接口

建议增加：

```text
GET    /api/v1/app/files/{file_id}
GET    /api/v1/app/files/{file_id}/download-url
DELETE /api/v1/app/files/{file_id}
GET    /api/v1/admin/files/{file_id}
GET    /api/v1/admin/files/{file_id}/download-url
```

注意：

- 不应直接暴露真实文件路径。
- 下载必须鉴权。
- 客户只能访问自己的文件。

### 4.4 库存缺少释放、消耗、损耗接口

当前只有材料入库/调整和锁定列表。

建议增加：

```text
POST /api/v1/admin/inventory/locks/{lock_id}/release
POST /api/v1/admin/inventory/locks/{lock_id}/consume
POST /api/v1/admin/inventory/materials/{material_id}/loss
```

影响：

- 排期锁定材料后，没有明确释放和消耗入口。
- 打印失败损耗无法闭环。

### 4.5 排期缺少详情和取消接口

建议增加：

```text
GET    /api/v1/admin/production-schedule-orders/{schedule_order_id}
DELETE /api/v1/admin/production-schedule-orders/{schedule_order_id}
PATCH  /api/v1/admin/production-schedule-items/{schedule_item_id}
```

## 5. 文档质量问题

### 5.1 所有成功响应 schema 为空

检查结果：

```text
接口总数：40
200 响应 schema 为空：40
```

影响：

- 前端无法从 OpenAPI 直接知道返回字段。
- Apifox/Postman 导入后没有清晰响应结构。
- 无法生成可靠 SDK。

建议：

- 定义统一响应模型 `ApiResponse[T]`。
- 定义分页响应模型 `PageResponse[T]`。
- 每个接口标注 `response_model`。

例如：

```python
@router.get("", response_model=ApiResponse[PageResponse[ProductListItem]])
def list_products(...):
    ...
```

### 5.2 `Idempotency-Key` 在文档中不是必填

当前有 6 个接口暴露 `Idempotency-Key`：

```text
POST /api/v1/app/orders/listed-product
POST /api/v1/app/custom-requests
POST /api/v1/app/quotes/{quote_id}/confirm
POST /api/v1/admin/orders/{order_id}/payment-confirm
POST /api/v1/admin/production-schedule-orders
POST /api/v1/admin/inventory/materials/{material_id}/stock-logs
```

但 OpenAPI 中都显示：

```text
required: false
```

建议：

- 代码里把 Header 类型改成必填。
- 例如：

```python
idempotency_key: str = Header(alias="Idempotency-Key")
```

这样文档会显示必填。

### 5.3 列表接口筛选参数不足

当前许多列表只有：

```text
page
page_size
```

建议补充：

商品列表：

- `keyword`
- `category_id`
- `sales_status`

订单列表：

- `order_type`
- `status`
- `payment_status`
- `keyword`
- `created_from`
- `created_to`

定制需求列表：

- `status`
- `keyword`
- `created_from`
- `created_to`

打印任务列表：

- `status`
- `printer_id`
- `order_id`

排期列表：

- `printer_id`
- `order_id`
- `status`
- `start_date`
- `end_date`

### 5.4 状态字段没有枚举约束

当前很多请求里的 `status` 是普通 `string`。

建议使用 `Literal` 或 Enum：

```python
SalesStatus = Literal["draft", "on_sale", "off_sale", "sold_out", "archived"]
PrinterStatus = Literal["idle", "printing", "paused", "completed", "error", "offline", "maintenance"]
```

好处：

- OpenAPI 会展示可选值。
- 前端不容易传错。
- Apifox/Postman 文档更清楚。

### 5.5 登录接口只是骨架

当前登录接口存在，但需要注意：

- 客户登录没有真正验证码校验。
- 管理员登录没有真正密码校验。
- 返回的用户 ID 是 `null`。

这对 API 骨架阶段可以接受，但进入联调前必须接数据库。

## 6. 建议补充接口清单

### 6.1 客户 APP 端建议补充

```text
GET /api/v1/app/orders
GET /api/v1/app/orders/{order_no}
GET /api/v1/app/custom-requests
GET /api/v1/app/files/{file_id}
GET /api/v1/app/files/{file_id}/download-url
DELETE /api/v1/app/files/{file_id}
GET /api/v1/app/product-categories
```

### 6.2 管理端建议补充

```text
GET   /api/v1/admin/custom-requests
GET   /api/v1/admin/custom-requests/{request_id}
PATCH /api/v1/admin/custom-requests/{request_id}/review
POST  /api/v1/admin/custom-requests/{request_id}/quote

GET   /api/v1/admin/quotes
GET   /api/v1/admin/quotes/{quote_id}

GET   /api/v1/admin/print-tasks
POST  /api/v1/admin/print-tasks
GET   /api/v1/admin/print-tasks/{task_id}
PATCH /api/v1/admin/print-tasks/{task_id}/status

GET   /api/v1/admin/product-categories
POST  /api/v1/admin/product-categories
PATCH /api/v1/admin/product-categories/{category_id}

GET    /api/v1/admin/products/{product_id}/images
PATCH  /api/v1/admin/product-images/{image_id}
DELETE /api/v1/admin/product-images/{image_id}

GET    /api/v1/admin/production-schedule-orders/{schedule_order_id}
DELETE /api/v1/admin/production-schedule-orders/{schedule_order_id}
PATCH  /api/v1/admin/production-schedule-items/{schedule_item_id}

POST /api/v1/admin/inventory/locks/{lock_id}/release
POST /api/v1/admin/inventory/locks/{lock_id}/consume
POST /api/v1/admin/inventory/materials/{material_id}/loss
```

## 7. 优先级建议

### P0：必须先补

1. 管理端定制审核接口。
2. 管理端报价接口。
3. 管理端打印任务接口。
4. 客户端订单列表/详情接口。
5. 客户端定制需求列表接口。
6. `Idempotency-Key` 标记为必填。
7. 成功响应 schema 补全。

### P1：联调前建议补

1. 列表筛选参数。
2. 状态字段枚举。
3. 文件详情和下载接口。
4. 排期详情和取消接口。
5. 库存释放、消耗、损耗接口。

### P2：后续增强

1. 商品图片排序和删除。
2. 更细的 RBAC 权限接口。
3. 操作日志查询接口。
4. OpenAPI examples 示例。
5. SDK 生成配置。

## 8. 下一步执行建议

建议按这个顺序改代码：

1. 先补缺失 router：`admin/custom_requests.py`、`admin/quotes.py`、`admin/print_tasks.py`。
2. 给客户侧补 `GET /app/orders`、`GET /app/orders/{order_no}`、`GET /app/custom-requests`。
3. 把所有关键写接口的 `Idempotency-Key` 改成 OpenAPI 必填。
4. 引入统一响应 Pydantic 模型，让 `/openapi.json` 出现明确 response schema。
5. 给状态字段改成 Enum/Literal。
6. 重新导出 `openapi.json`，再复查一次。
