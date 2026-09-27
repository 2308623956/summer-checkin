# ADR-003 数据库命名与主键规范

- 状态：已采纳
- 日期：2026-09-25
- 相关：`../data-model/README.md`、`ADR-001-domain-service.md`

## 背景

参考实现的 schema 由 Prisma 定义：表名全小写（`plantask`），**列名是 camelCase**（`userId`、`createdAt`），主键是应用侧生成的 cuid 字符串，时间列是 Prisma 的 `DateTime`（PostgreSQL 里落在 `timestamp`）。

本项目数据库**空地新建**（无历史数据），拥有者换成 Python 侧的 SQLAlchemy + Alembic。于是有一个必须一次性定下来的问题：字段命名与类型照抄，还是借这次机会规范化？

## 决策

| 项 | 决定 |
|---|---|
| 表名 | **沿用现状**（`user`、`plantask`、`agentrun`…）：与参考实现一一对应，排查与搬运时不用做心智映射 |
| 列名 | **统一 snake_case**（`user_id`、`created_at`、`email_verified`） |
| 主键 | `id text PRIMARY KEY`，应用侧生成 **UUIDv7 字符串**（时间有序） |
| 时间列 | **`timestamptz`**，统一 UTC 存储 |
| 枚举值 | 一律 `text` + 应用层校验，不用数据库 enum 类型 |
| 向量列 | `vector(1024)`，HNSW + `vector_cosine_ops` |

## 被否方案

**A. 完全照抄 Prisma 命名（camelCase 列名）**：零适配成本，但 PostgreSQL 会把未加引号的标识符折成小写，`userId` 必须处处写成 `"userId"`——Alembic 自动生成的迁移、psql 排查、任何 raw SQL 都要记得引号，忘记引号时报错信息还很难看出原因。因为这个项目要长期手写查询与统计，这笔"引号税"要一直交。

**B. 表名也改成 snake_case / 复数**：收益只是"更顺眼"，代价是以后读参考实现、对比迁移、搬运代码时都要做一次名字映射。不划算。

**C. 主键继续用 cuid**：Python 没有与 JS 版 cuid 完全一致的官方实现，自己写一份等于给"造 id"这件事增加自定义代码；UUIDv7 标准、时间有序（相邻写入落在相邻索引页）、无需自研。

**D. 用数据库 enum 类型**：改一个取值要 `ALTER TYPE`（还可能锁表），而本项目状态取值仍在演进（`agentapproval.status` 这次就多了个 `expired`）。text + 应用层校验更灵活。

## 代价与后果

- **需要一张名称对照表**：参考实现字段名 → 本项目字段名（规则机械：`userId → user_id`），写代码时按 `../data-model/` 为准，不按 Prisma schema。
- **Better Auth 需要字段映射**：它的默认结构是 camelCase，本项目物理列是 snake_case，要在配置里声明（`user.modelName` / `fields`）。实现前先按其文档确认写法；**升级 Better Auth 时要回归登录**。
- **`user` 作为表名保留**：PostgreSQL 允许，但它是 SQL 保留字之一，若将来某处必须加引号造成麻烦，改名为 `app_user` 需同时改 Better Auth 的 `modelName`——记在这里，避免下次重新纠结。
- 时间列从 `timestamp` 变 `timestamptz`：**行为差异**是跨时区/夏令时时不会算错，代价是任何"按天分组"的查询都要显式声明时区（本项目统一按 `Asia/Shanghai` 业务日切分）。
- 应用侧生成的 id 必须在**写库前**确定（不能依赖数据库返回自增），这对幂等键构造其实有利：`{run_id}:{action}:{主键}` 里的主键是已知的。

## 验证方式

1. `alembic upgrade head` 建出的表里不存在任何需要引号才能查询的列名（`\d+ agentrun` 自查）。
2. 一条 raw SQL 统计（按日汇总时长）不加任何引号即可执行。
3. Better Auth 登录/注册在映射配置下正常工作，且 `session.expires_at` 时间比对本机时间无时区偏差。
4. 抽查 20 条新写入数据的 `id`：字符串字典序与插入顺序一致（UUIDv7 的时间有序性）。
