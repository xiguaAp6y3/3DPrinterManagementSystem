# 3DPMS Backend

3DPMS Backend 是 3D 打印农场管理系统的 FastAPI 后端，当前阶段聚焦后端 API、SQL Server 数据库和 Flutter/管理后台联调能力。

当前接口已经覆盖基础业务链路，不再是纯骨架接口：

- APP 邮箱注册登录、token refresh、logout。
- 后台管理员登录、token refresh、logout。
- 后台客户账号和管理员账号管理。
- 商品分类、商品、SKU、商品图片。
- APP 商品浏览和上架商品下单。
- APP 文件上传、个性化定制申请、报价确认。
- 管理端定制审核、报价、订单确认收款。
- 打印机、打印任务、排期、材料库存。
- 仓库、库位、生产完成入库、发货单、多快递单、批量出库。

最新 OpenAPI：

```text
paths: 91
operations: 121
```

## 1. 技术栈

- Python 3.13
- FastAPI
- SQLAlchemy 2.x
- SQL Server / Azure SQL
- pyodbc
- Pydantic Settings
- JWT
- pwdlib[argon2]
- Caddy 反向代理

## 2. 运行约定

- 后端本地监听：`127.0.0.1:5000`
- API 前缀：`/api/v1`
- 数据库名：`3DPMS`
- 阶段 1 不接在线支付、不接第三方物流轨迹、不接打印机自动控制。
- 打印机状态暂时由管理端人工维护。
- 上架商品为下单后生产，不维护预售卖现货库存。

## 3. 初始化环境

在项目根目录执行：

```powershell
cd C:\Users\Gua3\Desktop\3DPrinterManagementSystem\backend
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
$env:PYTHONUTF8="1"
$env:PYTHONIOENCODING="utf-8"
pip install -r requirements.txt
```

如果 PowerShell 禁止激活虚拟环境：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

编辑本地 `.env` 的 SQL Server 连接信息。示例：

```env
SQLSERVER_HOST=127.0.0.1
SQLSERVER_PORT=1433
SQLSERVER_DATABASE=3DPMS
SQLSERVER_USER=sa
SQLSERVER_PASSWORD=YourStrongPassword
SQLSERVER_DRIVER=ODBC Driver 18 for SQL Server
SQLSERVER_TRUST_CERTIFICATE=true
```

## 4. 编码和中文存储

- 源码统一使用 UTF-8。
- Python 运行建议启用 `PYTHONUTF8=1` 和 `PYTHONIOENCODING=utf-8`。
- SQL Server 中文文本字段使用 `NVARCHAR`。
- SQL 脚本中的中文字符串使用 `N'中文'`。
- 不强制 `_UTF8` collation，避免部分 SQL Server 环境报 `Invalid collation`。
- ORM 字符串字段使用 SQLAlchemy Unicode 类型，避免中文写入变成 `????`。

## 5. 初始化数据库

数据库名固定为：

```text
3DPMS
```

当前库内 SQL 脚本不包含 `USE 3DPMS`。请在 SQL Server 客户端中新建连接，并直接连接到 `3DPMS` 后执行脚本。

如果你准备清空所有旧表，按顺序执行：

```text
deploy/sql/001_create_tables.sql
deploy/sql/002_create_triggers.sql
deploy/sql/003_seed_dev.sql
```

旧库增量补丁已经移除；当前只维护从空数据库重建的 `001 -> 002 -> 003` 脚本链路。

`003_seed_dev.sql` 会创建：

- 默认超级管理员。
- 默认商品分类。
- 默认材料。
- 默认打印机。
- 默认仓库和库位。

默认管理员：

```text
username: admin
password: admin123456
role: super_admin
```

注意：

- 不要把脚本改回 `USE AgentOrder` 或其他旧库名。
- 不要使用 SQL Server `_UTF8` collation。
- 如果历史数据已经写成 `????`，无法自动恢复，需要重新录入。

## 6. 启动后端

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

常用地址：

```text
http://127.0.0.1:5000/health
http://127.0.0.1:5000/docs
http://127.0.0.1:5000/redoc
http://127.0.0.1:5000/openapi.json
```

## 7. 导出 API 文档

启动后端后：

```powershell
Invoke-WebRequest http://127.0.0.1:5000/openapi.json -OutFile D:\openapi.json
```

也可以不启动后端，直接从应用对象导出：

```powershell
cd C:\Users\Gua3\Desktop\3DPrinterManagementSystem\backend
.\.venv\Scripts\python.exe -c "from app.main import app; import json; spec=app.openapi(); open(r'D:\openapi.json','w',encoding='utf-8').write(json.dumps(spec, ensure_ascii=False, indent=2)); print(len(spec['paths']), sum(len(v) for v in spec['paths'].values()))"
```

当前应输出：

```text
91 121
```

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

暴露后检查：

```text
https://你的域名/health
https://你的域名/api/v1/app/products
```

## 9. 认证说明

APP 正式登录：

```text
POST /api/v1/app/auth/register
POST /api/v1/app/auth/login
GET  /api/v1/app/auth/me
POST /api/v1/app/auth/refresh
POST /api/v1/app/auth/logout
```

APP 旧测试登录保留：

```text
POST /api/v1/app/auth/login-demo
```

`login-demo` 使用手机号 + 固定验证码：

```text
123456
```

管理端登录：

```text
POST /api/v1/admin/auth/login
GET  /api/v1/admin/auth/me
POST /api/v1/admin/auth/refresh
POST /api/v1/admin/auth/logout
```

默认开发管理员：

```text
admin / admin123456
```

登录返回：

- `access_token`
- `refresh_token`
- `token_type = Bearer`

`/refresh` 会轮换 refresh token。`/logout` 会撤销 refresh token，已签发 access token 等待自然过期。

生成新的密码 hash：

```powershell
cd C:\Users\Gua3\Desktop\3DPrinterManagementSystem\backend
.\.venv\Scripts\python.exe scripts\hash_password.py "你的新密码"
```

## 10. 关键接口清单

### 系统接口

```text
GET /health
```

### APP 端

```text
POST /api/v1/app/auth/register
POST /api/v1/app/auth/login
POST /api/v1/app/auth/login-demo
GET  /api/v1/app/auth/me
POST /api/v1/app/auth/refresh
POST /api/v1/app/auth/logout

GET  /api/v1/app/product-categories
GET  /api/v1/app/products
GET  /api/v1/app/products/{product_id}
GET  /api/v1/app/products/{product_id}/images

POST /api/v1/app/orders/listed-product
GET  /api/v1/app/orders
GET  /api/v1/app/orders/{order_no}
GET  /api/v1/app/orders/{order_no}/shipments

POST /api/v1/app/files/upload
GET  /api/v1/app/files/{file_id}
GET  /api/v1/app/files/{file_id}/download
GET  /api/v1/app/files/{file_id}/download-url
DELETE /api/v1/app/files/{file_id}

POST /api/v1/app/custom-requests
GET  /api/v1/app/custom-requests
GET  /api/v1/app/custom-requests/{request_id}
PATCH /api/v1/app/custom-requests/{request_id}

GET  /api/v1/app/quotes/{quote_id}
POST /api/v1/app/quotes/{quote_id}/confirm
```

### 管理端账号

```text
GET/POST/PATCH/DELETE /api/v1/admin/users
PATCH /api/v1/admin/users/{user_id}/status
POST  /api/v1/admin/users/{user_id}/reset-password

GET/POST/PATCH/DELETE /api/v1/admin/staff-users
PATCH /api/v1/admin/staff-users/{staff_user_id}/status
POST  /api/v1/admin/staff-users/{staff_user_id}/reset-password
```

### 商品和订单

```text
GET/POST/PATCH /api/v1/admin/product-categories
GET/POST/PATCH /api/v1/admin/products
PATCH /api/v1/admin/products/{product_id}/sales-status
GET/POST /api/v1/admin/products/{product_id}/skus
PATCH /api/v1/admin/products/skus/{sku_id}
POST /api/v1/admin/products/{product_id}/images
GET  /api/v1/admin/products/{product_id}/images
PATCH /api/v1/admin/product-images/{image_id}
DELETE /api/v1/admin/product-images/{image_id}

GET /api/v1/admin/orders
GET /api/v1/admin/orders/{order_id}
PATCH /api/v1/admin/orders/{order_id}/status
POST /api/v1/admin/orders/{order_id}/payment-confirm
```

### 定制和报价

```text
GET /api/v1/admin/custom-requests
GET /api/v1/admin/custom-requests/{request_id}
PATCH /api/v1/admin/custom-requests/{request_id}/review
POST /api/v1/admin/custom-requests/{request_id}/quote
GET /api/v1/admin/quotes
GET /api/v1/admin/quotes/{quote_id}
```

### 生产、排期、库存

```text
GET/POST/PATCH /api/v1/admin/printers
PATCH /api/v1/admin/printers/{printer_id}/status

GET/POST /api/v1/admin/print-tasks
GET /api/v1/admin/print-tasks/{task_id}
PATCH /api/v1/admin/print-tasks/{task_id}/status

GET/POST/PATCH/DELETE /api/v1/admin/production-schedule-orders
GET/PATCH /api/v1/admin/production-schedule-items/{schedule_item_id}

GET /api/v1/admin/inventory/overview
GET/POST/PATCH /api/v1/admin/inventory/materials
GET/POST /api/v1/admin/inventory/materials/{material_id}/stock-logs
POST /api/v1/admin/inventory/materials/{material_id}/loss
GET /api/v1/admin/inventory/locks
POST /api/v1/admin/inventory/locks/{lock_id}/release
POST /api/v1/admin/inventory/locks/{lock_id}/consume
GET /api/v1/admin/inventory/finished-goods
```

### 仓库、发货、出库

```text
GET/POST/PATCH /api/v1/admin/warehouses
GET/POST/PATCH /api/v1/admin/warehouse-locations

POST /api/v1/admin/print-tasks/{task_id}/transfer-to-warehouse
POST /api/v1/admin/orders/{order_id}/transfer-to-warehouse
GET  /api/v1/admin/warehouse/stock-items
GET  /api/v1/admin/warehouse/inbounds

POST   /api/v1/admin/orders/{order_id}/shipments
GET    /api/v1/admin/orders/{order_id}/shipments
PATCH  /api/v1/admin/shipments/{shipment_id}
DELETE /api/v1/admin/shipments/{shipment_id}

POST /api/v1/admin/warehouse/outbounds/batch
POST /api/v1/admin/warehouse/outbounds/{outbound_id}/confirm
GET  /api/v1/admin/warehouse/outbounds
GET  /api/v1/admin/warehouse/outbounds/{outbound_id}
```

## 11. 主业务流程

### 上架商品下单后生产

1. 管理员维护商品、图片和 SKU。
2. 客户 APP 浏览上架商品。
3. 客户选择规格后下单。
4. 管理员确认收款。
5. 管理员创建排期和打印任务。
6. 打印任务完成后进入 `pending_inbound`。
7. 管理员将打印任务转移入库。
8. 订单全部打印任务入库后变为 `ready_to_ship`。
9. 管理员创建发货单，填写一个或多个快递单号。
10. 管理员批量出库。
11. 订单全部库存件出库后变为 `shipped`。

### 个性化定制

1. 客户上传切片文件。
2. 客户提交定制表单。
3. 管理员审核。
4. 信息不足则退回补充，无法生产则驳回。
5. 审核通过后管理员报价。
6. 客户确认报价。
7. 管理员确认收款。
8. 订单排期、打印、入库、发货、出库。

## 12. 幂等要求

关键写接口需要传：

```http
Idempotency-Key: 任意唯一字符串
```

当前多个接口已在 OpenAPI 中声明该 Header，但“相同 key 返回第一次业务响应”的完整幂等复用还需要继续增强。

优先补齐：

- APP 下单。
- 确认报价。
- 确认收款。
- 创建排期。
- 转移入库。
- 创建发货单。
- 批量出库。
- 确认出库。

## 13. 当前验证状态

已通过：

```powershell
.\.venv\Scripts\python.exe -m compileall app
```

OpenAPI 导出：

```text
D:\openapi.json
paths: 91
operations: 121
```

尚需在数据库清空并重建后进行 HTTP 全链路验收。

建议验收顺序：

```text
注册 -> 登录 -> 创建商品 -> 下单 -> 确认收款 -> 创建打印任务 -> 完成打印 -> 入库 -> 创建发货单 -> 批量出库 -> 确认订单 shipped
```

## 14. 当前限制

- 细粒度 RBAC 权限表尚未实现，目前主要依赖 `staff_users.role`。
- 第三方支付不在阶段 1 范围。
- 第三方物流轨迹不在阶段 1 范围，当前只保存快递公司和单号。
- 打印机未接 OctoPrint / Klipper，状态由管理员人工维护。
- 出库撤销、退货入库、盘点、库存件调整属于仓库二期。
- Dashboard 已有基础统计，但待补仓库待办、待入库、待出库等统计。
