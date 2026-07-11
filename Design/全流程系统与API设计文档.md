# 3D 打印农场管理系统全流程系统与 API 设计文档

版本：`1.0`  
更新时间：`2026-07-11`  
适用范围：FastAPI 后端、SQL Server 数据库、Flutter 客户端、电脑管理端、Caddy、阿里云 ECS/RDS

## 1. 文档定位

本文是当前系统业务流程、接口契约、状态流转、数据库事务和部署边界的统一基线。发生冲突时，优先级如下：

1. 已部署数据库约束和生产数据安全规则。
2. 当前 FastAPI OpenAPI。
3. 本文档。
4. 历史路线图和阶段性分析报告。

当前 OpenAPI 基线：

```text
paths: 100
operations: 131
schemas: 197
API prefix: /api/v1
```

## 2. 系统目标

系统同时支持两类销售业务：

- 上架商品：管理员预先配置商品、SKU、图片和价格，客户下单后再生产。
- 个性化定制：客户上传切片文件并提交打印参数，管理员审核、报价，客户确认后进入收款和生产流程。

两类业务最终汇入统一订单生产闭环：

```text
订单 -> 收款确认 -> 排期 -> 打印任务 -> 打印完成 -> 成品入库
     -> 创建运单/包裹 -> 批量出库 -> 确认出库 -> 已发货
```

系统还包含：

- 客户与管理员账号体系。
- JWT Access Token 与 Refresh Token。
- 商品和分类管理。
- 优惠券模板、管理员发券和客户抽奖。
- 打印机人工状态维护。
- 材料库存、库存锁、损耗与成品库存件。
- 仓库、库位、入库单、发货单、包裹和出库单。
- 私有切片文件和公开商品图片。

## 3. 技术架构

### 3.1 技术栈

```text
Python 3.13
FastAPI
Uvicorn
Pydantic 2
SQLAlchemy 2
pyodbc
ODBC Driver 18 for SQL Server
SQL Server / 阿里云 RDS
Caddy
JWT + Refresh Token
Flutter 多端客户端
```

### 3.2 生产访问链路

```text
Flutter / 管理端
        |
        | HTTPS 443
        v
      Caddy
        |
        | HTTP 127.0.0.1:5000
        v
 FastAPI / Uvicorn
        |
        | SQL Server TCP 1432（当前 RDS 实例配置）
        v
 3DPMS 数据库
```

### 3.3 端口边界

| 端口 | 服务 | 开放范围 |
|---:|---|---|
| 22 | OpenSSH / VS Code Remote SSH | 仅办公公网 IP |
| 3389 | Windows RDP | 仅办公公网 IP |
| 80 | Caddy HTTP 与 HTTPS 跳转 | 公网 |
| 443 | Caddy HTTPS API | 公网 |
| 5000 | FastAPI | 仅 `127.0.0.1` |
| 1432 | 当前 SQL Server RDS 端口 | 仅云服务器和白名单地址 |

禁止把 FastAPI 端口和数据库端口直接暴露给公网客户端。

## 4. 角色与权限

### 4.1 客户用户

客户 Token 只能访问 `/api/v1/app/*`，并且只能访问自己的：

- 账户资料。
- 文件。
- 定制申请。
- 报价。
- 订单与物流。
- 优惠券和抽奖记录。

### 4.2 管理员

管理员 Token 访问 `/api/v1/admin/*`，处理：

- 商品、SKU 和图片。
- 客户账号。
- 定制审核和报价。
- 收款确认。
- 打印机、打印任务和排期。
- 库存、仓库、入库、发货和出库。
- 优惠券模板、发放和作废。

`super_admin` 额外负责管理员账号增删改、禁用和密码重置。

### 4.3 公开资源

```text
GET /api/v1/public/product-images/{image_id}
```

只用于已保存的商品展示图片。客户上传的切片文件不走公开接口。

## 5. API 通用契约

### 5.1 鉴权

```http
Authorization: Bearer <access_token>
```

Access Token 用于业务接口；Refresh Token 只用于刷新和退出。客户 Token 与管理员 Token 不可混用。

### 5.2 成功响应

```json
{
  "code": "OK",
  "message": "success",
  "data": {}
}
```

### 5.3 分页响应

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

### 5.4 错误响应

```json
{
  "code": "RESOURCE_NOT_FOUND",
  "message": "资源不存在",
  "details": {}
}
```

HTTP 状态码：

| 状态码 | 含义 |
|---:|---|
| 400 | 业务参数错误 |
| 401 | 登录凭据、Token 或原密码错误 |
| 403 | 账号状态或权限不允许 |
| 404 | 资源不存在或不属于当前用户 |
| 409 | 状态、库存、幂等或数据库约束冲突 |
| 413 | 上传文件过大 |
| 422 | 请求字段校验失败 |
| 500 | 未处理服务端错误，必须记录服务端日志 |

### 5.5 幂等请求

关键写接口使用：

```http
Idempotency-Key: <UUID>
```

当前接口虽然普遍声明该 Header，但通用 `IdempotencyService` 尚未完全实现。优惠券抽奖通过用户锁和抽奖记录处理重复请求；订单、排期、仓库等接口仍需逐步接入统一幂等表。

## 6. 账号与认证流程

### 6.1 客户注册登录

```text
POST /api/v1/app/auth/register
POST /api/v1/app/auth/login
GET  /api/v1/app/auth/me
POST /api/v1/app/auth/refresh
POST /api/v1/app/auth/logout
```

注册成功后创建用户、生成 Access Token、保存 Refresh Token 哈希。邮箱对未软删除用户唯一，昵称允许重复。

### 6.2 客户资料与密码

```text
PATCH /api/v1/app/auth/profile
```

规则：

- 修改昵称不要求昵称唯一。
- 昵称去除首尾空格且不能为空。
- 修改密码必须同时提供 `old_password` 与 `new_password`。
- 新密码至少 8 位。
- 原密码错误返回 `401 AUTH_INVALID_OLD_PASSWORD`。
- 修改密码成功后撤销当前用户所有 Refresh Token。

### 6.3 管理端账号

```text
POST /api/v1/admin/auth/login
GET  /api/v1/admin/auth/me
POST /api/v1/admin/auth/refresh
POST /api/v1/admin/auth/logout
```

客户账号管理位于 `/api/v1/admin/users`，管理员账号管理位于 `/api/v1/admin/staff-users`。

## 7. 上架商品完整流程

### 7.1 管理员准备商品

```text
POST  /api/v1/admin/product-categories
POST  /api/v1/admin/products
POST  /api/v1/admin/products/{product_id}/images
POST  /api/v1/admin/products/{product_id}/skus
PATCH /api/v1/admin/products/{product_id}/sales-status
```

规则：

- 商品名称允许重复，商品以 `product_id` 区分。
- SKU 定义材料、颜色、尺寸、精度、价格和数量范围。
- 商品默认 `make_to_order`，不扣现货成品库存。
- 只有 `on_sale` 商品和 `active` SKU 可以下单。

### 7.2 客户浏览和下单

```text
GET  /api/v1/app/product-categories
GET  /api/v1/app/products
GET  /api/v1/app/products/{product_id}
GET  /api/v1/app/products/{product_id}/images
POST /api/v1/app/orders/listed-product
```

下单事务：

1. 创建订单主表。
2. 查询 SKU 和商品。
3. 校验销售状态。
4. 计算订单明细和原始总价。
5. 如选择优惠券，锁定优惠券并计算适用金额。
6. 写入折扣金额和实付金额。
7. 提交订单与优惠券状态。

初始状态：

```text
order.status = submitted
order.payment_status = unconfirmed
```

## 8. 个性化定制完整流程

### 8.1 文件上传

```text
POST /api/v1/app/files/upload
GET  /api/v1/app/files/{file_id}
GET  /api/v1/app/files/{file_id}/download
GET  /api/v1/app/files/{file_id}/download-url
```

切片文件必须走鉴权接口，数据库只保存存储路径和元数据。允许格式包括 `.gcode`、`.3mf`、`.bgcode` 和 `.zip`。

### 8.2 客户提交定制申请

```text
POST  /api/v1/app/custom-requests
GET   /api/v1/app/custom-requests
GET   /api/v1/app/custom-requests/{request_id}
PATCH /api/v1/app/custom-requests/{request_id}
```

核心字段：

- 切片文件，必填。
- 申请打印时间，可选。
- 指定打印机和型号，可选。
- 耗材颜色和类型，可选。
- 是否使用 AMS，必填。
- 打印盘数，必填且大于 0。

### 8.3 管理员审核和报价

```text
GET   /api/v1/admin/custom-requests
GET   /api/v1/admin/custom-requests/{request_id}
PATCH /api/v1/admin/custom-requests/{request_id}/review
POST  /api/v1/admin/custom-requests/{request_id}/quote
GET   /api/v1/admin/quotes
GET   /api/v1/admin/quotes/{quote_id}
```

### 8.4 客户确认报价

```text
GET  /api/v1/app/quotes/{quote_id}
POST /api/v1/app/quotes/{quote_id}/confirm
```

确认后生成或关联定制订单，订单仍等待管理员确认线下收款。

定制状态主线：

```text
submitted -> reviewing -> quote_pending -> quoted -> quote_confirmed
                |              
                +-> need_more_info -> submitted
                +-> rejected
```

## 9. 优惠券与抽奖流程

### 9.1 管理员模板和发放

```text
POST  /api/v1/admin/coupons/templates
GET   /api/v1/admin/coupons/templates
PATCH /api/v1/admin/coupons/templates/{template_id}/status
POST  /api/v1/admin/coupons/grant
GET   /api/v1/admin/coupons
POST  /api/v1/admin/coupons/{coupon_id}/revoke
```

模板状态：`active`、`disabled`、`archived`。

管理员优惠券列表返回：

```json
{
  "user_id": 12,
  "user_nickname": "客户昵称",
  "user_email": "user@example.com"
}
```

发券前校验用户存在、用户未软删除、用户列表无重复、模板配额和每人限领数量。

### 9.2 客户优惠券和抽奖

```text
GET  /api/v1/app/coupons
GET  /api/v1/app/coupons/my
POST /api/v1/app/coupons/lottery/draw
```

`/app/coupons` 是推荐路径，`/my` 为兼容路径。

当前抽奖由前端产生结果，后端负责约束和落库：

- 每个用户最多抽 3 次。
- 百分比折扣值为 `80-99`，最多八折。
- 满减金额最多为门槛金额的 20%。
- 无门槛立减最多 5 元。
- 同一用户抽奖通过 SQL Server 用户行锁串行化。

### 9.3 下单使用优惠券

优惠券必须满足：归属当前用户、`unused`、已生效、未过期、达到门槛、订单商品符合范围。

商品券和分类券按适用商品小计计算折扣；模板 `max_discount` 作为最高减免；同一张券使用 `UPDLOCK + HOLDLOCK` 防止并发重复核销。

## 10. 收款、排期与打印流程

### 10.1 管理员确认收款

```text
POST /api/v1/admin/orders/{order_id}/payment-confirm
```

结果：

```text
payment_status = confirmed
order.status = payment_confirmed
```

未确认收款的订单不应进入正式排期。

### 10.2 创建打印任务和排期

```text
POST /api/v1/admin/print-tasks
POST /api/v1/admin/production-schedule-orders
GET  /api/v1/admin/production-schedule-orders
PATCH /api/v1/admin/production-schedule-items/{schedule_item_id}
```

排期内容包括订单、打印任务、打印机、开始时间、结束时间、优先级和材料锁。

### 10.3 打印任务状态

```text
pending -> scheduled -> printing -> paused -> completed
                                  +-> failed
                                  +-> cancelled
```

任务变为 `completed` 后：

```text
warehouse_status = pending_inbound
```

打印机状态由管理员人工维护，任务推进可联动打印机状态。

## 11. 库存与仓库流程

### 11.1 材料库存

```text
GET/POST /api/v1/admin/inventory/materials
POST     /api/v1/admin/inventory/materials/{material_id}/stock-logs
POST     /api/v1/admin/inventory/materials/{material_id}/loss
GET      /api/v1/admin/inventory/locks
POST     /api/v1/admin/inventory/locks/{lock_id}/release
POST     /api/v1/admin/inventory/locks/{lock_id}/consume
```

库存规则：

- `stock_weight >= 0`。
- `reserved_weight >= 0`。
- `reserved_weight <= stock_weight`。
- 锁定、释放、消耗和损耗写入库存流水。

### 11.2 成品入库

```text
POST /api/v1/admin/print-tasks/{task_id}/transfer-to-warehouse
POST /api/v1/admin/orders/{order_id}/transfer-to-warehouse
GET  /api/v1/admin/warehouse/stock-items
GET  /api/v1/admin/warehouse/inbounds
```

入库事务：

1. 校验打印任务已完成且未入库。
2. 创建成品库存件。
3. 创建入库记录。
4. 更新打印任务 `warehouse_status = inbounded`。
5. 更新订单明细入库数量。
6. 全部有效打印任务入库后，订单变为 `ready_to_ship`。

## 12. 发货与出库流程

### 12.1 创建发货单和包裹

```text
POST /api/v1/admin/orders/{order_id}/shipments
GET  /api/v1/admin/orders/{order_id}/shipments
PATCH /api/v1/admin/shipments/{shipment_id}
```

一个订单支持多个发货单，每个发货单支持一个或多个包裹和快递单号。创建发货单时库存件由 `available` 变为 `reserved`，订单进入 `shipping`。

### 12.2 批量出库

```text
POST /api/v1/admin/warehouse/outbounds/batch
POST /api/v1/admin/warehouse/outbounds/{outbound_id}/confirm
GET  /api/v1/admin/warehouse/outbounds
```

确认出库事务：

1. 锁定出库单和库存件。
2. 库存件改为 `shipped`。
3. 运单和包裹改为 `outbounded`。
4. 更新订单明细已发货数量。
5. 全部库存件发货后订单变为 `shipped`，否则为 `partially_shipped`。

客户查询：

```text
GET /api/v1/app/orders/{order_no}/shipments
```

## 13. 订单状态机

完整状态集合：

```text
submitted
reviewing
quoted
quote_confirmed
payment_confirmed
scheduled
printing
post_processing
quality_check
partially_completed
completed
partially_inbound
in_warehouse
ready_to_ship
shipping
partially_shipped
shipped
cancelled
```

推荐主线：

```text
submitted -> payment_confirmed -> scheduled -> printing -> completed
          -> ready_to_ship -> shipping -> shipped
```

禁止无条件跨状态更新。`PATCH /admin/orders/{id}/status` 当前仍允许管理员提交任意枚举状态，后续必须接入状态迁移矩阵。

## 14. 核心事务与并发规则

必须在单个数据库事务中完成：

- 注册用户和创建 Refresh Token。
- 下单、订单明细和优惠券核销。
- 报价确认和定制订单创建。
- 收款确认和状态更新。
- 排期、打印任务和材料锁定。
- 打印完成入库和订单入库状态同步。
- 发货单、库存预留和订单状态更新。
- 出库确认、库存件发货和订单终态同步。
- 管理员发券和模板发放数量更新。

锁策略：

| 业务资源 | 策略 |
|---|---|
| 优惠券核销/作废 | `UPDLOCK, HOLDLOCK` |
| 同用户抽奖 | 锁定用户行 |
| 同模板发券 | 锁定模板行 |
| 材料库存 | 锁定材料行 |
| 成品库存预留/出库 | 锁定库存件 |
| 排期时间窗口 | 数据库约束与事务校验 |

数据库连接设置 `LOCK_TIMEOUT 30000`，连接池等待超时 30 秒。

## 15. 数据库模块

核心表：

```text
users, staff_users, auth_refresh_tokens
product_categories, products, product_images, product_skus
model_files, custom_requests, custom_request_reviews, quotes
orders, order_items
printers, print_tasks
production_schedule_orders, production_schedule_items
materials, inventory_locks, material_stock_logs
warehouses, warehouse_locations, warehouse_stock_items
warehouse_inbound_records, shipments, shipment_packages, shipment_items
warehouse_outbound_records, warehouse_outbound_items
coupon_templates, user_coupons, coupon_grant_batches, lottery_records
idempotency_keys, operation_logs
```

中文字段使用 `NVARCHAR`，Python 文件和 `.env` 使用 UTF-8。SQL 脚本直接连接 `3DPMS`，不使用 `USE` 切换数据库。

## 16. 文件安全

- 商品图片通过图片 ID 读取，不向客户端返回磁盘真实路径。
- 切片文件必须验证用户归属或管理员权限。
- 上传文件名经过路径清理。
- 上传大小同时受 Caddy 和 FastAPI 限制。
- 模型文件后续应增加病毒扫描、切片参数解析和对象存储。

## 17. 部署与运维

### 17.1 FastAPI

```powershell
uvicorn app.main:app --host 127.0.0.1 --port 5000
```

生产环境不使用 `--reload`，应注册为 Windows 服务并配置失败自动重启。

### 17.2 Caddy

Caddy 对外监听 80/443，反向代理到 `127.0.0.1:5000`。日志至少包含请求路径、状态码、耗时和来源 IP。

### 17.3 健康与日志

```text
GET /health
GET /openapi.json
GET /docs（debug 环境）
```

未处理异常统一返回 `INTERNAL_SERVER_ERROR`，完整堆栈只写服务端日志。

## 18. 全流程验收用例

### 18.1 上架商品订单

1. 管理员登录。
2. 创建分类、商品、SKU，上传图片并上架。
3. 客户注册并登录。
4. 客户查询商品和优惠券。
5. 客户创建订单。
6. 管理员确认收款。
7. 管理员创建打印任务和排期。
8. 推进打印任务至完成。
9. 转移成品入库，订单变为 `ready_to_ship`。
10. 创建运单和包裹。
11. 创建批量出库单并确认。
12. 验证订单状态为 `shipped`。

### 18.2 个性化定制订单

1. 客户上传切片文件。
2. 提交定制申请。
3. 管理员审核并创建报价。
4. 客户确认报价。
5. 管理员确认收款。
6. 后续进入统一排期、打印、入库、发货流程。

### 18.3 优惠券

1. 管理员创建模板并发放给用户。
2. 管理员列表能看到 `user_id/user_nickname/user_email`。
3. 客户查询自己的优惠券。
4. 客户下单使用优惠券。
5. 验证范围、门槛、最高减免和并发重复使用均被正确处理。
6. 客户抽奖第四次返回次数用尽。

## 19. 当前已知缺口

### P0

- 通用 `IdempotencyService` 仍是 TODO，多数关键写接口只声明 Header，尚未真正保存和复用响应。
- 管理员订单状态接口缺少严格状态迁移矩阵。
- 订单取消时缺少统一的优惠券释放、库存释放和排期取消事务。
- 尚未完成云服务器环境的自动化全流程回归测试。

### P1

- 部分响应仍包含松散 `dict` 嵌套结构，前端代码生成约束不足。
- 部分 PATCH 接口仍要求接近全量对象。
- 排期冲突、材料库存和成品库存并发规则需要更完整的数据库实测。
- 过期优惠券当前由查询时动态计算，数据库状态未由定时任务持久化。

### P2

- 增加操作日志查询接口。
- 增加订单取消、退款和优惠券返还策略。
- 增加文件病毒扫描、切片参数解析和对象存储。
- 增加打印机协议自动接入。

## 20. 交付标准

后端交付必须同时包含：

- 可启动 FastAPI 服务。
- 可执行 SQL Server 初始化和升级脚本。
- 与代码一致的 OpenAPI。
- Caddy 和端口安全配置。
- `.env.example`，不得包含生产密码。
- 全流程自动化测试及测试数据清理策略。
- 数据库备份、恢复和故障排查文档。

