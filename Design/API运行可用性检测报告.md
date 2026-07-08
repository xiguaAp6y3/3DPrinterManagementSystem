# API 运行可用性检测报告

检测时间：2026-07-08  
后端地址：`http://127.0.0.1:5000`  
数据库：远程 SQL Server，当前连接库 `3DPMS`

## 1. 当前结论

本轮已经将主要 API 从骨架接口推进到“基础业务可用”状态。

当前可用能力：

| 模块 | 当前状态 |
|---|---|
| 服务启动 / 健康检查 | 可用 |
| Swagger / OpenAPI | 可用 |
| 登录认证 Demo | 可用 |
| APP token 查询 / refresh | 可用 |
| 管理端 token 查询 / refresh | 可用 |
| 商品分类 | 真实读写数据库 |
| 商品 / SKU / 图片 | 真实读写数据库 |
| APP 商品浏览 | 真实查库，只展示 `on_sale` 商品 |
| 文件上传 | 真实落盘并写入 `model_files` |
| APP 上架商品下单 | 真实创建 `orders/order_items` |
| APP 定制申请 | 真实创建 `custom_requests` 并关联切片文件 |
| 管理端定制审核 | 真实更新状态并写审核记录 |
| 管理端报价 | 真实创建 `quotes` |
| APP 确认报价 | 真实确认报价并生成定制订单 |
| 管理端订单管理 | 真实查询、改状态、确认收款 |
| 材料库存 | 真实创建、查询、流水调整 |
| 打印机管理 | 真实创建、查询、更新状态 |
| 打印任务 | 真实创建、查询、更新状态 |
| 排期 | 真实创建排期主表/明细表，并锁定材料 |
| Dashboard | 真实统计待办数据 |

当前仍属于后续增强：

- 幂等键当前只保留接口必填 Header，尚未实现重复请求返回同一业务结果。
- 文件下载目前返回本地 `storage_key`，还不是签名 URL 或流式下载接口。
- 图片上传写入本地路径，尚未接对象存储/CDN。
- 排期已有 SQL Server 触发器防止同一打印机时间重叠，但冲突错误尚未转换成友好的业务错误。
- 库存成本核算、成品库存自动入库、打印完成自动扣料还未完整自动化。
- 权限仍是 Demo 级别管理员/客户区分，没有 RBAC。

## 2. 实测通过项

### 2.1 基础服务

```text
GET /health
```

结果：`OK`

OpenAPI 导出：

```text
D:\openapi.json
```

当前接口规模：

```text
paths: 63
operations: 82
```

### 2.2 登录认证

APP 登录：

```text
POST /api/v1/app/auth/login
```

结果：

```text
access_token: 有
refresh_token: 有
user_id: 1
```

管理端登录：

```text
POST /api/v1/admin/auth/login
```

结果：

```text
access_token: 有
refresh_token: 有
staff_id: 1
```

APP `me/refresh` 实测：

```text
GET /api/v1/app/auth/me
POST /api/v1/app/auth/refresh
```

结果：

```text
me=1
refresh=True
```

### 2.3 上架商品下单链路

已实测：

```text
POST /api/v1/admin/product-categories
POST /api/v1/admin/products
POST /api/v1/admin/products/{product_id}/skus
POST /api/v1/app/orders/listed-product
```

结果：

```text
category=3
product=1
sku=1
order=OD20260708000001
amount=59.8
```

结论：商品、SKU、订单、订单明细真实入库。

### 2.4 个性化定制链路

已实测：

```text
POST /api/v1/app/files/upload
POST /api/v1/app/custom-requests
PATCH /api/v1/admin/custom-requests/{request_id}/review
POST /api/v1/admin/custom-requests/{request_id}/quote
POST /api/v1/app/quotes/{quote_id}/confirm
```

结果：

```text
file=1
custom=CR20260708000001
quote=QT20260708000001
quote_status=confirmed
order_id=2
```

结论：文件、定制申请、审核、报价、报价确认、定制订单生成真实可用。

### 2.5 生产管理链路

已实测：

```text
POST /api/v1/admin/inventory/materials
POST /api/v1/admin/printers
POST /api/v1/admin/orders/{order_id}/payment-confirm
POST /api/v1/admin/print-tasks
POST /api/v1/admin/production-schedule-orders
```

结果：

```text
material=2
printer=2
order=2
task=PT20260708000001
schedule=SCH20260708000002
items=1
locks=1
```

结论：材料、打印机、收款确认、打印任务、排期、材料锁定真实可用。

### 2.6 列表和 Dashboard

实测：

```text
GET /api/v1/admin/products
GET /api/v1/admin/orders
GET /api/v1/admin/dashboard
```

结果：

```text
products=2
orders=2
dashboard=OK
```

## 3. 已修复的技术问题

### 3.1 SQL Server ROWVERSION 插入问题

问题：

```text
Cannot insert an explicit value into a timestamp column.
```

修复：

ORM 中所有 `row_version` 字段已改为数据库生成列：

```python
server_default=FetchedValue()
server_onupdate=FetchedValue()
```

### 3.2 SQL Server 触发器与 OUTPUT 冲突

问题：

```text
The target table 'production_schedule_items' ... cannot have any enabled triggers if the statement contains an OUTPUT clause
```

修复：

`ProductionScheduleItem` 关闭 SQLAlchemy 隐式 returning：

```python
__table_args__ = {"implicit_returning": False}
```

## 4. 当前可联调范围

现在可以开始后端自测或 Flutter 早期联调：

- 登录认证
- 商品分类和商品维护
- 商品 SKU 维护
- APP 浏览商品
- APP 上架商品下单
- APP 文件上传
- APP 定制申请
- 管理端定制审核
- 管理端报价
- APP 确认报价
- 管理端订单确认收款
- 材料库存基础维护
- 打印机维护
- 打印任务维护
- 订单排期和材料锁定

## 5. 下一阶段建议

优先增强：

1. 接入 `idempotency_keys`，实现关键写接口真正幂等。
2. 给 SQLAlchemy 异常增加统一转换，尤其是排期冲突、库存约束、外键错误。
3. 增加 pytest 接口测试，固定核心业务链路。
4. 文件下载改为流式下载或签名 URL。
5. 打印完成后自动消耗材料，并可选生成成品库存。
6. 增加管理员账号维护和 RBAC。
