# 01 · 账号与会话

> 5 张表：`user`、`session`、`account`、`verification`、`avatarchange`。
> **归属**：由 `web/`（Next.js + Better Auth，Kysely adapter）读写，`service/` 不碰——它只从 JWT 的 `sub` 取到 `user.id`。
> 这是唯一允许 web 侧直接访问数据库的一组表（见 `../architecture.md` §3）。
>
> 这 4 张 Better Auth 表（`verification` 除外的是核心表）**DDL 由 Alembic 拥有**，
> 不用 `better-auth migrate`——两个 DDL 来源必然漂移（见任务 `design.md` D3）。

## 1.1 `user`

账号主表，同时是全部业务表的 `user_id` 引用目标。

| 列 | 类型 | 默认 / 约束 | 说明 |
|---|---|---|---|
| `id` | text | PK | UUIDv7 |
| `name` | text | NOT NULL | 昵称（页面显示名） |
| `email` | text | NOT NULL, UNIQUE | 登录名 |
| `email_verified` | boolean | NOT NULL, `false` | Better Auth 维护 |
| `image` | text | NULL | 头像 URL（OSS） |
| `bio` | text | NULL | 个人简介 |
| `theme` | text | NOT NULL, `'system'` | `system` / `light` / `dark` |
| `vip` | boolean | NOT NULL, `false` | 免每日 token 限额。**不是安全边界**：只影响 `usage` 的限额判断，不改变任何鉴权 |
| `created_at` | timestamptz | NOT NULL, `now()` | |
| `updated_at` | timestamptz | NOT NULL, `now()` | 应用侧更新 |

**索引**：`UNIQUE(email)`。
**关系**：1-N → 全部业务表（`ON DELETE CASCADE`）。
**本项目用法**：`vip` 在单用户自用阶段恒为 true（限额靠 `SUMMER_AI_TOKEN_LIMIT`）；`name` 用于通知与复盘文案。

> **没有 `password` 列**：Better Auth 把凭据放在 `account.password` 上，`user` 表不存密码。
> 参考实现的 `user.password` 是自研认证的遗留，迁移时删除（见任务 `design.md` D3）。

## 1.2 `session`

Better Auth 的会话表。

| 列 | 类型 | 默认 / 约束 | 说明 |
|---|---|---|---|
| `id` | text | PK | |
| `user_id` | text | NOT NULL → `user.id` CASCADE | |
| `token` | text | NOT NULL, UNIQUE | 会话令牌（httpOnly cookie 里的值） |
| `expires_at` | timestamptz | NOT NULL | 会话过期时间 |
| `ip_address` | text | NULL | |
| `user_agent` | text | NULL | |
| `created_at` | timestamptz | NOT NULL, `now()` | |
| `updated_at` | timestamptz | NOT NULL, `now()` | |

**索引**：`UNIQUE(token)`；建议 `INDEX(user_id)`（登出全部设备时用）。
**本项目用法**：web 侧用它维持登录；service 侧完全不知道它的存在——service 只验 JWT 签名。

## 1.3 `account`

第三方/凭据登录方式（Better Auth 标准结构）。

| 列 | 类型 | 默认 / 约束 | 说明 |
|---|---|---|---|
| `id` | text | PK | |
| `user_id` | text | NOT NULL → `user.id` CASCADE | |
| `provider_id` | text | NOT NULL | 通常为 `credential`（邮箱密码） |
| `account_id` | text | NOT NULL | 提供方侧的用户标识 |
| `provider` | text | NOT NULL, `'credential'` | |
| `password` | text | NULL | 该 provider 下的密码哈希 |
| `access_token` | text | NULL | 预留（第三方登录） |
| `refresh_token` | text | NULL | 预留 |
| `access_token_expires_at` | timestamptz | NULL | 预留 |
| `refresh_token_expires_at` | timestamptz | NULL | 预留 |
| `scope` | text | NULL | 预留 |
| `id_token` | text | NULL | 预留 |
| `created_at` | timestamptz | NOT NULL, `now()` | |
| `updated_at` | timestamptz | NOT NULL, `now()` | |

**索引**：`UNIQUE(provider_id, account_id)`。
**本项目用法**：首版只用 `credential` 一条路径；第三方登录不做（Out-of-Scope）。
`access_token_expires_at` / `refresh_token_expires_at` / `scope` / `id_token` 四列现在都用不到，
但**必须留在建表语句里**：Better Auth 的 adapter 按 schema 拼 SQL，缺列会在第三方登录启用时报错，
而不是在首版就暴露出来。

## 1.4 `verification`

Better Auth 核心 schema 的第四张表：验证请求（邮箱验证、重置密码等）。

| 列 | 类型 | 默认 / 约束 | 说明 |
|---|---|---|---|
| `id` | text | PK | |
| `identifier` | text | NOT NULL | 验证目标（通常是邮箱） |
| `value` | text | NOT NULL | 验证令牌/码 |
| `expires_at` | timestamptz | NOT NULL | |
| `created_at` | timestamptz | NOT NULL, `now()` | |
| `updated_at` | timestamptz | NOT NULL, `now()` | |

**为什么现在就建**：它属于 Better Auth 的核心 schema。缺表时"忘记密码"这类路径会在运行时报错——
而那时你正在排查登录问题，多一张空表的成本远低于那种处境。

## 1.5 `avatarchange`

头像变更历史，用于"回滚到上一张"。

| 列 | 类型 | 默认 / 约束 | 说明 |
|---|---|---|---|
| `id` | text | PK | |
| `user_id` | text | NOT NULL | 无外键约束（与参考实现一致，保留即可） |
| `image` | text | NULL | 当时使用的头像 URL；NULL 表示"恢复默认" |
| `created_at` | timestamptz | NOT NULL, `now()` | |

**索引**：`INDEX(user_id, created_at)`。实际建成**升序**复合索引，而不是 `DESC`：
Postgres 的 btree 反向扫描同样快，而 `DESC` 表达式索引反射不回模型、会被 `alembic check` 误报成漂移。
**本项目用法**：不是核心链路，纯粹保留既有体验；头像上传的预签名 URL 由 **service** 签发（见 `../architecture.md` §2）。

---

**变更记录**

| 日期 | 变更 |
|---|---|
| 2026-09-25 | 首版（4 张表全字段） |
| 2026-09-27 | R000 落地：补 `verification`（→ 5 张表）、删 `user.password`、补 `account` 四个官方列 |
