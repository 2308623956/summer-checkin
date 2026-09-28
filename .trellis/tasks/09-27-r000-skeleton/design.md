# R000 技术设计

> 本文件只写本任务的**增量与选型**；跨需求契约（服务边界、目录、错误码、表结构定义、部署拓扑）一律以 `docs/tech/` 为准，此处不复制。
> 每条决定记录"选择 / 被否方案 / 代价"，供后续需求回溯。

## 1. 设计目标

用最小可运行的两条空壳，把"分层约束"变成**代码里的既成事实**：目录、模块边界、统一信封、鉴权链路、schema 所有权、迁移纪律。R000 的产物不是功能，是后续每个需求的落点。

## 2. 架构与边界

沿用 `docs/tech/architecture.md` §0/§2/§4 的分层与目录，不新增层。本任务只落实两处：

- `web/` 只保留一个 Next API 路由族：`api/auth/[...all]`（Better Auth）+ `api/service-token`（签发 service JWT）。**其余 27 个 route.ts 一律不搬**（它们的职责由 service 的 `/api/v1/*` 承担）。
- `service/` 按 `backend.md` §1 建目录；R000 只填 `core/`、`db/`、`models/`、`api/v1/system.py` + 读接口薄路由、`llm/pool.py` 最小切片。

数据流（R000 实际存在的那一条）：

```
浏览器 → nginx
  ├─ / 与 /api/auth/*  → web（Next.js）：页面 + Better Auth + /api/service-token
  └─ /api/v1/*         → service（FastAPI）：验签 → 薄路由 → 服务层（R000 返回空）
                                              ↘ PostgreSQL（31 张表，空的）
```

## 3. 关键决定

### D1 认证令牌由 web 自签，不用 Better Auth JWT 插件

- **选择**：web 侧新增 `src/app/api/service-token/route.ts`，用 `jose` 以 RS256 私钥签发 15 分钟 JWT（`sub` = `user.id`、`exp`），写入 `httpOnly` cookie `summer_service_jwt`；service 用公钥验签。
- **被否 A：Better Auth JWT 插件**。它自带一张 `jwks` 表（第 32 张）、私钥存库、签发时查库，官方定位是 OAuth/OIDC 与外部服务场景。我们用不上 JWKS 轮换，却要多一张表和一次查询。
- **被否 B：service 直接解析 Better Auth 会话 cookie**。会把"认证格式"耦合进业务服务，违背"service 不碰认证表"。
- **代价**：令牌续期逻辑要自己写（会话有效期内静默续签）；密钥轮换靠双公钥过渡（`integrations.md` §5.3 已写）。实现前按 Better Auth 的 `getSession` 服务端 API 取会话，具体调用方式在 S3 落地时确认。

### D2 密钥：RS256 + RSA 2048，本机生成

- **选择**：用本机已装的 Node 22 `crypto.generateKeyPairSync('rsa', { modulusLength: 2048 })` 生成一对 PEM，写入本地 `.env` 的 `SUMMER_JWT_PRIVATE_KEY`（web 用）/ `SUMMER_JWT_PUBLIC_KEY`（service 用）；`.env.example` 只留占位符。
- **被否：EdDSA/Ed25519**（更短更快，但工具链与运维认知度低一档）、**HS256 对称密钥**（service 一旦持有即可自签任意身份，等于把认证能力复制到第二个服务）。
- **代价**：换密钥需要同时改两个服务并重启（首版可接受）；密钥一旦泄漏必须成对更换。

### D3 认证表严格对齐 Better Auth 核心 schema（30 → 31 张表）

- **选择**：`user` / `session` / `account` / `verification` 四张表按官方核心 schema 建；`user` 保留我们的业务列（`bio`、`theme`、`vip`），**删除 `user.password`**；`account` 补齐官方列（`access_token_expires_at`、`refresh_token_expires_at`、`scope`、`id_token`）。
- **理由**：Better Auth 在初始化与请求前做 schema 校验，缺表缺列会让认证请求失败；邮箱密码的哈希只写 `account.password`，`user.password` 是参考实现的遗留列。
- **被否：`npx auth migrate` 建认证表**。它会在 Alembic 之外产生第二份 schema，直接违反"schema 唯一所有者"。
- **代价**：表数从 30 变 31，需回写 `docs/tech/data-model/` 与 `tech/README.md`；`user.modelName` / `fields` 的 snake_case 映射需要按官方文档确认一遍（ADR-003 已预判）。

### D4 迁移纪律（回答"怎么保证迁移"）

**核心不变量**：schema 只有一条迁移链，数据库只是"这条链执行到第几步"的结果。链是代码、进 git；库是随时可丢可重建的产物。

| # | 规则 | 强制点 |
|---|---|---|
| 1 | `service/app/models/` 是唯一声明处；DDL 只出现在 `alembic/versions/` | review + CI `grep` 守卫 |
| 2 | 改模型必须同时提交一条迁移 | CI 跑 `alembic check`，非零即失败 |
| 3 | dev 启动（`SUMMER_AUTO_MIGRATE=true`）先 `upgrade head` 再启动；**生产固定关闭**，部署脚本显式跑 | 配置默认值与 compose |
| 4 | 测试库上跑 `upgrade head → downgrade base → upgrade head`，证明可从零重建 | 测试夹具（**待 URL 填好后启用**） |
| 5 | 用 `alembic_version` 比对两台库是否同一 head | `alembic current --check-heads` |

- **"两个库都能同步到开发进度"= 两边跑同一条链**，不是任何自动修复魔法。
- `alembic check` 是**报告**不是**修复**：它能发现漂移，不能修复任意漂移。
- **R000 阶段不连数据库**：迁移的正确性用离线渲染验证——`alembic upgrade head --sql` 生成完整 DDL，断言其中含 `CREATE EXTENSION`、31 条 `CREATE TABLE`、2 条 `USING hnsw`；另加一条单测断言 `Base.metadata.tables` 恰好 31 张、且迁移链的 `upgrade`/`downgrade` 对称。真库执行与 `alembic check` 在第 5 条规则上等你填好 URL 后跑。
- 已知能力边界（写进"新增接口的 5 步"文档，避免踩坑）：**表改名与列改名检测不出来**（渲染成 drop+add，照执行会丢数据，必须手写 `alter_column(new_column_name=...)`）；`compare_server_default` 默认关闭；数据搬运永远手写。
- 对 pgvector 的两个已知坑：`vector(1024)` 类型与 HNSW 索引 autogenerate **认不出来**——迁移里 `CREATE EXTENSION vector`、`vector` 列、`CREATE INDEX ... USING hnsw` 三处**手写**并人工审阅。同时 HNSW 索引要在模型侧声明（`Index(..., postgresql_using="hnsw", postgresql_ops={"embedding": "vector_cosine_ops"})`），否则 `alembic check` 可能把库里的索引报成"多余"而误判漂移；S2 第一次跑 `alembic check` 时**实测确认**这一点，若反射结果无法与模型对齐，就用 `include_object` 回调把这两张 HNSW 索引排除在对比之外，并在 `env.py` 里写明原因。

### D5 数据库拓扑：test / 生产两库，只有 test 可达

- **选择**：数据库与库的创建全部交给 `infra/db/init-databases.sh`（compose 的 `db` 服务通过 `docker-entrypoint-initdb.d` 挂载执行）：建 `summer_checkin`（生产）与 `summer_checkin_test`（测试），并建 `vector` 扩展。**不需要你手敲 SQL**。
- **本机连接**：优先 **SSH 隧道**（`ssh -L 5433:127.0.0.1:5432 <host>`，本机 5433 已确认空闲），安全组仅对本机出口 IP 放行 5432 作为备选；生产库不暴露。
- **R000 不连库**：`.env.example` 的 `SUMMER_DATABASE_URL` 只放占位值；本地 `.env` 由你在容器起来后填。
- **被否**：两个库在所有环境都建（生产环境多余）、单库用事务回滚隔离（无法验证 `downgrade base`）、要求你手动建库（能脚本化就别手敲）。
- **代价**：init 脚本只在数据卷为空时执行一次——库被误删后需手动重建或删卷重来，这条写进 `infra/README`。

### D6 迁移执行策略

- **选择**：dev 自动 + 生产显式（`SUMMER_AUTO_MIGRATE` 默认 false）。自动路径下先 `upgrade head` 追平，**再跑一次 `alembic check`**，有漂移则拒绝启动并提示生成修复迁移。
- **被否**：所有环境都显式（本地每次重启都要手敲）、所有环境都自动（迁移失败会让服务起不来；将来多实例并发跑迁移）。
- **代价**：dev 启动多一次元数据对比（数秒）；需回改 `integrations.md` §6.1 与 `backend.md` §5.3 那两句"迁移不在容器启动时隐式执行"。

### D7 测试库护栏

- **选择**：任何破坏性数据库操作前断言目标库名以 `_test` 结尾，否则报错退出。断言放在 **pytest 夹具**与 **`downgrade` 前置**两处。
- **理由**：本地连的是服务器上的库，`downgrade base` 跑错库等于删库。
- **不可协商**：这条不接受"我知道我在做什么"式的绕过。

### D8 接口范围：三类，且读接口返回空信封

- 真实现：`GET /healthz`（含 `db` 探测）、`GET /meta`（版本 + feature flags + limits）。
- 占位：`POST /cron/daily`（`CRON_SECRET` 鉴权 → 找到期用户 → 写一条 `agentrun(status='queued')`，不跑分析）。
- 空实现：`GET /checkins`、`GET /plans`、`GET /runs`、`GET /notifications`、`GET /stats/overview`——返回合法信封 + 空数组，让页面渲染空态。
- **不建任何写路由**。

### D9 `env.py` 不做自动前置升级

- **选择**：`SUMMER_AUTO_MIGRATE=true` 时由**应用启动钩子**执行 `upgrade head`，而不是在 `alembic/env.py` 里挂自动前置。
- **理由**：在 `env.py` 里前置 `upgrade head` 会污染**所有** alembic 命令的语义（`downgrade`、`revision --autogenerate`、`current` 都变成"先升级再说"），让历史回退与漂移排查变得不可预期。
- **代价**：多一个启动钩子函数（十几行）。

### D10 模型池最小切片

- **选择**：`service/app/llm/pool.py` 实现档位链读取、失败降级、限流冷却、`usage` 记账；全部走注入的假 client 单测。
- **理由**：`/meta` 要暴露限额、W2 一开工就要用，且它不依赖真实 key。
- **代价**：R000 内没有真实调用方，属于"为下一需求预置的地基"；边界严格限制在"档位链 + 降级 + 记账"，不碰 rerank 与 embedding。

### D11 页面范围 15 个，`/review` 与 `/agent/eval` 不建

- **选择**：搬 15 个既有页面；六条主路由走通接口取数。
- **被否**：建两个空壳页面。理由：空壳等于替 R004/R010 预写 UI，且没有接口可对接，只会制造"看起来做完了"的假象。
- **代价**：PRD 3.0.1 的"17 个页面"要回改成 15；导航入口里指向 `/review`、`/agent/eval` 的链接在 R000 期间不显示。

### D12 包管理：web 用 npm，service 用 venv + pip

- **选择**：`web/` 用 npm + Node 22；service 用 Python 3.12 的**普通 venv + pip**，依赖写在 `requirements.txt` / `requirements-dev.txt`。
- **理由**：`web/` 不是 workspace，搬过来的 `package-lock.json` 可直接用；PRD 3.11 的验收命令就是 `npm run check`。service 侧 pip 装依赖时可以直接 `-i <镜像源>`（镜像内是 `--build-arg PIP_INDEX_URL`）。
- **改选（服务器实测）**：原来选的是 uv + `uv.lock`。实测 `uv sync --frozen` 即使在 `UV_DEFAULT_INDEX` 指向镜像源时，仍然按 lock 里记录的 `https://pypi.org/simple` / `files.pythonhosted.org` 取包——**源在 lock 生成时就钉死了**，服务器上只能走公网。改成 venv + pip 后源在安装时决定。
- **被否**：继续用 uv 但在服务器上改 `uv.lock` 里的源。理由：那是改生成物，每次重新 lock 都会被覆盖回去。
- **代价**：没有 lock 文件，只钉住直接依赖的版本号（`==`）；传递依赖由 pip 在安装时解析。
- **镜像滞后**：国内镜像比 pypi.org 慢几天（实测阿里云镜像上 sqlalchemy 只到 2.0.54、uvicorn 0.53.0、pyjwt 2.14.0、ruff 0.16.8）。所以 `requirements*.txt` 钉的是**镜像上有的版本**——钉 pypi 最新版会让服务器构建直接失败（`No matching distribution found`）。清华镜像当时有这些新版本，可以用 `-i` 换它。

### D13 单任务，不拆父/子

- **选择**：一个任务 `--meta req=R000`。
- **被否**：父任务 + service/web/infra 三个子任务。
- **理由**：R000 的验收本身是端到端的（一条链路穿 web → nginx → service → db），拆开后"半边跑通"会被当成完成。
- **代价**：任务偏大，靠 `implement.md` 的 S1~S5 分段与两个评审卡点控制。

### D14 注册钩子：去掉 `cloneGuideTemplates`

- **选择**：R000 注册只写 `user`/`session`/`account`；不搬 `user.create.after → cloneGuideTemplates()`。
- **理由**：它往 `document`/`documenttemplate` 写数据，违反"web 不碰业务表"；且 R000 所有页面都是空态，模板克隆在这套骨架里无法验证。
- **代价**：新用户冷启动路径暂时缺失，登记为待办（将来由 service 提供接口）。

### D15 不开 CORS，`/docs` 仅本地开放

- **选择**：不加 CORS 中间件（同域部署）；FastAPI 自带的 `/docs` 与 `/openapi.json` 仅在非生产环境开放。
- **理由**：减少一处配置面；生产由 nginx 屏蔽或加 Basic 认证（`api/README.md` §9 已写）。

## 4. 契约增量

本任务**不新增**跨需求契约；落地时必须与下列现有契约一致，冲突时以 `docs/tech/` 为准并当场修正：

| 契约 | 出处 | R000 落地物 |
|---|---|---|
| 统一响应与错误码 | `tech/api/README.md` §4、`tech/architecture.md` §7.1 | `core/response.py`、`core/errors.py` |
| 鉴权三种调用方 | `tech/api/README.md` §3 | `core/security.py` |
| 分页与游标 | `tech/api/README.md` §6 | `core/pagination.py`（R000 只编码/解码 + 空页） |
| 31 张表定义 | `tech/data-model/*`（含本任务 D3 的修正） | `service/app/models/*` + 初始迁移 |
| 路由表与五态 | `tech/frontend.md` §2/§3 | `web/src/app/**` |
| 环境变量清单 | `tech/integrations.md` §5 | `.env.example`、`core/config.py` |
| Compose 与 nginx | `tech/integrations.md` §6 | `infra/**` |

## 5. 兼容与迁移

- **数据库**：空地新建，无历史数据；`0001_initial` 一次建出 31 张表 + 扩展 + 索引。**不接管任何已有库**。
- **发布形态**：R000 不做服务器部署（R011）；本机无 Docker，compose 与 nginx 两项按降级验收处理。
- **回滚**：任务内回滚 = `git revert` 对应提交；测试库随时可 `downgrade base` 重建。生产库在 R000 期间不建数据，无回滚风险。

## 6. 运维与可观测

- 每个请求带 `X-Request-Id`（无则生成），响应与日志同值；nginx 透传。
- 结构化日志字段按 `backend.md` §5.2；`/healthz` 的 `db` 字段由 `SELECT 1` 得出。
- 启动自检：缺 `SUMMER_DATABASE_URL` 或 JWT 公钥 → 拒绝启动；并在启动时用一对自造的假 token 验一次，验证公钥可用。
