# R000 双服务骨架（第一优先，不含业务逻辑）

> 本任务是需求 `R000` 的落地任务。需求溯源：`docs/PRD.md` 1.6 需求表、3.0 功能详述、3.11 验收标准。
> 技术契约以 `docs/tech/` 为准（现状契约 > 本任务 `design.md` > `docs/PRD.md` 摘要）。本文件只写需求、约束与验收，技术方案见 `design.md`，执行清单见 `implement.md`。

## 1. 目标与价值

在 `summer-checkin/` 立起两条能跑的空壳：`service/`（FastAPI）提供统一结构的接口并能连库，`web/`（Next.js）能打开页面并完成登录，nginx 在同一域名下分流。业务逻辑留给 R001 之后。

价值：后续每个需求只回答"填什么"，不再重新决定"放哪个服务、放哪一层"。R000 结束时页面能打开、数据是空的——这是预期，不是缺陷。

参考工程 `summer-checkin-master/` 全程**只读**，只作为搬运来源与对照。

## 2. 已核实事实

### 2.1 环境（实测）

| 项 | 实测结果 | 影响 |
|---|---|---|
| Node / npm | v22.16.0 / 10.9.2 | web 侧可用 |
| pnpm | 11.8.0（已装，本任务不用） | 包管理器二选一，见 design D12 |
| Python | 默认 3.10.13（Miniconda）；另有 CPython 3.12.13（独立解释器，原由 uv 装，仍在） | service 用 3.12 建**普通 venv + pip**（uv / `uv.lock` 已弃用，pip 才能指定镜像源） |
| Docker | **不存在**（`docker` 命令未识别），WSL Ubuntu-20.04 处于 Stopped | compose 与 nginx 验收降级，见 §10 第 15 行 |
| 本地 PostgreSQL | 无 psql，5432/5433 均未监听 | **R000 不需要数据库连接**：迁移在本机用离线 DDL 渲染验证，真库校验在服务器上做 |
| git | 已有仓库、5 个提交、**无 remote**、无 `.github/` | CI 文件先写好，见 §10 第 16 行 |

### 2.2 参考工程（实测）

- `src/app` 下 **15 个 `page.tsx`**、**28 个 `route.ts`**；`src/components` **86 个文件**。
- **没有 `middleware.ts`，是 `src/proxy.ts`**（Next.js 16 已将 middleware 更名 proxy）。
- `src/lib/auth.ts` 使用 `prismaAdapter`，并在 `user.create.after` 调 `cloneGuideTemplates()` **写业务表**。
- 无 `src/middleware.ts`、无 JWT 插件使用痕迹。

### 2.3 文档漂移（本任务收尾时修正）

| 位置 | 现状 | 实际 |
|---|---|---|
| `docs/PRD.md` 3.0.1 | "全部 17 个页面" | 参考工程仅 15 个可搬；`/review`、`/agent/eval` 是 R004/R010 的新页面 |
| `docs/PRD.md` 3.0.1 | 交付物含"`git init`（monorepo）" | 仓库早已存在（5 个提交、Trellis 已装），只需新增工程基线提交 |
| `docs/PRD.md` 4.4 | "R000 只做 3.0.1 表里的 7 项" | 该表实际 10 行；时间盒与 roadmap D1~D7 三者不一致 |
| `docs/tech/frontend.md` §5 | 受保护路由由 `middleware.ts` 校验 | 参考实现是 `proxy.ts` |
| `docs/tech/data-model/01-account.md` | 认证 3 张表、`user.password` 存在 | Better Auth 核心 schema 为 4 张表（含 `verification`）；邮箱密码只写 `account.password` |
| `docs/tech/{README,data-model}` | 30 张表 | 补 `verification` 后为 **31 张** |
| `docs/tech/integrations.md` §7 | `pnpm install --frozen-lockfile` | 本任务定为 npm（见 design D12） |
| `docs/tech/{integrations.md §6.1, backend.md §5.3}` | "迁移不在容器启动时隐式执行" | 需按 design D6 补充 dev 自动迁移的例外 |

### 2.4 外部事实（已查证）

- Better Auth 官方 JWT 插件自带 `jwks` 表并存私钥，签发需查库（`https://better-auth.com/docs/plugins/jwt`）。
- Better Auth 在初始化与请求前做 schema 校验，缺表缺列会让认证请求失败（`https://better-auth.com/docs/concepts/database`）。
- `CREATE EXTENSION vector` 需要超级用户权限，pgvector 不是 trusted extension（`https://github.com/pgvector/pgvector/issues/904`）。
- `alembic check` 是"对比模型与实际库、有漂移即非零退出"，不是修复工具；`alembic current --check-heads` 可判定库是否在 head。
- Alembic autogenerate **不能**识别表改名与列改名（会渲染成 drop+add）；`compare_server_default` 默认关闭。

## 3. 用户与角色

| 角色 | 是谁 | R000 范围 |
|---|---|---|
| 使用者 | 你自己（PRD 已定：单人、自用为主） | 一个真实账号：注册 → 登录 → 打开页面 → 登出 |
| 运维者 | 你自己 | 在服务器上建库、跑迁移、起服务、看日志 |

多用户不是 R000 的风险，**"忘了带 `user_id` 过滤"才是**，因此用一条单测（两个 user_id 互不可见）钉死，而不做多账号手工验收。

## 4. 入口

| 入口 | 形态 | 用途 |
|---|---|---|
| 日常开发 | 本地 `web`（npm run dev）+ 本地 `service`（uvicorn --reload），`SUMMER_DATABASE_URL` 指向测试库 | 写代码与调试 |
| 验收入口 | 经 nginx 的同一域名访问（`/` 与 `/api/auth/*` → web，`/api/v1/*` → service） | PRD 3.0.1 的"编排"验收 |
| 数据库入口 | 由 `infra/db/init-databases.sh` 建两个库；本机通过 SSH 隧道或仅放行本机 IP 的 5432 连接 | 唯一可被本机访问的是测试库 |

**R000 期间不建立任何数据库连接。** `.env.example` 里 `SUMMER_DATABASE_URL` 只写占位值、不填真值；迁移的正确性用离线 DDL 渲染验证（`prd.md` §10 第 5~8 行），真库执行与 `alembic check` 在你本地填好 URL 之后进行。

## 5. 成功路径

浏览器 → 登录（Better Auth：只读写认证四张表）→ web 侧 `/api/service-token` 签发短期 JWT → 页面调 `/api/v1/*` → 五条读接口返回合法信封 + 空数组 → 页面渲染空态、无控制台报错。

页面范围 **15 个既有页面**：全部能打开；其中 `/`、`/checkin`、`/dashboard`、`/plans`、`/docs`、`/agent` 六条主路由必须走通接口取数并渲染空态。`/review`、`/agent/eval` **R000 不建**。

**已知不完整点（预期，不是缺陷）**：R000 不建任何写接口，所以 `/checkin` 的打卡表单只渲染、提交路径不可用（按钮禁用并给出说明文案，R001 接 `POST /checkins`）；`/plans/[id]`、`/docs/[id]` 等详情页在空库下没有 id 可访问，只验证 `NOT_FOUND` 空态。

## 6. 失败路径（进验收）

| # | 场景 | 期望行为 |
|---|---|---|
| 1 | 缺必需环境变量（DB URL / JWT 公钥） | 启动时明确报错并**拒绝启动**，不允许静默降级成无鉴权 |
| 2 | 数据库不可达 | `/healthz` 仍返回 200 且 `db: "down"`；`status: "degraded"` |
| 3 | 无凭据 / JWT 过期 | 401 `AUTH_REQUIRED` |
| 4 | cron secret 错误 | 403 `FORBIDDEN` |
| 5 | 后端未启动 / `/api/v1/*` 不可达 | 页面不白屏，显示可重试提示（前端错误码映射生效） |
| 6 | 迁移未跑（表不存在） | 启动只校验"能连库"，不校验表存在；表缺失按 `INTERNAL` 处理并写日志 |

## 7. 范围

### 7.1 做

1. 仓库骨架与基线提交（`web/`、`service/`、`infra/`、`.gitignore`、`.env.example`；仓库已存在，不再 `git init`）
2. `service/` 应用装配与 `app/core`（config / security / response / errors / logging / ids / pagination）
3. SQLAlchemy 模型（**31 张表**）+ Alembic 初始迁移（pgvector 扩展、`vector(1024)`、HNSW 索引）
4. 认证链路：web 签发 15 分钟 JWT，service 验签取 `user_id`
5. 三类接口：`/healthz`、`/meta`（真实现）；`POST /cron/daily`（占位：鉴权 + 找到期用户 + 写一条 `agentrun(status='queued')`）；**五条**读接口空实现（`/checkins`、`/plans`、`/runs`、`/notifications`、`/stats/overview`）
6. `web/` 搬运 15 个页面与组件 + 新增 `api.ts` / `use-api.ts` / `error-messages.ts` / `service-token` 路由，数据请求改走 `/api/v1/*`
7. 模型池**最小切片**（档位链 + 失败降级 + 记账），纯逻辑、假 client 单测，不接真实 key
8. `infra/`：两个 Dockerfile + `docker-compose.yml`（web/service/db/nginx）+ `docker-compose.dev.yml`（只起 db）+ nginx 路径分流
9. CI 三工作流文件（web-check / service-check / docker-build）
10. 一份"新增一个接口的 5 步"文档

### 7.2 不做（边界）

| 能力 | 放到哪个需求 |
|---|---|
| agent 运行时（Observe→Analyze→Plan→Execute） | R001–R003 |
| 模型池完整版（rerank、embedding 链） | R005 |
| RAG 检索链路、题库清洗 | R005 |
| 长期记忆抽取与合并 | R006–R007 |
| 通知投递与节流 | R001 |
| 统计与成本聚合 | R008–R009 |
| eval 框架与 `/agent/eval` 页面 | R010 |
| 聊天室 + WS sidecar（`server/`） | 永不搬 |
| `/review` 页面 | R004 / R006 |
| 任何业务**写**接口 | 各业务需求 |
| 服务器部署、HTTPS、域名 | R011 |
| `cloneGuideTemplates`（注册时克隆引导模板） | 待定需求：改由 service 提供接口后恢复 |

**写接口在 R000 不建路由**——空数据下前端没有可提交的东西，建了只能返回假成功或 501，两者都会在验收时说谎。

## 8. 需求条目

| ID | 需求 | 验收锚点 |
|---|---|---|
| R000-1 | 仓库骨架立起，工程基线提交就位 | §10 1 |
| R000-2 | `service/` 应用可启动、能连库、以统一信封返回 | §10 9、10 |
| R000-3 | 数据库基线可从空库一次建出 **31 张表**，且模型与库无漂移、可逆 | §10 5、6、7、8 |
| R000-4 | 认证链路打通：web 签发、service 验签取 `user_id`；跨用户数据不可见 | §10 4、11、13 |
| R000-5 | `web/` 15 个页面可打开、六条主路由走通接口取数并渲染空态 | §10 13、14 |
| R000-6 | 模型池最小切片可用（档位链 + 降级 + 记账），假 client 可单测 | §10 4 |
| R000-7 | 容器化与编排：两个 Dockerfile、两份 compose、nginx 分流 | §10 15 |
| R000-8 | CI 与工程文档就绪 | §10 16、17 |

## 9. 约束与安全边界

1. **web 不直连业务库**：`web/src` 内 `grep -r "prisma"` 必须为空；业务数据请求只经 `/api/v1/*`。
2. **schema 唯一所有者是 Alembic**：DDL 只允许出现在 `service/alembic/versions/`；不使用 `auth migrate` 等第二份 schema 来源。
3. **service 不碰认证表**：只从 JWT 的 `sub` 取 `user_id`。
4. **跨用户访问一律 `NOT_FOUND`**，不泄露存在性。
5. **JWT 只承载 `sub` + `exp`**，有效期 15 分钟；**不使用对称密钥**（避免 service 获得签发能力）。
6. **测试库护栏**：任何会破坏数据的命令（`downgrade base`、清 schema）只允许作用于库名以 `_test` 结尾的库，断言失败即退出。
7. **只有测试库可被本机访问**，生产库不暴露、R000 期间只建不连。
8. **密钥纪律**：`.env` 进 `.gitignore`，仓库只留 `.env.example`（占位值）；日志与错误响应不出现 key、正文原文。
9. **不开 CORS**：同域部署，浏览器只访问 nginx 入口；本地开发走 `next.config.ts` rewrite。
10. **`CRON_SECRET` 只保护 `POST /cron/daily`**，不是用户身份。

## 10. 验收标准

| # | 命令 / 动作 | 期望 |
|---|---|---|
| 1 | `git log --oneline` | 新增提交承载工程基线（仓库已有历史，不重新 `git init`） |
| 2 | `cd web; npm run check` | typecheck + lint + test 全绿 |
| 3 | `cd service; .venv/bin/ruff check .; .venv/bin/ruff format --check .` | 全绿 |
| 4 | `cd service; .venv/bin/pytest` | 全绿（含跨用户隔离守卫、无 `user_id` 过滤的查询守卫、模型池降级 + 记账的假 client 单测） |
| 5 | `.venv/bin/python -c "..."` 统计 `Base.metadata.tables` | 恰好 **31** 张业务表 |
| 6 | `.venv/bin/alembic upgrade head --sql`（离线渲染，不连库） | 生成的 DDL 含 `CREATE EXTENSION` + 31 张 `CREATE TABLE` + 2 条 `USING hnsw` |
| 7 | 迁移链自检单测（`downgrade` 函数存在且与 `upgrade` 对称） | 通过 |
| 8 | **待你填好 `SUMMER_DATABASE_URL` 后执行**：`alembic upgrade head` → `alembic check` → `alembic current --check-heads` → `downgrade base` → `upgrade head` | 真库建出 31 张表、无漂移、在 head、可逆 |
| 9 | `curl /api/v1/healthz` | `{"data":{"status":"ok","db":"ok",...}}` |
| 10 | `curl /api/v1/meta` | 统一信封 + `features` / `limits` |
| 11 | 无凭据 `curl /api/v1/checkins` | 401 `AUTH_REQUIRED` |
| 12 | 错误 cron secret 调 `/api/v1/cron/daily` | 403 `FORBIDDEN` |
| 13 | 浏览器完成注册与登录，访问各主路由 | 空态、无白屏、无控制台报错 |
| 14 | `grep -r "prisma" web/src`；`grep -rl 'fetch("/api/' web/src` | 前者为空；后者只命中 `lib/api.ts` 与 `lib/service-token.ts`（令牌与登出的出口） |
| 15 | **降级验收**：`docker compose up` 起四容器、经 nginx 访问 | 本机无 Docker，标记"待服务器阶段执行"，不得静默划掉 |
| 16 | **降级验收**：CI 工作流真跑 | 仓库无 remote，标记"待建远端后执行"；本地等价命令已由 3~7 行覆盖（含 CI 的迁移离线渲染断言） |
| 17 | 按"新增一个接口的 5 步"新增一个示例接口 | 已由 `GET /api/v1/example` 落地，`test_envelope.py` 两条测试守住（401 与信封 + `userId` 来自 token） |

**时间盒：3 个工作日**（PRD 4.4 的"超 3 天即停手交验"）。超时按"已完成 / 未完成 + 原因"交验，不静默延期。

## 11. 风险

| 风险 | 应对 |
|---|---|
| 本机无 Docker，compose 与 nginx 两项无法就地验收 | 第 15 行标降级验收；代码按 `integrations.md` §6 写好，部署阶段验证 |
| 本地开发依赖服务器上的测试库 | 隧道/白名单为前置；S1 的迁移工作可在库可达后补跑 |
| pgvector 需超级用户 | 服务器必须用 pgvector 官方镜像容器，迁移用容器内超级用户执行；不用托管 RDS |
| 页面搬运是大头（86 个组件） | S2/S3 先做最小垂直切片，页面分批搬 |
| 时间盒被搬运吃掉 | 按 §7.2 边界一律不碰业务；超 3 天交验 |
| 文档 31 张表与现状 30 张不一致 | 收尾统一回写 `docs/tech/`（§13） |

## 12. 阻塞性开放问题

无。所有产品与范围决策已在前置问答中定稿；技术选型见 `design.md`。

## 13. 收尾要回写的文档（Phase 3.3）

| 文件 | 改动 |
|---|---|
| `docs/PRD.md` 3.0.1 | 17 → 15 个既有页面；页面范围口径；删去 `git init`（仓库已存在） |
| `docs/PRD.md` 4.4 | "7 项" → 3.0.1 的 10 行交付物；时间盒口径统一 |
| `docs/tech/frontend.md` §5 | `middleware.ts` → `proxy.ts`；令牌传递落定 |
| `docs/tech/architecture.md` §3.1 | JWT 验签方式落定（RS256 公钥验签，非 JWKS） |
| `docs/tech/data-model/` | 认证册补 `verification`、删 `user.password`、补 `account` 官方列；30 → 31 张表（README + 分册） |
| `docs/tech/integrations.md` §5.3 / §6.1 | 迁移策略（dev 自动 + 生产显式）；§7 pnpm → npm |
| `docs/README.md` 状态表 | R000 任务状态与文档状态 |
| `.trellis/spec/web/index.md`、`.trellis/spec/service/index.md` | 新建两层 spec 索引 |

## 14. 变更记录

| 日期 | 变更 |
|---|---|
| 2026-09-27 | 首版：由 R000 前置问答（8 轮）定稿需求、边界、验收与风险 |
