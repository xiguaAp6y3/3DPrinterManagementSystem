# 3DPMS

3DPMS 是一个面向 3D 打印农场的管理系统，当前阶段聚焦后端与数据库能力。

核心目标：

- 电脑端后台集中管理上架商品、订单、库存、打印机状态、排期和打印任务。
- 手机 APP 端支持客户浏览上架商品、提交个性化定制、查询订单和确认报价。
- 后端本地运行 FastAPI 服务，通过 Caddy 将 API 暴露给外部访问。

当前实现以 API 契约和数据库基线为主，业务接口仍是骨架返回，下一步需要接入 SQLAlchemy service 和 SQL Server 事务。

## 技术栈

- Python 3.13
- FastAPI
- SQL Server
- SQLAlchemy 2.x
- pyodbc
- Caddy
- Flutter 多端前端规划

## 目录

```text
backend/          FastAPI 后端项目
deploy/sql/       SQL Server 建库、建表、触发器、开发种子脚本
deploy/caddy/     Caddy 反向代理配置
Design/           阶段路线图、数据库设计、API 缺口分析文档
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

SQL 脚本不使用 `USE` 切换数据库。执行库内对象脚本前，请在 SQL Server 客户端中新建连接并直接连接到 `3DPMS`。

中文字段优先使用 SQL Server `NVARCHAR`，SQL 字符串使用 `N'中文'`，避免中文乱码。

## 当前开发重点

1. 将 API 骨架接入数据库查询和事务。
2. 实现幂等键落库与重复请求返回。
3. 完成上架商品下单、定制审核、人工报价、报价确认、人工收款确认。
4. 完成订单排期、打印任务拆分、材料库存锁定/消耗/释放。
5. 补充接口测试和 OpenAPI 示例。
