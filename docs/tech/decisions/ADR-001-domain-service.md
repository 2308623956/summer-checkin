# ADR-001 后端服务化：FastAPI 领域服务 + Next BFF

- 状态：已采纳
- 日期：2026-09-25
- 相关：`../architecture.md`、`../api/`、`../data-model/`、`../../PRD.md` 1.5 / 1.8 / 3.0

## 背景

本项目基于已有的自习室平台（`summer-checkin-master/`）改造，原技术形态是 **Next.js 全栈单进程**：页面、Route Handlers、Prisma、agent 运行时都在同一个进程里。

此前有一版方案（PRD 0.2.0）主张把后端重写成独立服务，被否掉，理由是工期 4–6 周、且当时的目标是"多端互通"，性价比低。现在目标变了：

1. 要有**一个真正的后端服务**作为架构载体——面试里"两个服务怎么划分边界、怎么认证、怎么保证一致性"能讲的东西，比"Next 里分了几个目录"多得多；
2. 求职方向偏 Python / Agent 后端，与已有的 FastAPI + SQLAlchemy 生产经验（华策 aigc-transdubbing：FastAPI + SQLAlchemy + APScheduler + 向量库）连续，认知成本低、可复用的表达多；
3. 时间预算 2–3 周、允许分期，不再追求"两个客户端"。

## 决策

**两个服务、一个数据库**：

- `service/`（FastAPI + SQLAlchemy 2.0 + Alembic + APScheduler）：拥有数据库 schema 与**全部业务接口** `/api/v1/*`，承载 agent 巡检、审批、复盘（题库 / 简历）、统计、成本账本、回归面板；模型池、记忆、RAG 一并迁到 Python。
- `web/`（Next.js 16）：只做**页面渲染 + 登录认证**（Better Auth + Kysely），不再直接读业务库。
- nginx 同一域名按路径分流：`/` 与 `/api/auth/*` → web，`/api/v1/*` → service。
- 认证用 **BFF 模式**：Better Auth 留在 web，签发短期 JWT 写入同域 httpOnly cookie，service 验签取 `user_id`，不访问认证表。
- **Prisma 退场**：Alembic 是唯一的 DDL/迁移来源，包含认证四张表。

## 被否方案

**A. 保持单栈，只在 Next 内部分层（原 PRD 方案）**：工期 3 天，但拿不到"独立后端服务"这个简历点，且 agent 运行时继续和页面挤在一个进程里，讲不清楚边界。放弃原因：不满足第 1 条目标。

**B. 全量重写，认证也迁到 FastAPI（自己发 JWT + refresh）**：架构更"标准"，但注册、登录、找回密码、会话表、页面侧 cookie 同步都要重做，比 BFF 多约 1 周，而这一周不产生任何可演示的增量。放弃原因：性价比低，分期推进时它挡在最前面。

**C. Prisma 保留 schema 所有权，Python 侧用 SQLAlchemy 反射或原生 SQL**：表定义不用抄两遍，但 Python 侧类型提示弱、IDE 补全差，两边容易不同步；且"schema 归谁"这件事讲不清楚。放弃原因：单一所有权比省一遍抄写更重要。

**D. 换域重做（面试对练台 / 语音对练）**：更亮眼但工期 8–12 周，与"2–3 周进入可演示"直接冲突。已在 PRD 附录 B 记录过。

## 代价与后果

- **工期从 2 周变 2–3 周**，且第 1 周结束时产品仍不可用（只有骨架 + 一条端到端链路）。
- **要重建 30 张表的 SQLAlchemy 模型与迁移基线**：可以从现有 PostgreSQL 反向生成草稿，但必须人工整理类型、约束、索引（含 pgvector 的 `vector(1024)` 与 HNSW 索引，见参考项目 `prisma/migrate-to-pgvector.sql`）。
- **agent 运行时（参考项目 `src/lib/agent/runtime.ts` 886 行 + `model-pool.ts` 587 行）要重写成 Python**：这是最容易低估的一块，重写时必须保留"审批不越过"的边界（原实现在 `CREATE_TASK` 直接写库，是已知缺陷）。
- **新增一条硬约束**：web 侧不得直连业务库。打卡等"留在 web 的功能"指页面留在 web，数据请求仍走 `/api/v1/*`。
- **部署多一个进程**，本地开发要同时起 web / service / db 三个东西（用 `infra/docker-compose.yml` 或两个终端）。
- **两栈并行**意味着认知成本：写接口先想"这属于哪个服务"。判据写在 `../architecture.md` §2。

## 验证方式

1. 第 1 周末：浏览器打开页面，`GET /api/v1/meta` 返回统一结构，一条真实数据链路（如统计概览）从 service 到页面跑通。
2. 第 2 周末：每日巡检自动跑，审批能真的建出任务，页面读的是 `/api/v1/*`。
3. 第 3 周末：题库复盘与简历复盘闭环可用；成本账本能对上 `tokenusage` 求和。
4. 面试前：能不看文档讲清"为什么两个服务、边界在哪、认证怎么走、schema 归谁、怎么防漂移"。
