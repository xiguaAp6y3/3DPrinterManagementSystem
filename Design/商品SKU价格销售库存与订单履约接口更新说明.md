# 商品 SKU 价格、销售库存与订单履约接口更新说明

## 1. 文档信息

- 更新日期：2026-07-13
- API 前缀：`/api/v1`
- 适用后端：FastAPI + SQLAlchemy + SQL Server
- 涉及客户端：电脑管理端、手机客户 App
- 数据库增量脚本：`deploy/sql/007_add_sku_sales_stock.sql`

本次更新不新增服务端购物车，不修改定制订单、排期、打印、入库和发货主流程。主要解决商品价格来源、无 SKU 商品上架、SKU 销售库存、下单履约方式以及多 SKU 订单统一使用优惠券的问题。

## 2. 上线前置条件

已有数据库必须先执行：

```text
deploy/sql/007_add_sku_sales_stock.sql
```

脚本会完成以下操作：

1. 为 `product_skus` 增加 `sale_stock_quantity`。
2. 为 `order_items` 增加 `fulfillment_mode`。
3. 将商品 `base_price` 回填为有效 SKU 最低价。
4. 将没有有效 SKU 的已上架商品调整为 `off_sale`。
5. 增加销售库存非负约束和履约方式枚举约束。

执行顺序：停止后端服务，备份数据库，执行 `007`，确认成功后部署后端代码并重启服务。

## 3. 通用约定

### 3.1 认证

- `/api/v1/admin/*`：使用管理员 Bearer Token。
- `/api/v1/app/*`：使用客户 Bearer Token。

```http
Authorization: Bearer <access_token>
Content-Type: application/json; charset=utf-8
```

### 3.2 成功响应

```json
{
  "code": "OK",
  "message": "success",
  "data": {}
}
```

### 3.3 失败响应

```json
{
  "code": "PRODUCT_HAS_NO_ACTIVE_SKU",
  "message": "商品至少需要一个有效 SKU 才能上架",
  "details": {}
}
```

### 3.4 字段含义

| 字段 | 含义 |
| --- | --- |
| `base_price` | 商品所有 `active` SKU 的最低价格，由后端维护，只用于展示 |
| `sale_stock_quantity` | SKU 当前销售可用现货数量，必须为非负整数 |
| `total_sale_stock_quantity` | 商品全部有效 SKU 的销售库存合计 |
| `has_active_sku` | 商品是否至少有一个有效 SKU |
| `active_sku_count` | 商品有效 SKU 数量，仅管理端商品响应返回 |
| `fulfillment_hint` | 根据当前库存生成的下单前提示，不是最终履约承诺 |
| `fulfillment_mode` | 下单事务提交时固化的订单项履约方式 |
| `fulfillment_modes` | 一笔订单包含的履约方式去重列表 |

履约方式取值：

- `in_stock`：销售库存充足，订单创建时已扣减相应销售库存。
- `make_to_order`：销售库存不足，订单项整体按单生产，销售库存不扣减。

## 4. 本次调整的接口

| 方法 | 接口 | 主要变化 |
| --- | --- | --- |
| `POST` | `/admin/products` | 商品价格不再由请求维护；创建时不能直接上架 |
| `PATCH` | `/admin/products/{product_id}` | 忽略商品价格；上架时校验有效 SKU |
| `PATCH` | `/admin/products/{product_id}/sales-status` | 上架时校验商品未删除且存在有效 SKU |
| `GET` | `/admin/products` | 返回最低价、有效 SKU 数量和销售库存合计 |
| `GET` | `/admin/products/{product_id}` | 返回最低价、有效 SKU 数量和销售库存合计 |
| `POST` | `/admin/products/{product_id}/skus` | 请求和响应增加 SKU 销售库存 |
| `GET` | `/admin/products/{product_id}/skus` | 返回销售库存和履约提示 |
| `PATCH` | `/admin/products/skus/{sku_id}` | 支持部分修改价格、销售库存和状态 |
| `GET` | `/app/products` | 返回商品最低价和销售库存合计 |
| `GET` | `/app/products/{product_id}` | SKU 返回销售库存和履约提示 |
| `POST` | `/app/orders/listed-product` | 锁定 SKU、扣减销售库存、固化履约方式并统一计算优惠券 |
| `GET` | `/app/orders` | 订单摘要增加 `fulfillment_modes` |
| `GET` | `/app/orders/{order_no}` | 订单项增加 `fulfillment_mode` |
| `GET` | `/admin/orders/{order_id}` | 管理端订单项增加 `fulfillment_mode` |

## 5. 管理端商品接口

### 5.1 创建商品

```http
POST /api/v1/admin/products
```

请求示例：

```json
{
  "category_id": 1,
  "name": "桌面收纳盒",
  "description": "PLA 材质桌面收纳盒",
  "sales_status": "draft",
  "production_mode": "make_to_order",
  "supports_custom_note": true
}
```

变更说明：

- 请求不再包含 `base_price`。
- 即使旧客户端继续提交 `base_price`，该字段也不会参与商品价格写入。
- 新商品应先以 `draft` 创建，添加有效 SKU 后再调用上架接口。
- 创建时直接提交 `sales_status = on_sale` 返回 `409 PRODUCT_HAS_NO_ACTIVE_SKU`。

### 5.2 修改商品

```http
PATCH /api/v1/admin/products/{product_id}
```

请求示例：

```json
{
  "name": "桌面收纳盒 Pro",
  "description": "更新后的商品描述",
  "supports_custom_note": false
}
```

该接口不再允许前端直接修改 `base_price`。商品名称允许按现有规则重复，商品价格仅由 SKU 同步。

### 5.3 修改销售状态

```http
PATCH /api/v1/admin/products/{product_id}/sales-status
```

请求示例：

```json
{
  "sales_status": "on_sale"
}
```

上架条件：

1. 商品存在且未被软删除。
2. 至少存在一个 `status = active` 的 SKU。
3. SKU 价格满足非负约束。

上架失败示例：

```json
{
  "code": "PRODUCT_HAS_NO_ACTIVE_SKU",
  "message": "商品至少需要一个有效 SKU 才能上架",
  "details": {}
}
```

已删除商品返回：

```json
{
  "code": "PRODUCT_DELETED",
  "message": "已删除商品不能上架",
  "details": {}
}
```

### 5.4 商品响应新增字段

适用于管理端商品列表、商品详情、创建、修改和状态修改响应。

```json
{
  "id": 100,
  "name": "桌面收纳盒",
  "base_price": 19.9,
  "has_active_sku": true,
  "active_sku_count": 2,
  "total_sale_stock_quantity": 8,
  "sales_status": "on_sale"
}
```

规则：

- `base_price` 等于全部有效 SKU 的最低 `price`。
- 没有有效 SKU 时，`base_price = 0`、`has_active_sku = false`。
- 前端在 `has_active_sku = false` 时应显示“暂无可售规格”，不能显示“0 元起”。

## 6. 管理端 SKU 接口

### 6.1 创建 SKU

```http
POST /api/v1/admin/products/{product_id}/skus
```

请求示例：

```json
{
  "material_id": 12,
  "color": "黑色",
  "size_label": "标准",
  "precision_level": "0.20mm",
  "price": 29.9,
  "sale_stock_quantity": 5,
  "min_quantity": 1,
  "max_quantity": 20,
  "status": "active"
}
```

`sale_stock_quantity` 可省略，默认值为 `0`。创建成功后，后端立即重新计算所属商品的 `base_price`。

响应核心字段：

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "id": 501,
    "product_id": 100,
    "price": 29.9,
    "sale_stock_quantity": 5,
    "fulfillment_hint": "in_stock",
    "min_quantity": 1,
    "max_quantity": 20,
    "status": "active"
  }
}
```

### 6.2 查询商品 SKU

```http
GET /api/v1/admin/products/{product_id}/skus
```

响应中的每个 SKU 都包含 `sale_stock_quantity` 和 `fulfillment_hint`。管理端接口会同时返回有效和停用的 SKU，前端需要根据 `status` 区分。

### 6.3 部分修改 SKU

```http
PATCH /api/v1/admin/products/skus/{sku_id}
```

本接口现在支持真正的部分更新，不需要重复提交完整 SKU。

仅调整销售库存：

```json
{
  "sale_stock_quantity": 10
}
```

仅修改价格：

```json
{
  "price": 25.5
}
```

仅停用 SKU：

```json
{
  "status": "inactive"
}
```

价格或状态修改成功后，商品最低价会在同一事务中重新计算。已上架商品的最后一个有效 SKU 不允许被停用，否则返回 `409 PRODUCT_HAS_NO_ACTIVE_SKU`。

字段约束：

- `price >= 0`
- `sale_stock_quantity >= 0` 且必须是整数
- `min_quantity > 0`
- `status` 只能是 `active` 或 `inactive`

## 7. 客户端商品接口

### 7.1 商品列表

```http
GET /api/v1/app/products
```

商品列表项新增：

```json
{
  "id": 100,
  "name": "桌面收纳盒",
  "base_price": 19.9,
  "has_active_sku": true,
  "total_sale_stock_quantity": 8
}
```

`total_sale_stock_quantity` 只用于商品列表概览，不能据此判断某一个 SKU 是否有现货。

### 7.2 商品详情

```http
GET /api/v1/app/products/{product_id}
```

客户商品详情只返回 `active` SKU。SKU 新增字段示例：

```json
{
  "id": 501,
  "product_id": 100,
  "color": "黑色",
  "size_label": "标准",
  "precision_level": "0.20mm",
  "price": 29.9,
  "sale_stock_quantity": 5,
  "fulfillment_hint": "in_stock",
  "min_quantity": 1,
  "max_quantity": 20,
  "status": "active"
}
```

`fulfillment_hint` 计算规则：

```text
sale_stock_quantity > 0  -> in_stock
sale_stock_quantity = 0  -> make_to_order
```

该字段只表示查询时的库存提示。多人同时下单时库存可能发生变化，最终结果必须以下单响应和订单详情中的 `fulfillment_mode` 为准。

## 8. 客户端上架商品下单接口

### 8.1 创建订单

```http
POST /api/v1/app/orders/listed-product
Idempotency-Key: <客户端生成的唯一值>
```

请求示例：

```json
{
  "items": [
    {
      "sku_id": 501,
      "quantity": 2,
      "custom_note": "表面不要打磨"
    },
    {
      "sku_id": 502,
      "quantity": 1,
      "custom_note": null
    }
  ],
  "customer_note": "工作日发货",
  "coupon_id": 88
}
```

请求规则：

1. `items` 至少包含一项。
2. 同一请求中不能重复提交相同 `sku_id`；相同 SKU 应由前端合并数量。
3. `quantity` 必须符合 SKU 的 `min_quantity` 和 `max_quantity`。
4. 商品必须已上架，SKU 必须为 `active`。
5. 单价由后端读取 SKU 当前价格，不接受前端传价。
6. 每笔订单最多使用一张优惠券。
7. `Idempotency-Key` 请求头为必填。当前接口要求客户端提供该值，但完整的重复请求结果重放仍需后续统一幂等服务接入；前端同时应在提交期间禁用按钮。

### 8.2 库存与履约事务

后端按 SKU 编号排序并使用 SQL Server `UPDLOCK, HOLDLOCK` 锁定 SKU 行：

- 当前库存大于或等于购买数量：扣减库存，订单项记录 `in_stock`。
- 当前库存小于购买数量：不扣减库存，订单项整体记录 `make_to_order`。
- 不会将一条订单项拆成“部分现货、部分生产”。
- 任一商品、SKU、数量或优惠券校验失败时，订单创建和本次库存扣减一起回滚。

### 8.3 优惠券计算

`coupon_id` 对整笔订单统一处理：

- `scope_type = all`：全部 SKU 订单项参与计算。
- `scope_type = product`：目标商品下的所有已选 SKU 参与计算。
- `scope_type = category`：目标分类下的所有已选 SKU 参与计算。
- 不适用的订单项保留，但不计入优惠基数。
- 满减门槛按符合范围的订单项金额判断。
- 订单只保存一个 `user_coupon_id`。

### 8.4 创建成功响应

```json
{
  "code": "OK",
  "message": "success",
  "data": {
    "id": 9001,
    "order_no": "OD202607130001",
    "order_type": "listed_product",
    "status": "submitted",
    "total_amount": 68.82,
    "payment_status": "unconfirmed",
    "item_count": 2,
    "fulfillment_modes": [
      "in_stock",
      "make_to_order"
    ],
    "user_coupon_id": 88,
    "coupon_discount_amount": 7.98,
    "created_at": "2026-07-13T15:30:00"
  }
}
```

`fulfillment_modes` 是订单内订单项履约方式的去重集合，顺序不应作为业务依据。

## 9. 订单查询接口

### 9.1 客户订单列表

```http
GET /api/v1/app/orders
```

每个订单摘要增加：

```json
{
  "fulfillment_modes": ["in_stock", "make_to_order"]
}
```

### 9.2 客户订单详情

```http
GET /api/v1/app/orders/{order_no}
```

每个 `items[]` 增加：

```json
{
  "sku_id": 501,
  "quantity": 2,
  "fulfillment_mode": "in_stock"
}
```

### 9.3 管理端订单详情

```http
GET /api/v1/admin/orders/{order_id}
```

管理端每个 `items[]` 同样增加 `fulfillment_mode`，用于判断该订单项应从现货流程处理还是进入生产流程。

## 10. 主要错误码

| HTTP 状态 | `code` | 场景 |
| --- | --- | --- |
| `401` | 认证相关错误 | Token 缺失、无效或过期 |
| `403` | 权限相关错误 | 客户调用管理端接口或权限不足 |
| `404` | 实体不存在错误 | 商品、SKU、订单或优惠券不存在 |
| `409` | `PRODUCT_HAS_NO_ACTIVE_SKU` | 无有效 SKU 时上架，或停用已上架商品最后一个有效 SKU |
| `409` | `PRODUCT_DELETED` | 尝试上架已删除商品 |
| `409` | `DUPLICATE_ORDER_SKU` | 同一订单重复提交相同 SKU |
| `409` | `SKU_QUANTITY_INVALID` | 数量不符合 SKU 最小或最大购买量 |
| `409` | `DATABASE_CONSTRAINT_VIOLATION` | 违反数据库价格、库存或枚举约束 |
| `409` | 优惠券业务错误 | 优惠券不适用、已使用、已过期或未满足门槛 |
| `422` | `VALIDATION_ERROR` | 字段类型、必填项或数值范围校验失败 |

## 11. 前端适配要求

### 11.1 管理端

1. 商品价格改为只读展示，不再提交 `base_price`。
2. 商品创建默认使用 `draft`。
3. 添加有效 SKU 后再调用销售状态接口上架。
4. SKU 表单增加 `sale_stock_quantity` 非负整数输入。
5. SKU 价格、状态或库存更新后重新获取商品和 SKU 数据。
6. `has_active_sku = false` 时显示“暂无可售规格”并禁用上架操作。

### 11.2 客户端

1. SKU 选项展示价格和 `sale_stock_quantity`。
2. 数量超过销售库存时提示“库存不足，本项将整体按单生产”，但允许提交。
3. 优惠券在订单结算层选择一次，不在每个 SKU 行分别选择。
4. 下单成功后使用 `fulfillment_modes` 更新订单级提示。
5. 订单详情使用每个订单项的 `fulfillment_mode` 展示最终履约结果。
6. 不使用 `fulfillment_hint` 代替下单结果，也不在客户端自行扣减库存。

## 12. 兼容性和范围说明

- `products.base_price` 字段继续保留，作为有效 SKU 最低价缓存，旧版商品响应仍可读取该字段。
- 旧客户端提交商品 `base_price` 不会改变实际价格，应尽快删除该提交字段。
- `sale_stock_quantity` 是销售可用数量，不替代 `warehouse_stock_items`、材料库存、成品库存或库位库存。
- 本次没有实现销售库存与仓库实物库存自动对账。
- `in_stock` 只表示下单时已占用销售现货，后续仓库出库仍按既有仓库流程执行。
- `make_to_order` 继续进入既有排期、打印、入库和发货流程。
- 本次没有新增 SKU 专属优惠券，也没有新增服务端购物车接口。

## 13. 最小验收清单

1. 无 SKU 商品上架返回 `409 PRODUCT_HAS_NO_ACTIVE_SKU`。
2. 新增价格 `30` 和 `20` 的有效 SKU 后，商品 `base_price = 20`。
3. 停用价格 `20` 的 SKU 后，商品 `base_price = 30`。
4. SKU 库存为 `3`、购买 `2` 后，库存变为 `1`，订单项为 `in_stock`。
5. SKU 库存为 `1`、购买 `2` 后，库存仍为 `1`，订单项为 `make_to_order`。
6. 两个不同 SKU 使用一张商品券时，符合范围的订单项统一参与优惠计算。
7. 同一订单重复提交相同 SKU 时返回 `409 DUPLICATE_ORDER_SKU`。
8. 两个用户并发购买最后一件现货时，最多一个订单项为 `in_stock`，库存不会小于 `0`。
9. 客户订单详情和管理端订单详情均能读取 `fulfillment_mode`。

