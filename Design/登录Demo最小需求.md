# 登录 Demo 最小需求

创建时间：2026-07-08  
适用阶段：当前登录 Demo 阶段

## 1. 目标

当前阶段只实现一个可运行的登录 Demo，不做完整认证系统。

最小闭环：

```text
创建/保存账号 -> 登录返回 token -> 携带 token 调用受保护 API -> 定期刷新 token
```

## 2. 当前已有能力

| 能力 | 当前状态 |
|---|---|
| JWT 生成 | 已有 |
| Bearer Token 校验 | 已有 |
| APP 登录接口 | 已实现：固定验证码 + 自动创建用户 |
| 管理端登录接口 | 已实现：查询 `staff_users` + Argon2 密码校验 |
| `users` 表 | 已有 |
| `staff_users` 表 | 已有 |
| `auth_refresh_tokens` 表 | 已新增脚本和 ORM |
| `/me` 查询 | 已实现 |
| `/refresh` 刷新 | 已实现，采用 refresh token 轮换 |
| `/logout` 退出 | 已实现，撤销 refresh token |

当前仍不做：

- 真实短信验证码。
- 完整 RBAC 权限。
- 登录审计和失败锁定。
- 多设备管理和强制下线。

## 3. 本阶段必须实现

### 3.1 APP 登录 Demo

接口：

```text
POST /api/v1/app/auth/login
```

请求：

```json
{
  "phone": "13800000000",
  "code": "123456"
}
```

规则：

- 当前阶段使用固定验证码 `123456`。
- 如果手机号不存在，自动创建 `users`。
- 如果手机号已存在，直接登录。
- 如果用户状态不是 `active`，拒绝登录。
- 登录成功返回 `access_token` 和 `refresh_token`。

### 3.2 管理端登录 Demo

接口：

```text
POST /api/v1/admin/auth/login
```

请求：

```json
{
  "username": "admin",
  "password": "admin123456"
}
```

规则：

- 查询 `staff_users.username`。
- 校验 `status = active`。
- 使用密码哈希校验密码。
- 登录成功返回 `access_token` 和 `refresh_token`。

### 3.3 当前用户信息

APP：

```text
GET /api/v1/app/auth/me
```

管理端：

```text
GET /api/v1/admin/auth/me
```

规则：

- 必须携带：

```http
Authorization: Bearer <access_token>
```

- APP 返回当前客户信息。
- 管理端返回当前管理员信息。

### 3.4 刷新 Token

APP：

```text
POST /api/v1/app/auth/refresh
```

管理端：

```text
POST /api/v1/admin/auth/refresh
```

请求：

```json
{
  "refresh_token": "refresh-token"
}
```

规则：

- 校验 refresh token 是否存在。
- 校验 refresh token 未过期。
- 校验 refresh token 未被撤销。
- 返回新的 `access_token`。
- 当前 Demo 已采用 refresh token 轮换：刷新成功后旧 refresh token 会被撤销，客户端需要保存新 refresh token。

### 3.5 退出登录

APP：

```text
POST /api/v1/app/auth/logout
```

管理端：

```text
POST /api/v1/admin/auth/logout
```

规则：

- 将 refresh token 标记为撤销。
- 已签发的 access token 可等自然过期。

## 4. Token 设计

### 4.1 Access Token

用途：

- 调用受保护 API。

建议有效期：

```text
2 小时
```

开发阶段可临时设为：

```text
24 小时
```

APP token payload：

```json
{
  "sub": "user:1",
  "type": "app",
  "user_id": 1,
  "phone": "13800000000",
  "exp": 1234567890
}
```

管理端 token payload：

```json
{
  "sub": "staff:1",
  "type": "admin",
  "staff_user_id": 1,
  "username": "admin",
  "role": "admin",
  "exp": 1234567890
}
```

### 4.2 Refresh Token

用途：

- 定期刷新 access token。

建议有效期：

```text
7 天
```

开发阶段可临时设为：

```text
30 天
```

规则：

- refresh token 使用随机字符串。
- 数据库只保存 refresh token hash。
- refresh token 明文只在登录时返回一次。

## 5. 最小数据库改动

当前阶段只需要新增一张表：

```text
auth_refresh_tokens
```

新库直接执行 `001_create_tables.sql` 即可；已有库需要执行：

```text
deploy/sql/004_auth_refresh_tokens.sql
deploy/sql/005_update_demo_admin_password.sql
```

当前落地字段：

```sql
CREATE TABLE dbo.auth_refresh_tokens (
    id BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    token_hash NVARCHAR(128) NOT NULL,
    subject_type NVARCHAR(50) NOT NULL,
    user_id BIGINT NULL,
    staff_user_id BIGINT NULL,
    expires_at DATETIME2(3) NOT NULL,
    revoked_at DATETIME2(3) NULL,
    created_at DATETIME2(3) NOT NULL CONSTRAINT DF_auth_refresh_tokens_created_at DEFAULT SYSUTCDATETIME(),
    CONSTRAINT UQ_auth_refresh_tokens_token_hash UNIQUE (token_hash)
);
```

暂不需要：

- 登录日志表。
- 验证码表。
- 权限表。
- 设备表。
- access token 黑名单表。

## 6. 本阶段不做

当前登录 Demo 不做：

- 真实短信发送。
- 复杂验证码表。
- RBAC 权限系统。
- 多设备管理。
- 强制下线。
- access token 黑名单。
- 登录失败锁定。
- 登录审计日志。
- 管理员创建/编辑界面。

这些可以留到正式认证系统阶段。

## 7. 验收标准

### APP 登录

1. 使用手机号和 `123456` 登录成功。
2. 新手机号登录后，数据库 `users` 自动新增记录。
3. 登录响应包含 `access_token` 和 `refresh_token`。
4. 携带 `access_token` 调用 `/api/v1/app/auth/me` 成功。
5. 使用 `refresh_token` 调用 `/api/v1/app/auth/refresh` 成功返回新 access token。

### 管理端登录

1. 数据库存在管理员账号。
2. 正确密码登录成功。
3. 错误密码登录失败。
4. 登录响应包含 `access_token` 和 `refresh_token`。
5. 携带 `access_token` 调用 `/api/v1/admin/auth/me` 成功。
6. 使用 `refresh_token` 调用 `/api/v1/admin/auth/refresh` 成功返回新 access token。

### 受保护 API

1. 不带 token 调用业务 API 返回 `401`。
2. APP token 不能访问管理端 API。
3. 管理端 token 不能访问 APP API。
4. token 过期后不能继续访问。

## 8. 推荐实现顺序

1. 新增 `auth_refresh_tokens` 表。
2. 更新 ORM 模型。
3. 增加 refresh token 生成和 hash 工具函数。
4. 改造 APP 登录：固定验证码 + 自动创建用户。
5. 改造管理端登录：真实查库 + 密码哈希校验。
6. 新增 `/auth/me`。
7. 新增 `/auth/refresh`。
8. 新增 `/auth/logout`。
9. 调整 `require_app_user` 和 `require_admin`，确保 token 中有真实 ID。
