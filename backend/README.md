# 3DPMS Backend

3DPMS Backend 是 3D 打印农场管理系统的 FastAPI 后端。

当前阶段目标是先稳定数据库结构和 API 契约，支持 Flutter 客户端和电脑端管理后台后续联调。多数接口目前仍是骨架返回，下一步需要接入 SQLAlchemy service、SQL Server 事务和真实鉴权。

## 1. 技术栈

- Python 3.13
- FastAPI
- SQLAlchemy 2.x
- SQL Server
- pyodbc
- Pydantic Settings
- JWT
- pwdlib[argon2]
- Caddy 反向代理

## 2. 运行约定

- 后端本地监听：`127.0.0.1:5000`
- API 前缀：`/api/v1`
- 数据库名：`3DPMS`
- 阶段 1 不接在线支付、不接物流、不接打印机自动控制。
- 打印机状态暂时由管理端人工维护。
- 上架商品为下单后生产，不维护现货售卖库存。

## 3. 初始化环境

在项目根目录执行：

```powershell
cd C:\Users\Gua3\Desktop\3DPrinterManagementSystem\backend
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
$env:PYTHONUTF8="1"
$env:PYTHONIOENCODING="utf-8"
pip install -r requirements.txt
Copy-Item .env.example .env
```

编辑 `.env` 中的 SQL Server 连接信息：

```env
SQLSERVER_HOST=127.0.0.1
SQLSERVER_PORT=1433
SQLSERVER_DATABASE=3DPMS
SQLSERVER_USER=sa
SQLSERVER_PASSWORD=YourStrongPassword
SQLSERVER_DRIVER=ODBC Driver 18 for SQL Server
SQLSERVER_TRUST_CERTIFICATE=true
```

如果 PowerShell 禁止激活虚拟环境，可以临时允许当前进程执行脚本：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

## 4. 编码和中文存储

- 源码统一使用 UTF-8。
- Python 运行建议启用 `PYTHONUTF8=1` 和 `PYTHONIOENCODING=utf-8`。
- SQL Server 中文文本字段使用 `NVARCHAR`。
- SQL 脚本中的中文字符串使用 `N'中文'`。
- 默认不强制 `_UTF8` collation，避免部分 SQL Server 环境报 `Invalid collation`。
- 不要把业务中文文本存进 `VARCHAR` 字段。

## 5. 初始化数据库

第一步：连接到 `master` 或默认数据库，执行建库脚本：

```text
deploy/sql/000_create_database.sql
```

第二步：新建连接，并将连接数据库直接指定为 `3DPMS`，再依次执行：

```text
deploy/sql/001_create_tables.sql
deploy/sql/002_create_triggers.sql
deploy/sql/003_seed_dev.sql
```

如果数据库已经执行过旧版 `001_create_tables.sql`，需要额外执行增量脚本：

```text
deploy/sql/004_auth_refresh_tokens.sql
deploy/sql/005_update_demo_admin_password.sql
```

注意：

- 库内对象脚本不包含 `USE 3DPMS`。
- 如果 SQL 客户端不支持 `USE` 切库，必须用新连接直接连接到 `3DPMS`。
- 不要把脚本改回 `USE AgentOrder` 或其他旧库名。

## 6. 启动后端

如果当前不在 `backend` 目录：

```powershell
cd C:\Users\Gua3\Desktop\3DPrinterManagementSystem\backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --host 127.0.0.1 --port 5000 --reload
```

如果当前已经在 `backend` 目录，直接执行：

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --host 127.0.0.1 --port 5000 --reload
```

不要在 `backend` 目录里再次执行 `cd backend`，否则会进入不存在的 `backend\backend`。

健康检查：

```text
http://127.0.0.1:5000/health
```

Swagger UI：

```text
http://127.0.0.1:5000/docs
```

ReDoc：

```text
http://127.0.0.1:5000/redoc
```

OpenAPI JSON：

```text
http://127.0.0.1:5000/openapi.json
```

## 7. 导出 API 文档

启动后端后，可以下载 OpenAPI 文件：

```powershell
Invoke-WebRequest http://127.0.0.1:5000/openapi.json -OutFile D:\openapi.json
```

也可以在浏览器打开：

```text
http://127.0.0.1:5000/openapi.json
```

然后保存为 `openapi.json`，导入 Apifox、Postman 或前端 SDK 生成工具。

## 8. Caddy 暴露 API

配置文件：

```text
deploy/caddy/Caddyfile
```

默认反向代理目标：

```text
127.0.0.1:5000
```

启动示例：

```powershell
cd C:\Users\Gua3\Desktop\3DPrinterManagementSystem\deploy\caddy
.\caddy run --config Caddyfile
```

将 `api.example.com` 替换为你的真实域名。暴露后检查：

```text
https://你的域名/health
https://你的域名/api/v1/app/products
```

## 9. 认证说明

当前已实现登录 Demo：

- 客户 APP 登录固定验证码：`123456`。
- 新手机号登录会自动创建 `users` 账号。
- 管理端登录读取 `staff_users` 并校验 Argon2 密码 hash。
- 默认开发管理员：`admin / admin123456`。
- 登录返回 `access_token` 和 `refresh_token`。
- `/me` 使用 Bearer access token 查询当前身份。
- `/refresh` 使用 refresh token 轮换并返回新的 access token 和 refresh token。
- `/logout` 撤销 refresh token；已签发的 access token 等待自然过期。

Demo 调用顺序：

```text
POST /api/v1/app/auth/login
GET  /api/v1/app/auth/me
POST /api/v1/app/auth/refresh
POST /api/v1/app/auth/logout

POST /api/v1/admin/auth/login
GET  /api/v1/admin/auth/me
POST /api/v1/admin/auth/refresh
POST /api/v1/admin/auth/logout
```

生成新的管理员密码 hash：

```powershell
cd C:\Users\Gua3\Desktop\3DPrinterManagementSystem\backend
.\.venv\Scripts\python.exe scripts\hash_password.py "你的新密码"
```

## 10. 幂等要求

关键写接口必须传 `Idempotency-Key` Header：

```http
Idempotency-Key: 任意唯一字符串
```

当前已在 OpenAPI 中标记为必填的接口：

- `POST /api/v1/app/orders/listed-product`
- `POST /api/v1/app/custom-requests`
- `POST /api/v1/app/quotes/{quote_id}/confirm`
- `POST /api/v1/admin/orders/{order_id}/payment-confirm`
- `POST /api/v1/admin/production-schedule-orders`
- `POST /api/v1/admin/inventory/materials/{material_id}/stock-logs`

下一步需要将这些接口接入 `idempotency_keys` 表，做到重复请求返回同一业务结果。

## 11. 当前 API 清单

### 系统接口

- `GET /health`

### 客户 APP 端

- `POST /api/v1/app/auth/login`
- `GET /api/v1/app/auth/me`
- `POST /api/v1/app/auth/refresh`
- `POST /api/v1/app/auth/logout`
- `GET /api/v1/app/product-categories`
- `GET /api/v1/app/products`
- `GET /api/v1/app/products/{product_id}`
- `GET /api/v1/app/products/{product_id}/images`
- `GET /api/v1/app/orders`
- `GET /api/v1/app/orders/{order_no}`
- `POST /api/v1/app/orders/listed-product`
- `POST /api/v1/app/files/upload`
- `GET /api/v1/app/files/{file_id}`
- `GET /api/v1/app/files/{file_id}/download-url`
- `DELETE /api/v1/app/files/{file_id}`
- `GET /api/v1/app/custom-requests`
- `POST /api/v1/app/custom-requests`
- `GET /api/v1/app/custom-requests/{request_id}`
- `PATCH /api/v1/app/custom-requests/{request_id}`
- `GET /api/v1/app/quotes/{quote_id}`
- `POST /api/v1/app/quotes/{quote_id}/confirm`

### 管理端

- `POST /api/v1/admin/auth/login`
- `GET /api/v1/admin/auth/me`
- `POST /api/v1/admin/auth/refresh`
- `POST /api/v1/admin/auth/logout`
- `GET /api/v1/admin/dashboard`
- `GET /api/v1/admin/product-categories`
- `POST /api/v1/admin/product-categories`
- `PATCH /api/v1/admin/product-categories/{category_id}`
- `GET /api/v1/admin/products`
- `POST /api/v1/admin/products`
- `GET /api/v1/admin/products/{product_id}`
- `PATCH /api/v1/admin/products/{product_id}`
- `POST /api/v1/admin/products/{product_id}/images`
- `GET /api/v1/admin/products/{product_id}/images`
- `PATCH /api/v1/admin/product-images/{image_id}`
- `DELETE /api/v1/admin/product-images/{image_id}`
- `PATCH /api/v1/admin/products/{product_id}/sales-status`
- `GET /api/v1/admin/products/{product_id}/skus`
- `POST /api/v1/admin/products/{product_id}/skus`
- `PATCH /api/v1/admin/products/skus/{sku_id}`
- `GET /api/v1/admin/orders`
- `GET /api/v1/admin/orders/{order_id}`
- `PATCH /api/v1/admin/orders/{order_id}/status`
- `POST /api/v1/admin/orders/{order_id}/payment-confirm`
- `GET /api/v1/admin/custom-requests`
- `GET /api/v1/admin/custom-requests/{request_id}`
- `PATCH /api/v1/admin/custom-requests/{request_id}/review`
- `POST /api/v1/admin/custom-requests/{request_id}/quote`
- `GET /api/v1/admin/quotes`
- `GET /api/v1/admin/quotes/{quote_id}`
- `GET /api/v1/admin/files/{file_id}`
- `GET /api/v1/admin/files/{file_id}/download-url`
- `GET /api/v1/admin/print-tasks`
- `POST /api/v1/admin/print-tasks`
- `GET /api/v1/admin/print-tasks/{task_id}`
- `PATCH /api/v1/admin/print-tasks/{task_id}/status`
- `GET /api/v1/admin/printers`
- `POST /api/v1/admin/printers`
- `GET /api/v1/admin/printers/{printer_id}`
- `PATCH /api/v1/admin/printers/{printer_id}`
- `PATCH /api/v1/admin/printers/{printer_id}/status`
- `GET /api/v1/admin/production-schedule-orders`
- `POST /api/v1/admin/production-schedule-orders`
- `GET /api/v1/admin/production-schedule-orders/{schedule_order_id}`
- `PATCH /api/v1/admin/production-schedule-orders/{schedule_order_id}`
- `DELETE /api/v1/admin/production-schedule-orders/{schedule_order_id}`
- `GET /api/v1/admin/production-schedule-items/{schedule_item_id}`
- `PATCH /api/v1/admin/production-schedule-items/{schedule_item_id}`
- `GET /api/v1/admin/inventory/overview`
- `GET /api/v1/admin/inventory/materials`
- `POST /api/v1/admin/inventory/materials`
- `GET /api/v1/admin/inventory/materials/{material_id}`
- `PATCH /api/v1/admin/inventory/materials/{material_id}`
- `GET /api/v1/admin/inventory/materials/{material_id}/stock-logs`
- `POST /api/v1/admin/inventory/materials/{material_id}/stock-logs`
- `POST /api/v1/admin/inventory/materials/{material_id}/loss`
- `GET /api/v1/admin/inventory/locks`
- `POST /api/v1/admin/inventory/locks/{lock_id}/release`
- `POST /api/v1/admin/inventory/locks/{lock_id}/consume`
- `GET /api/v1/admin/inventory/finished-goods`

## 12. 业务流程

### 上架商品下单

1. 管理员维护商品、图片和 SKU。
2. 客户 APP 浏览上架商品。
3. 客户选择材料、颜色、尺寸、精度、数量后下单。
4. 系统生成订单，等待人工收款确认。
5. 管理员确认收款。
6. 管理员创建排期和打印任务。
7. 打印任务推进到完成。

### 个性化定制

1. 客户上传切片文件。
2. 客户提交定制表单。
3. 管理员审核。
4. 信息不足则退回补充，无法生产则驳回。
5. 审核通过后管理员报价。
6. 客户确认报价。
7. 必须收款确认后才能排期。
8. 订单可拆分多个打印任务。

### 库存和打印机

1. 材料库存支持入库、调整、损耗。
2. 排期时锁定材料。
3. 取消或变更时释放锁定。
4. 打印完成或确认消耗时扣减材料。
5. 打印机状态第一阶段由管理员人工维护。

## 13. 当前限制

- 接口多数仍未接数据库真实读写。
- 文件上传暂未完成真实落盘记录和鉴权下载。
- 支付状态为人工确认，不接第三方支付。
- 物流不在阶段 1 范围。
- 打印机状态未接 OctoPrint / Klipper。
- OpenAPI 已有响应模型，但返回示例和错误响应模型仍需补充。

## 14. 下一步开发重点

1. 将订单、定制、报价、排期、库存接口接入 SQLAlchemy。
2. 给关键写接口实现幂等键事务。
3. 实现上架商品下单事务。
4. 实现定制审核、人工报价、报价确认、人工收款确认。
5. 实现排期主表/明细表、打印任务拆分和材料库存锁定。
6. 补充 pytest 接口测试。
7. 重新导出 `openapi.json` 并交给前端联调。
