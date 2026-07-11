# 3DPMS

3DPMS 是一个面向 3D 打印农场的管理系统。当前仓库重点是后端 API 与 SQL Server 数据库，前端规划为 Flutter 多端。

## 当前能力

- 客户 APP：邮箱注册登录、商品浏览、上架商品下单、定制申请、文件上传、报价确认、订单和发货查询。
- 管理后台：商品、SKU、商品图片、订单、定制审核、报价、收款确认、打印机、打印任务、排期、材料库存。
- 仓库管理：仓库/库位、打印完成入库、成品库存件、发货单、多快递单号、批量出库。
- 账号管理：后台客户账号 CRUD、后台管理员账号 CRUD，后台账号管理仅 `super_admin` 可操作。
- API 文档：FastAPI 自动生成 Swagger / OpenAPI。

最新 OpenAPI 规模（2026-07-11）：

```text
paths: 100
operations: 131
schemas: 197
```

## 技术栈

- Python 3.13
- FastAPI
- SQLAlchemy 2.x
- SQL Server / Azure SQL
- pyodbc
- JWT + refresh token
- pwdlib[argon2]
- Caddy
- Flutter 多端前端规划

## 目录

```text
backend/          FastAPI 后端项目
deploy/sql/       SQL Server 建表、触发器、开发种子脚本
deploy/caddy/     Caddy 反向代理配置
Design/           路线图、数据库设计、API 可用性报告
```

## 快速开始

后端说明见：

```text
backend/README.md
```

常用地址：

```text
http://127.0.0.1:5000/health
http://127.0.0.1:5000/docs
http://127.0.0.1:5000/openapi.json
```

## 数据库

数据库名固定为：

```text
3DPMS
```

当前 SQL 脚本不使用 `USE` 切换数据库。执行脚本前，请在 SQL Server 客户端中新建连接，并直接连接到 `3DPMS`。

清空数据库后，推荐按顺序执行：

```text
deploy/sql/001_create_tables.sql
deploy/sql/002_create_triggers.sql
deploy/sql/003_seed_dev.sql
```

默认开发管理员：

```text
username: admin
password: admin123456
role: super_admin
```

中文字段使用 SQL Server `NVARCHAR`，SQL 字符串使用 `N'中文'`，不依赖 `_UTF8` collation。

## 当前验证状态

已完成：

```text
python -m compileall app
OpenAPI 导出到 D:\openapi.json
```

尚需在清库重建后执行完整 HTTP 链路验收：

```text
注册 -> 登录 -> 下单 -> 收款确认 -> 排期/打印任务 -> 完成 -> 入库 -> 发货 -> 出库
```

## 重要文档

- [后端 README](C:/Users/Gua3/Desktop/3DPrinterManagementSystem/backend/README.md)
- [已过时：API 运行可用性检测报告](C:/Users/Gua3/Desktop/3DPrinterManagementSystem/Design/已过时-API运行可用性检测报告.md)
- [全流程系统与 API 设计文档](C:/Users/Gua3/Desktop/3DPrinterManagementSystem/Design/全流程系统与API设计文档.md)
- [API 完善性分析报告](C:/Users/Gua3/Desktop/3DPrinterManagementSystem/Design/API完善性分析报告.md)
- [仓库管理与账号体系扩展路线图](C:/Users/Gua3/Desktop/3DPrinterManagementSystem/Design/仓库管理与账号体系扩展路线图.md)
