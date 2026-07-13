# 明日商品 SKU 价格、优惠券与销售库存最小修改方案

## 1. 修改目标

本次仅修复以下问题，不引入服务端购物车、不重构仓库系统、不修改定制订单流程：

1. 商品本身不再人工维护价格，商品展示价格取有效 SKU 最低价。
2. 商品未配置有效 SKU 时不允许上架。
3. 一张优惠券统一作用于本次订单中所有符合范围的 SKU 商品项。
4. SKU 可配置销售库存；库存充足时显示现货，库存不足时自动按单生产。
5. 主要交互和流程提示由前端优化，关键数据约束仍由后端兜底。

## 2. 统一业务规则

### 2.1 商品价格

- `products.base_price` 不再由管理员输入。
- 商品展示价等于该商品所有 `active` SKU 的最低 `price`。
- 新增、修改、启用、停用 SKU 后，后端重新计算并保存 `products.base_price`。
- 商品没有有效 SKU 时，`base_price` 返回 `0`，前端显示“暂无可售规格”，不显示“0 元起”。

### 2.2 商品上架

商品修改为 `on_sale` 前必须满足：

- 至少存在一个 `status = active` 的 SKU。
- 所有参与销售的 SKU 价格大于或等于 `0`。
- 商品未被删除。

不满足时返回：

```text
409 PRODUCT_HAS_NO_ACTIVE_SKU
商品至少需要一个有效 SKU 才能上架
```

前端应禁用“上架”按钮并显示原因，但后端仍必须执行相同校验，不能只依赖前端。

### 2.3 优惠券

- 每笔订单最多选择一张优惠券。
- 优惠券不是绑定某个 SKU 使用，而是对订单中所有符合范围的商品项统一计算。
- `scope_type = all`：计算全部 SKU 商品项金额。
- `scope_type = product`：计算指定商品下所有已选 SKU 的金额。
- `scope_type = category`：计算指定分类下所有已选 SKU 的金额。
- 不符合范围的商品项保留在订单中，但不参与优惠金额计算。
- 最低消费门槛按“符合优惠范围的商品项金额”判断。

现有后端已经按 `order_items.product_id` 和商品分类汇总优惠金额，本次不新增“SKU 专属券”。前端只需在结算区统一选择一张优惠券，并展示可优惠金额、优惠金额和最终金额。

### 2.4 现货与按单生产

销售库存以 SKU 为单位，不放在商品主表。

```text
sale_stock_quantity > 0  → 显示“现货”
sale_stock_quantity = 0  → 显示“按单生产”
```

下单时按单个订单项判断：

- 销售库存大于或等于购买数量：该订单项为 `in_stock`，扣减销售库存。
- 销售库存小于购买数量：该订单项整体转为 `make_to_order`，不部分扣减库存。
- 同一订单允许同时包含现货项和按单生产项。

销售库存扣减必须在后端事务中完成，并锁定对应 SKU，前端显示结果不能作为最终依据。

## 3. 最小数据库修改

建议新增 `007_add_sku_sales_stock.sql`，只增加两个字段：

```sql
ALTER TABLE dbo.product_skus
ADD sale_stock_quantity INT NOT NULL
    CONSTRAINT DF_product_skus_sale_stock_quantity DEFAULT 0;

ALTER TABLE dbo.product_skus
ADD CONSTRAINT CK_product_skus_sale_stock_quantity
CHECK (sale_stock_quantity >= 0);

ALTER TABLE dbo.order_items
ADD fulfillment_mode NVARCHAR(50) NOT NULL
    CONSTRAINT DF_order_items_fulfillment_mode DEFAULT N'make_to_order';

ALTER TABLE dbo.order_items
ADD CONSTRAINT CK_order_items_fulfillment_mode
CHECK (fulfillment_mode IN (N'in_stock', N'make_to_order'));
```

说明：

- `sale_stock_quantity` 是前台销售可用数量，不替代耗材库存和订单成品库存。
- `fulfillment_mode` 固化下单时的履约决定，避免库存变化后历史订单含义改变。
- 本次不修改 `warehouse_stock_items`，未售现货的库位级管理后续单独设计。

## 4. 最小后端修改

### 4.1 商品与 SKU 接口

调整以下接口：

```text
POST  /api/v1/admin/products
PATCH /api/v1/admin/products/{product_id}
POST  /api/v1/admin/products/{product_id}/skus
PATCH /api/v1/admin/products/skus/{sku_id}
PATCH /api/v1/admin/products/{product_id}/sales-status
GET   /api/v1/app/products
GET   /api/v1/app/products/{product_id}
```

具体变化：

- 商品创建、修改请求不再要求前端提交 `base_price`；即使提交也忽略。
- SKU 请求和响应增加 `sale_stock_quantity`。
- SKU 变更后同步该商品的有效 SKU 最低价到 `base_price`。
- 上架接口增加有效 SKU 校验。
- 客户商品接口增加：

```json
{
  "base_price": 19.90,
  "has_active_sku": true,
  "skus": [
    {
      "id": 1,
      "price": 19.90,
      "sale_stock_quantity": 3,
      "fulfillment_hint": "in_stock"
    }
  ]
}
```

### 4.2 上架商品订单接口

保持原接口路径和请求结构：

```text
POST /api/v1/app/orders/listed-product
```

后端在同一事务中逐项执行：

1. 查询并锁定 SKU。
2. 校验 SKU 有效、商品已上架。
3. 重新读取 SKU 当前价格，不信任前端价格。
4. 判断销售库存是否足够。
5. 库存足够则扣减并记录 `fulfillment_mode = in_stock`。
6. 库存不足则记录 `fulfillment_mode = make_to_order`。
7. 创建全部订单项后统一计算优惠券。
8. 任一步失败则整个订单回滚。

订单详情的每个订单项增加：

```json
{
  "fulfillment_mode": "in_stock"
}
```

## 5. 最小前端修改

### 5.1 管理端

- 删除商品表单中的“基础价格”输入框，改为只读“SKU 最低价”。
- SKU 编辑区域增加“销售库存量”整数输入框。
- 未配置有效 SKU 时禁用上架按钮，并显示“请先添加有效 SKU”。
- SKU 新增、修改、启停后刷新商品列表，显示最新最低价。
- 商品列表显示：`¥最低价起`、有效 SKU 数量、总销售库存。

### 5.2 客户端

- 必须先选择 SKU，才能输入数量并加入结算列表。
- SKU 显示价格和库存提示：

```text
库存 > 0：现货 3 件
库存 = 0：按单生产
```

- 购买数量超过当前库存时，提示“库存不足，本项将按单生产”，但不阻止下单。
- 优惠券在整个结算区统一选择一次，不在每个 SKU 行重复选择。
- 结算区显示：商品合计、适用优惠金额、优惠金额、最终金额。
- 下单成功后以接口返回的 `fulfillment_mode` 为准更新提示。

## 6. 明日实施顺序

1. 执行 `007_add_sku_sales_stock.sql`。
2. 修改 SQLAlchemy 的 `ProductSku` 和 `OrderItem` 模型。
3. 实现 SKU 最低价同步函数。
4. 给商品上架接口增加有效 SKU 校验。
5. 扩展 SKU 管理接口和客户商品响应。
6. 在下单事务中锁定 SKU、判断并扣减销售库存。
7. 确认现有优惠券对多 SKU 订单统一计算。
8. 修改管理端商品/SKU 表单。
9. 修改客户端 SKU、库存和统一优惠券交互。
10. 执行验收用例。

## 7. 最小验收用例

### 用例 A：无 SKU 禁止上架

1. 创建草稿商品，不添加 SKU。
2. 尝试上架。
3. 预期返回 `409 PRODUCT_HAS_NO_ACTIVE_SKU`。

### 用例 B：最低价自动同步

1. 添加价格为 `30` 和 `20` 的两个有效 SKU。
2. 预期商品 `base_price = 20`。
3. 停用价格为 `20` 的 SKU。
4. 预期商品 `base_price = 30`。

### 用例 C：统一优惠券

1. 选择同一商品的两个 SKU，各购买一件。
2. 选择一张商品范围优惠券。
3. 预期两个 SKU 的符合范围金额统一参与优惠计算。
4. 订单只记录一个 `user_coupon_id`。

### 用例 D：现货下单

1. SKU 销售库存为 `3`，购买 `2`。
2. 预期库存变为 `1`。
3. 订单项 `fulfillment_mode = in_stock`。

### 用例 E：库存不足转按单生产

1. SKU 销售库存为 `1`，购买 `2`。
2. 预期库存仍为 `1`，不部分扣减。
3. 订单项 `fulfillment_mode = make_to_order`。

### 用例 F：并发下单

1. SKU 销售库存为 `1`，两个用户同时购买一件。
2. 预期只有一个订单项为 `in_stock`。
3. 另一个订单项自动变为 `make_to_order`，库存不会变为负数。

## 8. 本次明确不做

- 不增加服务端购物车表和购物车接口。
- 不增加 SKU 专属优惠券。
- 不拆分一次下单中的部分现货、部分按单生产数量。
- 不把销售库存与库位级成品库存自动对账。
- 不改造定制订单、排期、打印、入库和发货主流程。

上述内容留到现货仓储模型稳定后再扩展，避免明日修复范围失控。
