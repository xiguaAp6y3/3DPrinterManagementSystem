# AgentOrder 3D Print Farm Backend

阶段1后端基线：

- FastAPI 本地服务。
- Python 3.13。
- SQL Server 数据库。
- Caddy 反向代理暴露 API。
- API 前缀：`/api/v1`。
- 阶段1不接在线支付、不接物流、不接打印机自动控制。

## 1. 初始化环境

```powershell
cd backend
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
$env:PYTHONUTF8="1"
$env:PYTHONIOENCODING="utf-8"
pip install -r requirements.txt
Copy-Item .env.example .env
```

编辑 `.env` 中的 SQL Server 连接信息。

## 编码约定

- 项目源码统一使用 UTF-8，见根目录 `.editorconfig`。
- Python 运行建议启用 `PYTHONUTF8=1` 和 `PYTHONIOENCODING=utf-8`。
- SQL Server 数据库默认使用 `Chinese_PRC_100_CI_AS_SC_UTF8` collation。
- 业务文本字段使用 `NVARCHAR`，这是 SQL Server 中存储中文最稳妥的方式。
- SQL 脚本中的中文字符串必须使用 `N'中文'` 写法，避免被当作非 Unicode 字符串处理。
- 如果本机 SQL Server 版本低于 2019，不支持 `_UTF8` collation，需要把建库语句中的 `COLLATE Chinese_PRC_100_CI_AS_SC_UTF8` 去掉，但仍保留所有业务字段为 `NVARCHAR`。

## 2. 初始化数据库

按顺序在 SQL Server 中执行：

```text
deploy/sql/001_create_tables.sql
deploy/sql/002_create_triggers.sql
deploy/sql/003_seed_dev.sql
```

## 3. 启动后端

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

健康检查：

```text
http://127.0.0.1:8000/health
```

OpenAPI 文档：

```text
http://127.0.0.1:8000/docs
```

## 4. Caddy 暴露 API

配置文件：

```text
deploy/caddy/Caddyfile
```

将 `api.example.com` 替换为你的域名，然后启动 Caddy。

暴露后的检查：

```text
https://你的域名/health
https://你的域名/api/v1/app/products
```

## 5. 当前已实现的接口骨架

客户侧：

- `POST /api/v1/app/auth/login`
- `GET /api/v1/app/products`
- `GET /api/v1/app/products/{product_id}`
- `GET /api/v1/app/products/{product_id}/images`
- `POST /api/v1/app/orders/listed-product`
- `POST /api/v1/app/files/upload`
- `POST /api/v1/app/custom-requests`
- `GET /api/v1/app/custom-requests/{request_id}`
- `PATCH /api/v1/app/custom-requests/{request_id}`
- `GET /api/v1/app/quotes/{quote_id}`
- `POST /api/v1/app/quotes/{quote_id}/confirm`

管理侧：

- `POST /api/v1/admin/auth/login`
- `GET /api/v1/admin/dashboard`
- `GET /api/v1/admin/products`
- `POST /api/v1/admin/products`
- `PATCH /api/v1/admin/products/{product_id}`
- `POST /api/v1/admin/products/{product_id}/images`
- `PATCH /api/v1/admin/products/{product_id}/sales-status`
- `GET /api/v1/admin/products/{product_id}/skus`
- `POST /api/v1/admin/products/{product_id}/skus`
- `PATCH /api/v1/admin/products/skus/{sku_id}`
- `GET /api/v1/admin/orders`
- `GET /api/v1/admin/orders/{order_id}`
- `PATCH /api/v1/admin/orders/{order_id}/status`
- `POST /api/v1/admin/orders/{order_id}/payment-confirm`
- `GET /api/v1/admin/printers`
- `POST /api/v1/admin/printers`
- `PATCH /api/v1/admin/printers/{printer_id}/status`
- `GET /api/v1/admin/production-schedule-orders`
- `POST /api/v1/admin/production-schedule-orders`
- `GET /api/v1/admin/inventory/overview`
- `GET /api/v1/admin/inventory/materials`
- `POST /api/v1/admin/inventory/materials`

## 6. 下一步开发重点

1. 将接口骨架接入 SQLAlchemy service。
2. 实现 `idempotency_keys` 幂等中间层。
3. 实现上架商品下单事务。
4. 实现切片文件落盘与 `model_files` 记录。
5. 实现定制审核、报价、报价确认。
6. 实现人工收款确认。
7. 实现排期主表/明细表和材料库存锁定事务。
