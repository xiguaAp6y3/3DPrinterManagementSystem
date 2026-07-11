# API 完善性分析报告

检查时间：`2026-07-11`

检查对象：当前 FastAPI 运行时代码生成的 OpenAPI

设计基线：`Design/全流程系统与API设计文档.md`

## 1. 总体结论

当前 API 已覆盖 3D 打印农场的主要业务闭环：

```text
注册登录
-> 商品上架或定制申请
-> 优惠券获取/使用
-> 创建订单
-> 管理员确认收款
-> 排期和打印任务
-> 打印完成入库
-> 创建发货单和快递包裹
-> 批量出库
-> 订单 shipped
```

最新 OpenAPI：

```text
paths: 100
operations: 131
schemas: 197
```

结论分级：

| 维度 | 结论 |
|---|---|
| 路由覆盖 | 完整，可覆盖主流程 |
| 请求/响应模型 | 较完整，仍有少量松散嵌套结构 |
| 数据库实现 | 主要接口已真实读写数据库 |
| 认证授权 | 客户/管理员 Token 已隔离 |
| 事务并发 | 部分关键路径已加锁，尚未全面统一 |
| 幂等 | OpenAPI 已声明，通用服务未完成 |
| 运行验证 | 静态检查通过，云端全流程回归仍需执行 |

## 2. 模块统计

| 模块 | Operations | 状态 |
|---|---:|---|
| system | 1 | 可用 |
| app-auth | 7 | 可用 |
| app-products/categories | 4 | 可用 |
| app-orders | 4 | 可用 |
| app-files | 5 | 可用 |
| app-custom-requests | 4 | 可用 |
| app-quotes | 2 | 可用 |
| app-coupons | 3 | 已修复列表和日期响应 |
| admin-auth/accounts | 18 | 可用 |
| admin-products/categories/images | 15 | 可用 |
| admin-orders | 4 | 基础可用 |
| admin-custom/quotes/files | 9 | 可用 |
| admin-printers/tasks/schedules | 16 | 基础可用 |
| admin-inventory | 12 | 基础可用 |
| admin-warehouse | 19 | 主流程可用 |
| admin-coupons | 6 | 已补模板状态和客户归属字段 |

## 3. 本轮已修复

### 3.1 客户优惠券列表

原问题：

- `GET /api/v1/app/coupons` 未注册，只有 `/my`。
- 日期字段声明为字符串，数据库返回 `datetime` 时可能触发响应校验 500。
- 已过期但数据库仍为 `unused` 的券展示和筛选错误。

当前结果：

```text
GET /api/v1/app/coupons       推荐路径
GET /api/v1/app/coupons/my    兼容路径
```

日期字段已改为 `datetime`，过期状态按有效期动态计算。

### 3.2 管理员发券

已增加：

- 用户存在和软删除校验。
- 重复用户校验。
- 单批最多 500 个用户。
- 模板配额和每人限领校验。
- 同模板并发发放锁。
- 数据库约束异常转换为明确 `409`。

### 3.3 管理员优惠券客户字段

`GET /api/v1/admin/coupons`、发放响应和作废响应现在返回：

```json
{
  "user_id": 12,
  "user_nickname": "客户昵称",
  "user_email": "user@example.com"
}
```

用户信息采用批量查询，避免 N+1 查询。

### 3.4 优惠券使用

已增加：

- 分类券和商品券适用范围校验。
- 按适用商品小计计算折扣。
- 模板 `max_discount` 上限。
- 优惠券核销、作废的 SQL Server 行锁。
- 固定有效期先后校验。
- 模板状态值与数据库统一为 `active/disabled/archived`。

### 3.5 错误日志

未处理异常现在统一返回：

```json
{
  "code": "INTERNAL_SERVER_ERROR",
  "message": "服务器内部错误",
  "details": {}
}
```

完整异常堆栈写入服务端日志，不直接泄露给客户端。

## 4. 全流程覆盖审核

### 4.1 上架商品订单

| 环节 | 接口 | 结论 |
|---|---|---|
| 创建分类/商品/SKU | `/admin/product-categories`、`/admin/products` | 已有 |
| 上传商品图片 | `/admin/products/{id}/images` | 已有 |
| 商品上架 | `/admin/products/{id}/sales-status` | 已有 |
| 客户浏览 | `/app/products` | 已有 |
| 客户下单 | `/app/orders/listed-product` | 已有 |
| 收款确认 | `/admin/orders/{id}/payment-confirm` | 已有 |
| 排期/打印 | `/admin/production-schedule-orders`、`/admin/print-tasks` | 已有 |
| 成品入库 | `/admin/print-tasks/{id}/transfer-to-warehouse` | 已有 |
| 发货/出库 | `/admin/orders/{id}/shipments`、`/admin/warehouse/outbounds/*` | 已有 |
| 客户物流查询 | `/app/orders/{order_no}/shipments` | 已有 |

### 4.2 个性化定制

| 环节 | 接口 | 结论 |
|---|---|---|
| 上传切片文件 | `/app/files/upload` | 已有 |
| 提交申请 | `/app/custom-requests` | 已有 |
| 管理员审核 | `/admin/custom-requests/{id}/review` | 已有 |
| 创建报价 | `/admin/custom-requests/{id}/quote` | 已有 |
| 客户确认 | `/app/quotes/{id}/confirm` | 已有 |
| 后续生产发货 | 复用统一订单流程 | 已有 |

### 4.3 优惠券

| 环节 | 接口 | 结论 |
|---|---|---|
| 创建模板 | `/admin/coupons/templates` | 已有 |
| 停用/归档模板 | `/admin/coupons/templates/{id}/status` | 已补 |
| 管理员发券 | `/admin/coupons/grant` | 已有并加固 |
| 客户抽奖 | `/app/coupons/lottery/draw` | 已有 |
| 客户查询 | `/app/coupons` | 已补 |
| 下单核销 | `/app/orders/listed-product` | 已有并加锁 |

## 5. P0 缺口

### 5.1 通用幂等尚未真正完成

`backend/app/services/idempotency_service.py` 仍为 TODO。多个接口要求 `Idempotency-Key`，但没有统一执行：

- 查询已处理请求。
- 比较请求体哈希。
- 保存首次响应。
- 重复请求复用首次结果。

影响：Flutter 重试、用户连点、Caddy 超时重放仍可能造成重复订单、排期、库存流水或出库单。

### 5.2 订单状态接口过于宽松

```text
PATCH /api/v1/admin/orders/{order_id}/status
```

当前只限制状态值属于枚举，没有限制状态迁移路径。管理员可从 `submitted` 直接改为 `shipped`。应增加服务层迁移矩阵，非法迁移返回 `409 INVALID_STATE_TRANSITION`。

### 5.3 订单取消缺少统一补偿事务

订单取消需要同时处理：

- 已使用优惠券返还策略。
- 材料库存锁释放。
- 成品库存预留释放。
- 排期和打印任务取消。
- 发货单取消限制。

当前没有独立取消接口和完整补偿服务。

### 5.4 云端全流程测试未自动化

当前已有人工测试经验，但尚缺可重复执行、自动生成报告并清理测试数据的全流程测试。

## 6. P1 缺口

- 部分订单、定制、排期响应中的嵌套字段仍使用松散字典。
- 部分状态响应写为 `枚举 | str`，影响 Flutter 类型生成。
- 部分 PATCH 接口仍复用创建模型，不是真正局部更新。
- `page`、`page_size` 并非所有接口都通过 Pydantic 限制范围。
- 优惠券过期状态目前查询时动态计算，尚无定时持久化任务。
- 缺少操作日志查询 API，运维只能查数据库或服务日志。
- Dashboard 尚未完整包含待入库、待发货、待出库等仓库指标。

## 7. OpenAPI 文档质量

优点：

- 197 个 schema，主要请求和响应已有类型。
- 28 个模块 tag 已提供中文职责说明。
- 131 个操作均已提供中文 `summary` 和中文 `description`。
- 业务接口具有 Bearer 鉴权声明。
- 常见错误响应统一声明。
- 优惠券路由、状态和客户归属字段已进入 OpenAPI。

仍需完善：

- 当前中文说明由 OpenAPI 生成阶段统一补充，关键写接口仍应增加专用业务说明。
- 为所有关键写接口增加请求和响应 examples。
- 在 description 中列出业务错误码和允许的前置状态。
- 为状态字段补充中文含义。
- 为文件上传补充大小和类型限制。
- 为幂等接口说明重复 key 的处理规则。

## 8. 推荐实施顺序

1. 实现统一幂等服务并接入订单、排期、库存、仓库写接口。
2. 建立订单状态迁移矩阵和独立取消接口。
3. 编写云端全流程自动化测试。
4. 收紧嵌套响应模型和状态枚举。
5. 增加操作日志查询和仓库 Dashboard 指标。
6. 补全 OpenAPI examples 与业务错误码说明。

## 9. 验收标准

进入稳定前后端联调前至少满足：

- OpenAPI 可生成且 `100 paths / 131 operations` 不发生非预期减少。
- 上架商品和定制订单均能到达 `shipped`。
- 同一幂等键不会创建重复资源。
- 同一优惠券不能被两个订单使用。
- 同一打印任务不能重复入库。
- 同一库存件不能进入多个发货单。
- 数据库异常有请求路径和堆栈日志。
- Flutter 能依据 OpenAPI 区分客户、管理员、状态和错误码。
