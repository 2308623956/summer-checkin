# Summer Checkin

学习打卡与复盘平台。每天记一笔进展，系统看着节奏：连续天数、任务完成度、该补的弱项；
一个主动巡检的 agent 每晚给出建议，**写库类动作必须经人批准才执行**。

> **当前状态：R000（双服务骨架）已完成。** 两个服务能跑、能登录、能连库，页面能打开并显示空态。
> **业务逻辑尚未实现**——打卡、计划、巡检运行时、复盘都还没有写接口，页面上会明确说明。
> 这不是缺陷，是排期（见 `docs/PRD.md` 3.0）。

## 架构

两个服务分离部署，nginx 在同一域名下按路径分流：

```
浏览器
  │
  ▼
nginx ── / 与 /api/auth/* ──▶ web   （Next.js：页面渲染 + Better Auth 登录）
  │
  └──── /api/v1/*        ──▶ service（FastAPI：业务数据与业务接口的唯一所有者）
                                  │
                                  ▼
                            PostgreSQL 16 + pgvector
```

**为什么拆开**：业务规则、数据与模型调用集中在 Python 服务里，页面只负责渲染。
web **不直连任何业务表**（唯一例外是 Better Auth 自己的认证四张表）。

**认证链路**：web 用 Better Auth 管会话，再自签一枚 15 分钟的 RS256 JWT 写进 httpOnly cookie；
service 只拿公钥验签、从 `sub` 取 `user_id`，不碰认证表。私钥只在 web，service 签不了 token。

## 目录

| 路径 | 内容 |
|---|---|
| `service/` | FastAPI 领域服务：31 张表的模型与 Alembic 迁移、统一响应与错误码、模型池 |
| `web/` | Next.js 前端：15 个页面、`lib/api.ts` 取数出口、登录与令牌签发 |
| `infra/` | 两个 Dockerfile、compose（生产/开发）、nginx 分流、建库脚本 |
| `docs/` | `PRD.md`（做什么）与 `tech/`（怎么做，**跨需求契约的唯一事实来源**） |
| `.trellis/` | 需求任务（`tasks/`）与编码规约（`spec/`） |

## 快速开始

需要 Node 22、[uv](https://docs.astral.sh/uv/)（管理 Python 3.12）与 Docker。

```bash
# 1. 起数据库（只起 db，两端在宿主机热重载）
docker compose -f infra/docker-compose.dev.yml up -d

# 2. 配置环境变量。
#    本机热重载时两个服务**都不会**读根目录的 .env——
#    service 读 service/.env，web 读 web/.env.local（Next.js 只认自己目录下的 .env*）。
#    所以要把模板拆成两份，对应关系见下方「环境变量怎么分」。
#    （根目录 .env 只在**生产 compose** 里用：infra/docker-compose.yml 的 env_file 指向它。）
cp .env.example .env            # 本机热重载用不到，但生产 compose 需要它

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

### 环境变量怎么分

`.env.example` 按注释分了两段（`service` / `web`），照段落拆即可：

| 变量 | 放哪 | 说明 |
|---|---|---|
| `SUMMER_DATABASE_URL`、`SUMMER_JWT_PUBLIC_KEY`、`SUMMER_CRON_SECRET` | `service/.env` | 前三项必填，缺了服务**拒绝启动** |
| `SUMMER_ENV`、`SUMMER_LOG_LEVEL`、限额等 | `service/.env` | 可选，缺省值见 `docs/tech/integrations.md` §5.1 |
| `DATABASE_URL`、`BETTER_AUTH_SECRET`、`BETTER_AUTH_URL` | `web/.env.local` | Better Auth 自己用；与 service 同库 |
| `SUMMER_JWT_PRIVATE_KEY` | `web/.env.local` | **只给 web**，service 只拿公钥，签不了 token |
| `SUMMER_SERVICE_URL` | `web/.env.local` | 本地 rewrite 用；线上经 nginx 不需要 |

生成一对 RS256 密钥（公钥给 service，私钥给 web）：

```bash
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out private.pem
openssl rsa -in private.pem -pubout -out public.pem
# 填进 .env 时把换行写成字面量 \n（service 侧会自动还原）
```

打开 http://localhost:3000 注册一个账号即可进入。web 通过 `next.config.ts` 的 rewrite
把 `/api/v1/*` 转发给 service，所以本地不需要 nginx。

生产形态（四容器 + nginx）见 `infra/README.md` 与 `infra/deploy.sh`。

## 校验

```bash
cd service
uv run ruff check . && uv run ruff format --check .
uv run pytest                        # 99 passed，不需要数据库

cd web
npm run check                        # typecheck + lint + vitest，20 passed
npm run build                         # 构建期问题只有它能抓到
```

迁移相关（离线，不需要连库）：

```bash
cd service
SUMMER_DATABASE_URL="postgresql+asyncpg://ci:ci@localhost:5432/summer_checkin_test" \
  uv run alembic upgrade head --sql | grep -c "CREATE TABLE"   # 32 = 31 张业务表 + alembic_version
```

## 接口现状

R000 只有这些端点（统一 `/api/v1` 前缀、统一信封），其余按需求逐个实现：

| 端点 | 说明 |
|---|---|
| `GET /healthz` | 存活与依赖状态；数据库连不上返回 `degraded` 而非 500 |
| `GET /meta` | 版本、环境与功能开关；前端据此决定入口显隐 |
| `GET /example` | **非产品接口**，用于验证"新增一个接口的 5 步"可照着执行 |
| `POST /cron/daily` | 巡检触发（占位：只排 `queued` run，不跑分析） |
| `GET /checkins` `/plans` `/runs` `/notifications` `/stats/overview` | 读接口，R000 返回空数组与零值 |

响应一律是 `{"data": ...}` / `{"data": [...], "meta": {...}}` / `{"error": {"code", "message", "requestId"}}`。
错误码与前端文案映射见 `docs/tech/architecture.md` §7 与 `docs/tech/frontend.md` §7。

## 文档

**改代码前先读 `docs/tech/`**——它是契约的唯一事实来源，冲突时优先级高于 PRD 与任务设计。

| 想知道 | 去哪 |
|---|---|
| 产品要做什么、验收标准 | `docs/PRD.md` |
| 服务边界、认证、数据所有权、硬规则 | `docs/tech/architecture.md` |
| 31 张表的字段、索引、迁移策略 | `docs/tech/data-model/` |
| 接口契约、新增接口的 5 步 | `docs/tech/api/` |
| 具体怎么写代码（分层、校验命令、常见坑） | `.trellis/spec/service/`、`.trellis/spec/web/` |

## 开发约定

- **DDL 只从 Alembic 出来**，不手改数据库；改模型必须配一条迁移（`alembic check` 会拦）。
- **`user_id` 只能来自验签后的 token**，永远不从请求参数取。
- **页面不得自己拼 `fetch`**，取数走 `web/src/lib/api.ts`。
- 破坏性迁移命令有护栏：目标库名必须以 `_test` 结尾。
- 提交信息用 `需求ID: 摘要`（如 `R001: 审批边界`）。

## 许可

[MIT](./LICENSE)。本项目的领域设计、数据模型与页面结构源自第三方 MIT 项目，
原始版权声明逐字保留在 [THIRD-PARTY-NOTICES.md](./THIRD-PARTY-NOTICES.md)。
