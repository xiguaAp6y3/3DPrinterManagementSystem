# 购物车、订单明细与排期任务接口更新

## 部署前准备

先执行 `deploy/sql/008_add_print_task_planned_quantity.sql`。该脚本为 `print_tasks` 增加 `planned_quantity` 字段，已有任务默认数量为 `1`。

客户测试前端位于 `C:\Users\Gua3\Desktop\test`：运行 `python app.py` 后访问 `http://127.0.0.1:3000`。前端通过其 `/api-proxy/*` 转发请求到配置的后端。

## 订单商品明细

### 客户订单列表

`GET /api/v1/app/orders`

列表中每个订单新增 `items`，让客户无需进入详情也能看到购买内容：

```json
{
  "id": 101,
  "order_no": "OD202607140001",
  "items": [
    {
      "id": 501,
      "product_id": 12,
      "sku_id": 31,
      "item_name": "桌面收纳盒",
      "sku_label": "黑色 / 大号 / 标准",
      "quantity": 2,
      "produced_quantity": 0,
      "inbounded_quantity": 0,
      "shipped_quantity": 0
    }
  ]
}
```

`GET /api/v1/app/orders/{order_no}` 与 `GET /api/v1/admin/orders/{order_id}` 使用相同的 `items` 字段。商家订单列表 `GET /api/v1/admin/orders` 也返回该字段。

`sku_label` 由 SKU 的颜色、尺寸和精度组合而成；定制订单没有 SKU 时为 `null`。

## 购物车与下单

购物车保存在客户浏览器的 `localStorage`，键名为 `app_cart_items`，不新增服务端购物车表。

提交时前端调用既有接口：

`POST /api/v1/app/orders/listed-product`

```json
{
  "items": [
    { "sku_id": 31, "quantity": 2 },
    { "sku_id": 32, "quantity": 1 }
  ],
  "customer_note": null,
  "coupon_id": null
}
```

同一 SKU 在购物车中会自动合并数量；后端仍会执行 SKU 状态、最小/最大购买数量和库存履约方式校验。

订单可以包含不同商品的 SKU。例如 `sku_id: 31` 和 `sku_id: 32` 可以分别属于不同的 `product_id`；后端会为每个 SKU 分别创建对应的订单明细，并保留各自的商品、SKU、数量和履约状态。唯一限制是同一 SKU 在一次请求中只能出现一次，重复数量应由前端合并后填写在 `quantity` 中。

## 打印任务数量与物品

`PrintTask` 及 `POST /api/v1/admin/print-tasks` 新增字段：

```json
{
  "order_id": 101,
  "order_item_id": 501,
  "printer_id": 8,
  "planned_quantity": 2,
  "plate_count": 1
}
```

- `order_item_id` 绑定订单中的具体商品/SKU；多商品订单必须提供该字段。
- `planned_quantity` 是本任务计划打印的成品数量，默认 `1`。
- `plate_count` 仍表示切片盘数，不再替代成品数量。
- 打印任务列表/详情新增 `item`，内容与订单 `items` 中单项一致。

## 排期内批量分配打印物品

### 查询排期详情

`GET /api/v1/admin/production-schedule-orders/{schedule_order_id}`

响应新增：

- `order_items`：该订单可被分配的商品和 SKU。
- `print_tasks`：该订单已有的打印任务及其 `planned_quantity`。
- `items[].print_task`：排期明细关联的具体打印任务。

### 批量创建并加入排期

`POST /api/v1/admin/production-schedule-orders/{schedule_order_id}/print-tasks`

```json
{
  "tasks": [
    {
      "order_item_id": 501,
      "printer_id": 8,
      "scheduled_start_at": "2026-07-14T09:00:00+08:00",
      "scheduled_end_at": "2026-07-14T12:00:00+08:00",
      "planned_quantity": 2,
      "plate_count": 1,
      "priority": 0,
      "use_ams": false
    },
    {
      "order_item_id": 502,
      "printer_id": 9,
      "scheduled_start_at": "2026-07-14T13:00:00+08:00",
      "scheduled_end_at": "2026-07-14T16:00:00+08:00",
      "planned_quantity": 1,
      "plate_count": 1
    }
  ]
}
```

每个 `tasks` 项同时创建一条 `print_tasks` 和一条 `production_schedule_items`。同一 `order_item_id` 可重复出现，用于将相同商品分派到多个打印机或不同时间段。

校验规则：

- 排期不能是 `cancelled`。
- 订单明细必须属于该排期关联的订单。
- 打印机必须存在。
- 每项结束时间必须晚于开始时间，并且时间区间必须落在排期总时间范围内。
