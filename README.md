<h1 align="center">
  <span>Summer</span>
  <span>Checkin</span>
</h1>

<p align="center">
  🌱 让每一次专注，都留下生长的痕迹
</p>

<p align="center">
  <strong>学习打卡与复盘平台</strong> · 打卡 · 计划 · AI 巡检 · 知识库 · 复盘
</p>

<p align="center">

![Next.js](https://img.shields.io/badge/Next.js-16-black?style=for-the-badge&logo=next.js&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?style=for-the-badge&logo=react&logoColor=black)
![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6?style=for-the-badge&logo=typescript&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.141-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)
![Tailwind](https://img.shields.io/badge/Tailwind%20CSS-v4-06B6D4?style=for-the-badge&logo=tailwindcss&logoColor=white)

</p>

---

## 📖 关于本项目

本项目是 **[gdut4140/summer-checkin](https://github.com/gdut4140/summer-checkin)** 的**二次开发**。

原项目是一个 AI 驱动的自习室学习平台（Next.js 全栈单体，用户 400+，
见 [在线演示](http://8.163.59.196/)），采用 Next.js API Routes + Prisma 的架构。
本项目在其**领域设计与数据模型**的基础上，把架构重写为**双服务分离部署**：

| | 原项目 | 本项目 |
|---|---|---|
| 后端 | Next.js API Routes（与页面同进程） | **FastAPI 独立服务**（`service/`） |
| 数据访问 | Prisma 直连（页面与接口都能连库） | **SQLAlchemy 2.0 + Alembic**，DDL 唯一来源 |
| 前端 | 全栈单体 | **只做页面与登录**（BFF + 短期 JWT） |
| 聊天室 | WebSocket sidecar | **不迁移**（见 `docs/tech/decisions/ADR-002`） |
| 巡检 | 建议直接写库 | **写库类动作必须人工审批**（风险分级） |

**为什么重写**：原项目的业务逻辑分散在页面组件与 API 路由里，权限与数据隔离没有统一收口。
本项目把业务规则集中到 Python 服务，接口统一信封与错误码，`user_id` 只从验签后的 token 取，
写库动作走审批链——目标是让"谁在什么权限下改了哪条数据"可追溯、可测试。

> **数据模型有继承**：31 张表中的 27 张沿用原项目的表名与字段语义
> （如 `agentapproval`、`plantask`、`plantemplate`、`usermemory`），
> 新增 `verification` 与 `evalfixture` / `evalrun` / `evalresult` 四张。
> 页面路由也沿用原项目（`/checkin`、`/plans`、`/docs`、`/agent`、`/statistics` 等）。
> 原始 MIT 版权声明见 [THIRD-PARTY-NOTICES.md](./THIRD-PARTY-NOTICES.md)。

### ⚠️ 当前进度

**R000（双服务骨架）已完成；业务功能尚未实现。**

两个服务能跑、能登录、能连库，页面能打开并显示空态。打卡、计划、巡检运行时、复盘
都还没有写接口——页面上会明确说明"还没开通"，而不是做一个点了没反应的按钮。
完整的现状与排期见 [`docs/PRD.md`](./docs/PRD.md)。

## ✨ 目标功能

> 下列是**项目的完整目标**，不是"现在就能用"。当前实现进度见上方 ⚠️。

| 功能 | 说明 | 状态 |
|---|---|---|
| 🏝️ **打卡与计划** | 每日打卡、计划拆解为任务、进度联动 | 页面已建，接口待实现 |
| 🤖 **AI 巡检** | 每晚分析学习数据给出建议，**写库类动作经人工审批才执行** | 骨架就绪（模型池切片），运行时待实现 |
| 📚 **知识库** | 资料导入、切块、向量检索（pgvector + HNSW） | 表与索引已建，接口待实现 |
| 📝 **复盘** | 题库复盘、简历复盘、弱项档案与曲线 | 表已建，接口待实现 |
| 📊 **统计** | 学习时长、连续天数、成本与延迟归因 | 读接口就绪（返回空态） |
| 🧪 **回归门禁** | 真实 trace 固化为 fixture，prompt 变更后重放对比 | 表已建，待实现 |
| 💬 实时聊天室 | WebSocket 群聊 | **明确不做**（ADR-002） |

## 🛠 技术栈

| 层 | 技术 |
|---|---|
| 前端 | Next.js 16（App Router）、React 19、TypeScript、Tailwind CSS v4 |
| 前端认证 | Better Auth（Kysely adapter，只管认证四张表） |
| 后端 | FastAPI、Python 3.12、SQLAlchemy 2.0（async）、Alembic、Pydantic v2 |
| 数据库 | PostgreSQL 16 + pgvector（`vector(1024)` 列 + HNSW 索引，检索在库内完成） |
| AI | 模型池多档位（HIGH / LOW 链），失败降级 + 限流冷却 + token 记账 |
| 部署 | Docker Compose（web / service / db / nginx 四容器）+ nginx 路径分流 |
| 质量 | ruff、pytest、ESLint、tsc、vitest、GitHub Actions |

## 🏗 架构概览

```
浏览器
  │
  ▼
nginx（反向代理，路径分流）
  ├─ / 与 /api/auth/*  ──► web（Next.js :3000）       页面渲染 + Better Auth 登录
  └─ /api/v1/*         ──► service（FastAPI :8000）  业务数据与接口的唯一所有者
                                │
                                └─ SQLAlchemy ──► PostgreSQL 16 + pgvector
```

**认证链路**：

```
登录 ─► Better Auth 写会话 cookie
     ─► web 用私钥签 15 分钟 RS256 JWT，写 httpOnly cookie
     ─► service 用公钥验签，从 sub 取 user_id（不访问认证表）
```

- **私钥只在 web**：service 拿不到私钥，签不出 token，无法伪造身份。
- **不用 JWKS**：只有一个签发方，静态公钥少一个网络依赖与故障点（见 `docs/tech/architecture.md` §3.1）。
- **web 不直连业务表**：唯一的数据库访问是 Better Auth 的认证四张表。

## 🚀 快速开始

### 环境要求

| 依赖 | 版本 |
|---|---|
| Node.js | 22+ |
| Python | 3.12（由 [uv](https://docs.astral.sh/uv/) 管理，无需手动安装） |
| PostgreSQL | 16 + pgvector（必须用 `pgvector/pgvector:pg16` 镜像，`vector(1024)` 与 HNSW 均来自该扩展）|
| Docker | 用于起数据库（也可自备 PostgreSQL 16） |

### 本地开发

```bash
# 1. 起数据库（只起 db，两端在宿主机热重载）
docker compose -f infra/docker-compose.dev.yml up -d

# 2. 配置环境变量
#    注意：本机热重载时两个服务都不读根目录的 .env——
#    service 读 service/.env，web 读 web/.env.local（Next.js 只认自己目录下的 .env*）。
#    根目录 .env 只给生产 compose 用（infra/docker-compose.yml 的 env_file 指向它）。
cp .env.example .env          # 留作模板，按下方「环境变量」拆成两份

# 3. service
cd service
uv sync
uv run alembic upgrade head          # 建 31 张表
uv run uvicorn app.main:app --reload # http://127.0.0.1:8000

# 4. web（另开一个终端）
cd web
npm ci
npm run dev                          # http://localhost:3000
```

打开 http://localhost:3000 注册账号即可进入。本地不需要 nginx：
web 通过 `next.config.ts` 的 rewrite 把 `/api/v1/*` 转发给 service。

### 环境变量

按服务拆成两份（`service/.env` 与 `web/.env.local`）：

| 变量 | 放哪 | 说明 |
|---|---|---|
| `SUMMER_DATABASE_URL` | service | **必填**，必须 `postgresql+asyncpg://` 前缀；本地库名以 `_test` 结尾 |
| `SUMMER_JWT_PUBLIC_KEY` | service | **必填**，RS256 公钥 PEM（换行写成字面量 `\n`） |
| `SUMMER_CRON_SECRET` | service | **必填**，`openssl rand -hex 32` |
| `SUMMER_AUTO_MIGRATE` | service | 开发 `true`（启动自动迁移并校验漂移），**生产必须 false** |
| `DATABASE_URL` | web | Better Auth 用（与 service 同库，各管各的表） |
| `BETTER_AUTH_SECRET` | web | 会话签名，`openssl rand -base64 32` |
| `BETTER_AUTH_URL` | web | 认证回调地址 |
| `SUMMER_JWT_PRIVATE_KEY` | web | **只给 web**，与 service 的公钥配对 |
| `SUMMER_SERVICE_URL` | web | 仅本地 rewrite 用，线上走 nginx |

生成一对 RS256 密钥：

```bash
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out private.pem
openssl rsa -in private.pem -pubout -out public.pem
```

完整清单与缺省值见 [`docs/tech/integrations.md`](./docs/tech/integrations.md) §5.1。

### 测试

```bash
# service：不需要数据库
cd service
uv run ruff check . && uv run ruff format --check .
uv run pytest                        # 99 passed

# web
cd web
npm run check                        # typecheck + lint + vitest，20 passed
npm run build                        # 构建期问题只有它能抓到
```

迁移校验（离线，不连库）：

```bash
cd service
SUMMER_DATABASE_URL="postgresql+asyncpg://ci:ci@localhost:5432/summer_checkin_test" \
  uv run alembic upgrade head --sql | grep -c "CREATE TABLE"   # 32 = 31 张业务表 + alembic_version
```

## 📁 项目结构

```
├── service/                     # FastAPI 领域服务
│   ├── app/
│   │   ├── core/                # 配置、鉴权、统一响应与错误码、日志、分页
│   │   ├── db/                  # 声明基类、async 会话、测试库护栏
│   │   ├── models/              # 31 张表的 SQLAlchemy 模型（schema 唯一声明处）
│   │   ├── schemas/             # 对外 JSON 的 Pydantic 模型
│   │   ├── api/v1/              # 薄路由：解析 → 鉴权 → 调服务层 → 包装信封
│   │   └── llm/                 # 模型池（档位链 / 降级 / 限流冷却 / 记账）
│   ├── alembic/                 # 唯一的迁移链——DDL 只允许出现在这里
│   └── tests/                   # pytest（不需要数据库）
├── web/                         # Next.js 前端
│   └── src/
│       ├── app/                 # 15 个页面 + 认证路由 + service-token 签发
│       ├── components/          # 状态组件与统一取数渲染器
│       ├── lib/                 # api.ts（取数唯一出口）、错误码映射、Better Auth
│       └── proxy.ts             # 受保护路由守卫（Next 16 由 middleware 改名）
├── infra/                       # Dockerfile、compose、nginx、建库脚本
├── docs/                        # PRD 与 tech/（跨需求契约的唯一事实来源）
└── .trellis/                    # 需求任务与编码规约
```

## 🗄 数据模型

31 张表，按模块分组（**27 张沿用原项目** + 4 张新增）：

| 模块 | 表 |
|---|---|
| 用户与认证 | `user` · `session` · `account` · `verification` ★ · `avatarchange` |
| 学习核心 | `plan` · `plantask` · `todo` · `checkin` · `studyrecord` · `plantemplate` |
| AI 智能体 | `agentrun` · `agentstep` · `agentapproval` · `agentdecision` · `agenttoolcall` · `agentschedule` · `usermemory` · `aihistory` · `notification` |
| 知识库 / 文档 | `document` · `documentchunk` · `knowledgedoc` · `documenttemplate` |
| 复盘 | `conversation` · `conversationmessage` · `chatmessage` |
| 成本与回归 | `tokenusage` · `evalfixture` ★ · `evalrun` ★ · `evalresult` ★ |

★ = 本项目新增。字段级定义见 [`docs/tech/data-model/`](./docs/tech/data-model/)（**以那里为准**）。

**列名统一 snake_case**（原项目为 camelCase）：数据库是空地新建，没有历史包袱，
省掉 PostgreSQL 大小写引号。Better Auth 侧通过字段映射对齐。

## 🐳 部署（Docker）

```bash
cp .env.example .env            # 生产 compose 读根目录 .env
bash infra/deploy.sh            # 构建镜像 → 等 db 就绪 → 显式跑迁移 → 起全部服务
```

| 文件 | 用途 |
|---|---|
| `infra/docker-compose.yml` | 四容器：db / service / web / nginx |
| `infra/docker-compose.dev.yml` | 只起 db，两端本地热重载 |
| `infra/nginx/default.conf` | 路径分流 + `X-Request-Id` 透传 + SSE 不缓冲 |
| `infra/deploy.sh` | **显式**跑迁移（不在容器启动时隐式执行） |

**为什么迁移不在容器启动时跑**：多实例同时启动会并发迁移，且迁移失败会让容器起不来，
排查时只看到"服务启动失败"。详见 [`infra/README.md`](./infra/README.md)。

## 🧭 开发约定

- **DDL 只从 Alembic 出来**，不手改数据库；改模型必须配一条迁移（CI 的 `alembic check` 会拦）。
- **`user_id` 只能来自验签后的 token**，永远不从请求参数取；跨用户访问一律 `NOT_FOUND`。
- **页面不得自己拼 `fetch`**，取数走 `web/src/lib/api.ts`。
- **破坏性迁移命令有护栏**：目标库名必须以 `_test` 结尾，否则拒绝执行。
- **接口只加不改**：破坏性变更走 `/api/v2`。
- 提交信息用 `需求ID: 摘要`（如 `R001: 审批边界`）。

## 📚 文档

**改代码前先读 [`docs/tech/`](./docs/tech/)**——它是契约的唯一事实来源，
冲突时优先级高于 PRD 与任务设计。

| 想知道 | 去哪 |
|---|---|
| 产品要做什么、验收标准、排期 | [`docs/PRD.md`](./docs/PRD.md) |
| 服务边界、认证、数据所有权、硬规则 | [`docs/tech/architecture.md`](./docs/tech/architecture.md) |
| 31 张表的字段、索引、迁移策略 | [`docs/tech/data-model/`](./docs/tech/data-model/) |
| 接口契约、**新增一个接口的 5 步** | [`docs/tech/api/`](./docs/tech/api/) |
| 具体怎么写代码（分层、校验命令、常见坑） | [`.trellis/spec/service/`](./.trellis/spec/service/index.md) · [`.trellis/spec/web/`](./.trellis/spec/web/index.md) |

## ❓ 常见问题

**为什么打卡按钮点了没反应？**
R000 只搭了骨架，写接口还没实现。页面上的表单是**禁用**状态并写明了原因——
不做"点了静默失败"的假按钮。

**为什么有两个 `.env`，不能合成一个？**
可以放一起，但两个服务**都读不到根目录**：service 的 `env_file` 是相对工作目录的，
Next.js 只加载自己目录下的 `.env*`（实测 `loadEnvConfig` 不会向上找）。
根目录那个只给生产 compose 用。

**`alembic check` 报漂移，但我没改过模型？**
大概率是表达式索引（如 `desc("created_at")`）——它反射不回模型。改用普通 btree，
PostgreSQL 反向扫描同样快。

**忘记密码了怎么办？**
R000 还没做自助重置流程（需要邮件服务）。当前可直连数据库改 `account.password`，
或删掉重建账号。

**能不能只跑 web，不起 service？**
不行。web 不含任何业务逻辑，`/api/v1/*` 全部由 service 提供。

## 🗺 路线图

- [x] **R000** 双服务骨架（本仓库当前进度）
- [ ] R001–R003 审批边界 · 幂等 · 每日建议（含依据与规则降级）
- [ ] R004–R007 题库复盘 · 题库导入与清洗 · 简历复盘 · 弱项档案
- [ ] R008–R010 统计面板 · 成本账本 · 回归门禁
- [ ] R011 部署上线（HTTPS + 域名）
- [ ] R012 演示材料

## 🙏 致谢

- 原项目：[**gdut4140/summer-checkin**](https://github.com/gdut4140/summer-checkin)（MIT）——本项目的领域设计与数据模型源自该项目
- [Next.js](https://nextjs.org) · [React](https://react.dev) · [Tailwind CSS](https://tailwindcss.com)
- [FastAPI](https://fastapi.tiangolo.com) · [SQLAlchemy](https://www.sqlalchemy.org) · [Alembic](https://alembic.sqlalchemy.org)
- [PostgreSQL](https://www.postgresql.org) · [pgvector](https://github.com/pgvector/pgvector)
- [Better Auth](https://better-auth.com) · [uv](https://docs.astral.sh/uv/)

## 📄 License

[MIT](./LICENSE)

本项目是 [gdut4140/summer-checkin](https://github.com/gdut4140/summer-checkin) 的二次开发，
原项目版权归其作者所有。按 MIT 要求，原始版权声明逐字保留在
[THIRD-PARTY-NOTICES.md](./THIRD-PARTY-NOTICES.md)。
