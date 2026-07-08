# API 运行可用性检测报告

检测时间：2026-07-08  
后端地址：`http://127.0.0.1:5000`  
数据库：SQL Server，目标库 `3DPMS`  
检测依据：`D:\openapi.json`、后端代码编译、当前 SQL 建表脚本  

> 说明：本轮是在“允许清空数据库并按新 SQL 重建”的前提下更新。后端本地服务此前已关闭，因此本报告不声称完成了运行时 HTTP 全链路实测；当前结论基于代码编译和 OpenAPI 成功导出。

## 1. 当前结论

后端接口已从原来的核心订单/生产链路，扩展到账号、仓库、入库、发货、批量出库链路。

最新 OpenAPI 规模：

```text
paths: 91
operations: 121
```

验证结果：

```text
python -m compileall app 通过
OpenAPI 导出成功：D:\openapi.json
```

数据库脚本状态：

```text
deploy/sql/001_create_tables.sql 已重写为新结构
deploy/sql/002_create_triggers.sql 可继续执行
deploy/sql/003_seed_dev.sql 已补默认 super_admin、默认仓库、默认库位
```

推荐数据库初始化顺序：

```text
001_create_tables.sql
002_create_triggers.sql
003_seed_dev.sql
```

## 2. 当前可用模块

| 模块 | 当前状态 | 说明 |
|---|---|---|
| 健康检查 | 可用 | `GET /health` |
| Swagger / OpenAPI | 可用 | `D:\openapi.json` 已更新 |
| APP 邮箱注册 | 已实现 | `POST /api/v1/app/auth/register` |
| APP 邮箱密码登录 | 已实现 | `POST /api/v1/app/auth/login` |
| APP 旧 Demo 登录 | 保留 | `POST /api/v1/app/auth/login-demo` |
| APP token 查询 / refresh / logout | 已实现 | access token + refresh token |
| 管理端登录 | 已实现 | 用户名或邮箱 + 密码 |
| 管理端 token 查询 / refresh / logout | 已实现 | refresh token 轮换 |
| 后台客户账号管理 | 已实现 | `/api/v1/admin/users` |
| 后台管理员账号管理 | 已实现 | `/api/v1/admin/staff-users`，仅 `super_admin` |
| 商品分类 | 可用 | 真实读写数据库 |
| 商品 / SKU | 可用 | 真实读写数据库 |
| 商品图片 | 可用 | 上传、列表、修改、删除、公开渲染 |
| APP 商品浏览 | 可用 | 只返回 `on_sale` 商品 |
| 文件上传 / 查询 / 下载 | 基础可用 | 私有文件走鉴权下载 |
| APP 上架商品下单 | 可用 | 创建 `orders/order_items` |
| APP 个性化定制申请 | 可用 | 创建 `custom_requests` 并关联切片文件 |
| 管理端定制审核 | 可用 | 状态更新并写审核记录 |
| 管理端报价 | 可用 | 创建 `quotes` |
| APP 确认报价 | 可用 | 确认报价并生成定制订单 |
| 管理端订单管理 | 基础可用 | 查询、改状态、确认收款 |
| 材料库存 | 基础可用 | 材料、流水、锁定、释放、消耗 |
| 打印机管理 | 可用 | 人工维护状态 |
| 打印任务 | 已扩展 | 完成后进入 `pending_inbound` |
| 排期 | 基础可用 | 创建排期并锁定材料 |
| 仓库 / 库位管理 | 已实现 | 仓库、库位 CRUD |
| 生产完成入库 | 已实现 | 打印任务或订单批量转移入库 |
| 成品库存件查询 | 已实现 | `/api/v1/admin/warehouse/stock-items` |
| 入库记录查询 | 已实现 | `/api/v1/admin/warehouse/inbounds` |
| 发货单 / 多快递单 | 已实现 | 一个订单可创建多个包裹/快递单号 |
| APP 查询订单发货 | 已实现 | `GET /api/v1/app/orders/{order_no}/shipments` |
| 批量出库 | 已实现 | 创建出库单、确认出库 |
| Dashboard | 可用 | 现有生产/库存统计可用，仓库待办统计待增强 |

## 3. 新增接口摘要

### 3.1 APP 账号接口

```text
POST /api/v1/app/auth/register
POST /api/v1/app/auth/login
POST /api/v1/app/auth/login-demo
GET  /api/v1/app/auth/me
POST /api/v1/app/auth/refresh
POST /api/v1/app/auth/logout
```

说明：

- `/login` 当前为邮箱 + 密码。
- `/register` 会创建客户账户并返回 token。
- `/login-demo` 仅用于旧测试链路，固定验证码仍为 `123456`。

### 3.2 后台账号接口

客户账号：

```text
GET    /api/v1/admin/users
POST   /api/v1/admin/users
GET    /api/v1/admin/users/{user_id}
PATCH  /api/v1/admin/users/{user_id}
PATCH  /api/v1/admin/users/{user_id}/status
POST   /api/v1/admin/users/{user_id}/reset-password
DELETE /api/v1/admin/users/{user_id}
```

后台账号：

```text
GET    /api/v1/admin/staff-users
POST   /api/v1/admin/staff-users
GET    /api/v1/admin/staff-users/{staff_user_id}
PATCH  /api/v1/admin/staff-users/{staff_user_id}
PATCH  /api/v1/admin/staff-users/{staff_user_id}/status
POST   /api/v1/admin/staff-users/{staff_user_id}/reset-password
DELETE /api/v1/admin/staff-users/{staff_user_id}
```

说明：

- 后台账号管理要求当前登录账号角色为 `super_admin`。
- 最后一个 `super_admin` 不允许禁用、删除或降级。
- 删除为软删除。
- 重置密码后会吊销旧 refresh token。

### 3.3 仓库接口

仓库和库位：

```text
GET   /api/v1/admin/warehouses
POST  /api/v1/admin/warehouses
GET   /api/v1/admin/warehouses/{warehouse_id}
PATCH /api/v1/admin/warehouses/{warehouse_id}

GET   /api/v1/admin/warehouse-locations
POST  /api/v1/admin/warehouse-locations
PATCH /api/v1/admin/warehouse-locations/{location_id}
```

入库：

```text
POST /api/v1/admin/print-tasks/{task_id}/transfer-to-warehouse
POST /api/v1/admin/orders/{order_id}/transfer-to-warehouse
GET  /api/v1/admin/warehouse/stock-items
GET  /api/v1/admin/warehouse/inbounds
```

发货和出库：

```text
POST   /api/v1/admin/orders/{order_id}/shipments
GET    /api/v1/admin/orders/{order_id}/shipments
PATCH  /api/v1/admin/shipments/{shipment_id}
DELETE /api/v1/admin/shipments/{shipment_id}

POST /api/v1/admin/warehouse/outbounds/batch
POST /api/v1/admin/warehouse/outbounds/{outbound_id}/confirm
GET  /api/v1/admin/warehouse/outbounds
GET  /api/v1/admin/warehouse/outbounds/{outbound_id}
```

APP 发货查询：

```text
GET /api/v1/app/orders/{order_no}/shipments
```

## 4. 仓库业务链路状态

### 4.1 打印任务完成

接口：

```text
PATCH /api/v1/admin/print-tasks/{task_id}/status
```

当状态改为：

```text
completed
```

系统会自动将：

```text
print_tasks.warehouse_status = pending_inbound
```

### 4.2 转移入库

接口：

```text
POST /api/v1/admin/print-tasks/{task_id}/transfer-to-warehouse
```

当前规则：

- 打印任务必须是 `completed`。
- 不能重复入库。
- 创建 `warehouse_stock_items`。
- 创建 `warehouse_inbound_records`。
- 更新 `print_tasks.warehouse_status = inbounded`。
- 更新 `order_items.inbounded_quantity`。
- 检查订单下打印任务是否全部入库。

订单状态自动流转：

```text
部分入库 -> partially_inbound
全部入库 -> ready_to_ship
```

### 4.3 创建发货单

接口：

```text
POST /api/v1/admin/orders/{order_id}/shipments
```

当前规则：

- 订单必须处于 `ready_to_ship`、`in_warehouse`、`partially_shipped` 或 `shipping`。
- 一个订单可以有多个发货单。
- 一个发货单可以有多个包裹和多个快递单号。
- 选中的库存件必须属于该订单。
- 选中的库存件必须是 `available`。
- 创建发货单后库存件变为 `reserved`。
- 订单状态变为 `shipping`。

### 4.4 批量出库

创建出库单：

```text
POST /api/v1/admin/warehouse/outbounds/batch
```

确认出库：

```text
POST /api/v1/admin/warehouse/outbounds/{outbound_id}/confirm
```

当前规则：

- 只允许 `ready` 状态发货单出库。
- 发货单必须有快递单号。
- 确认出库后库存件变为 `shipped`。
- 发货单和包裹变为 `outbounded`。
- 订单全部库存件已发货时变为 `shipped`。
- 部分发货时变为 `partially_shipped`。

## 5. 数据库结构更新状态

### 5.1 已扩展表

`users`：

- 新增 `email`
- 新增 `password_hash`
- `phone` 改为可选
- 新增 `email_verified_at`
- 新增 `last_login_at`
- 新增 `deleted_at`

`staff_users`：

- 新增 `email`
- 新增 `deleted_at`
- `role` 支持 `super_admin/admin/production_manager/warehouse_manager/customer_service`

`orders`：

- 新增收货人字段：
  - `receiver_name`
  - `receiver_phone`
  - `receiver_address`
- 状态扩展：
  - `partially_completed`
  - `partially_inbound`
  - `in_warehouse`
  - `ready_to_ship`
  - `shipping`
  - `partially_shipped`
  - `shipped`

`order_items`：

- 新增 `produced_quantity`
- 新增 `inbounded_quantity`
- 新增 `shipped_quantity`

`print_tasks`：

- 新增 `warehouse_status`

### 5.2 新增表

```text
warehouses
warehouse_locations
warehouse_stock_items
warehouse_inbound_records
shipments
shipment_packages
shipment_items
warehouse_outbound_records
warehouse_outbound_items
```

### 5.3 新增序列

```text
seq_stock_item_no
seq_inbound_no
seq_shipment_no
seq_outbound_no
```

## 6. 仍需注意的限制

### 6.1 未完成真实 HTTP 全链路回归

当前已完成：

- Python 编译检查。
- OpenAPI 导出检查。
- SQL 脚本结构更新。

尚未完成：

- 清空远程数据库后的真实建表执行验证。
- 启动后端后的 HTTP 实测。
- 从注册、下单、收款、排期、完成、入库、发货、出库的一整条真实数据链路跑通。

### 6.2 幂等仍需增强

当前多个关键接口要求 `Idempotency-Key`，但还没有全部实现“相同 key 返回第一次响应”的完整幂等逻辑。

优先补齐：

- APP 下单。
- 确认报价。
- 确认收款。
- 创建排期。
- 转移入库。
- 创建发货单。
- 批量出库。
- 确认出库。

### 6.3 权限仍是轻量角色判断

当前已有：

- APP 用户 token。
- 管理员 token。
- 后台账号管理要求 `super_admin`。

尚未实现：

- 细粒度 RBAC 表。
- 每个接口按角色精确授权。
- 权限变更审计。

### 6.4 仓库功能是第一版

当前已支持主链路，但二期仍建议补：

- 出库撤销。
- 退货入库。
- 发货单拆包时按包裹分配库存件。
- 仓库盘点。
- 库存件调整。
- 物流轨迹查询。

### 6.5 Dashboard 待扩展

当前 Dashboard 仍偏生产和材料库存统计，建议新增：

- 待入库打印任务数。
- 待发货订单数。
- 待出库发货单数。
- 今日出库单数。
- 仓库可发库存件数。

## 7. 下一步验收建议

### 7.1 数据库重建验收

按顺序执行：

```text
001_create_tables.sql
002_create_triggers.sql
003_seed_dev.sql
```

确认：

- 无 `USE` 语句。
- 无 `_UTF8` collation。
- 中文字段均为 `NVARCHAR`。
- 默认管理员创建成功。
- 默认仓库和库位创建成功。

默认管理员：

```text
username: admin
password: admin123456
role: super_admin
```

### 7.2 API 启动验收

启动：

```powershell
cd C:\Users\Gua3\Desktop\3DPrinterManagementSystem\backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 5000
```

检查：

```text
GET http://127.0.0.1:5000/health
GET http://127.0.0.1:5000/docs
```

### 7.3 主链路验收

建议按这个顺序跑：

1. APP 注册客户。
2. APP 登录获取 token。
3. 管理端登录 `admin/admin123456`。
4. 管理端创建商品分类、商品、SKU、商品图。
5. APP 创建上架商品订单。
6. 管理端确认收款。
7. 管理端创建打印任务。
8. 管理端将打印任务状态改为 `completed`。
9. 管理端转移入库。
10. 检查订单状态是否为 `ready_to_ship`。
11. 管理端创建发货单，填写一个或多个快递单号。
12. 管理端创建批量出库单。
13. 管理端确认出库。
14. 检查订单状态是否为 `shipped`。

