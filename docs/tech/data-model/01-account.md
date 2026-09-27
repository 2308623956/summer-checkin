# 01 · 账号与会话

> 4 张表：`user`、`session`、`account`、`avatarchange`。
> **归属**：由 `web/`（Next.js + Better Auth，Kysely adapter）读写，`service/` 不碰——它只从 JWT 的 `sub` 取到 `user.id`。
> 这是唯一允许 web 侧直接访问数据库的一组表（见 `../architecture.md` §3）。

## 1.1 `user`

账号主表，同时是全部业务表的 `user_id` 引用目标。

| 列 | 类型 | 默认 / 约束 | 说明 |
|---|---|---|---|
| `id` | text | PK | UUIDv7 |
| `name` | text | NOT NULL | 昵称（页面显示名） |
| `email` | text | NOT NULL, UNIQUE | 登录名 |
| `email_verified` | boolean | NOT NULL, `false` | Better Auth 维护 |
| `image` | text | NULL | 头像 URL（OSS） |
| `password` | text | NULL | 密码哈希（scrypt）；第三方登录时为空 |
| `bio` | text | NULL | 个人简介 |
| `theme` | text | NOT NULL, `'system'` | `system` / `light` / `dark` |
| `vip` | boolean | NOT NULL, `false` | 免每日 token 限额。**不是安全边界**：只影响 `usage` 的限额判断，不改变任何鉴权 |
| `created_at` | timestamptz | NOT NULL, `now()` | |
| `updated_at` | timestamptz | NOT NULL, `now()` | 应用侧更新 |

**索引**：`UNIQUE(email)`。
**关系**：1-N → 全部业务表（`ON DELETE CASCADE`）。
**本项目用法**：`vip` 在单用户自用阶段恒为 true（限额靠 `SUMMER_AI_TOKEN_LIMIT`）；`name` 用于通知与复盘文案。

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
| `created_at` | timestamptz | NOT NULL, `now()` | |
| `updated_at` | timestamptz | NOT NULL, `now()` | |

**索引**：`UNIQUE(provider_id, account_id)`。
**本项目用法**：首版只用 `credential` 一条路径；第三方登录不做（Out-of-Scope）。

## 1.4 `avatarchange`

头像变更历史，用于"回滚到上一张"。

| 列 | 类型 | 默认 / 约束 | 说明 |
|---|---|---|---|
| `id` | text | PK | |
| `user_id` | text | NOT NULL | 无外键约束（与参考实现一致，保留即可） |
| `image` | text | NULL | 当时使用的头像 URL；NULL 表示"恢复默认" |
| `created_at` | timestamptz | NOT NULL, `now()` | |

**索引**：`INDEX(user_id, created_at DESC)`。
**本项目用法**：不是核心链路，纯粹保留既有体验；头像上传的预签名 URL 由 **service** 签发（见 `../architecture.md` §2）。

---

**变更记录**

| 日期 | 变更 |
|---|---|
| 2026-09-25 | 首版（4 张表全字段） |
