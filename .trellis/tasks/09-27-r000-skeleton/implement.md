# R000 执行清单

> 排序原则：**先打通一条最小垂直切片，再补全其余**。3 天时间盒下这是唯一安全的推进方式。
> 每个 S 结束后跑该段校验命令；S2 与 S3 各设一个评审卡点，未过不进下一段。

## S0 前置（容器与库；R000 期间不建立连接）

| # | 动作 | 完成标志 |
|---|---|---|
| 0.1 | 写 `infra/db/init-databases.sh`：建 `summer_checkin`（生产）与 `summer_checkin_test`（测试），并在两个库里建 `vector` 扩展 | 脚本由 `infra/docker-compose.yml` 的 `db` 服务挂到 `docker-entrypoint-initdb.d` |
| 0.2 | 服务器（你执行）：起 db 容器 → 脚本自动建两个库 | `\l` 能看到两个库；`\dx` 能看到 `vector` |
| 0.3 | 你在容器起来后把连接串填进本地 `.env`（`.env.example` 只留占位，不填真值） | `SUMMER_DATABASE_URL` 指向 `..._test` |
> R000 的迁移开发**不依赖 0.2/0.3**：迁移用离线 DDL 渲染验证（见 S2）。0.2/0.3 完成后才跑真库那一组验收（`prd.md` §10 第 8 行）。
> init 脚本只在数据卷为空时执行一次；库被删掉后要重建，见 `infra/README`。

## S1 仓库骨架与基线提交

- [ ] 建 `web/`、`service/`、`infra/` 目录与根 `.gitignore`（`.env`、`node_modules`、`.next`、`__pycache__`、`.venv`、`*.pem`）
- [ ] 根 `.env.example`（web + service 两段，占位值）
- [ ] 用 Node 22 生成 RS256 密钥对，写入本地 `.env`（`design.md` D2 的命令）
- [ ] `git add` 并提交基线：`chore: r000 baseline`（文档 + 目录 + 忽略规则）
- 校验：`git log --oneline` 首个提交为基线；`git status` 无未跟踪的密钥文件

## S2a 数据库基线（本段不连库）

- [ ] `service/pyproject.toml`：Python 3.12（uv 安装）、SQLAlchemy 2.0 / Alembic / pgvector / pydantic-settings / pytest / ruff（FastAPI 等 Web 依赖在 S2b 一并加）
- [ ] `app/db/base.py`：`DeclarativeBase` + 命名约定（`naming_convention`，让约束有名字）
- [ ] `app/models/`：31 张表按域分文件——`account.py`(4)、`study.py`(6)、`knowledge.py`(4)、`agent.py`(9)、`conversation.py`(3)、`usage_eval.py`(4)、外加 `user` 已在 account（合计 31）
- [ ] pgvector：`Vector(1024)`（`documentchunk.embedding` 非空、`usermemory.embedding` 可空）；HNSW 索引在模型侧声明（`postgresql_using="hnsw"`、`postgresql_ops={"embedding": "vector_cosine_ops"}`）
- [ ] `alembic.ini` + `alembic/env.py`（`target_metadata` 指向模型、`compare_type` 默认开、URL 从 `SUMMER_DATABASE_URL` 取，**支持 `--sql` 离线模式**）
- [ ] `alembic/versions/0001_initial.py`：手写 `CREATE EXTENSION IF NOT EXISTS vector` → 建 31 张表 → HNSW 索引；`downgrade()` 与 `upgrade()` 对称
- [ ] `tests/test_schema.py`：断言 `Base.metadata.tables` 恰好 31 张、表名集合与 `docs/tech/data-model/` 一致、两张 HNSW 索引存在、迁移链 head 唯一且 `down_revision` 连续
- [ ] `infra/db/init-databases.sh`：建 `summer_checkin` + `summer_checkin_test` + 两个库的 `vector` 扩展（0.1）
- 校验（`prd.md` §10）：
  ```
  uv run ruff check . && uv run ruff format --check .        # §10-3
  uv run pytest                                              # §10-4、§10-7
  uv run alembic upgrade head --sql | grep -c "CREATE TABLE"  # §10-6 期望 31
  uv run alembic upgrade head --sql | grep -c "USING hnsw"    # §10-6 期望 2
  ```
- **评审卡点 1（基线）**：31 张表建出、离线 DDL 完整、测试全绿。
- **真库验收（等你填好 `.env` 后执行）**：`alembic upgrade head` → `alembic check` → `current --check-heads` → `downgrade base` → `upgrade head`（`prd.md` §10 第 8 行）；届时实测 HNSW 是否被 `alembic check` 误报为漂移，误报则用 `include_object` 排除并注明原因。

## S2b service 应用骨架与接口

- [ ] 补齐 Web 依赖：FastAPI / uvicorn / asyncpg / structlog / httpx / pytest-asyncio / pyjwt（或 jose）
- [ ] `app/core/`：`config.py`（`SUMMER_` 前缀）、`errors.py`（`AppError` 全家族 + 异常处理器）、`response.py`（`ok` / `list_ok`）、`ids.py`（`uuid7`）、`pagination.py`、`logging.py`（`X-Request-Id` 中间件）
- [ ] `app/db/session.py`：async engine、`get_session` 依赖（事务边界）
- [ ] `app/core/security.py`：RS256 公钥验签、`require_user`、`require_cron_secret`；启动时用假 token 自检公钥
- [ ] `app/main.py`：应用装配 + 启动自检（缺 env 拒绝启动）+ `SUMMER_AUTO_MIGRATE=true` 时执行 `upgrade head` 再 `alembic check`
- [ ] `app/api/v1/system.py`：`/healthz`、`/meta`；`/cron/daily` 占位
- [ ] 五条读接口空实现（`/checkins`、`/plans`、`/runs`、`/notifications`、`/stats/overview`）
- [ ] `tests/`：统一信封、错误码映射、鉴权（无凭据 401 / 错误 secret 403）、`db: down` 分支、跨用户隔离守卫、无 `user_id` 过滤的查询守卫、测试库名护栏
- 校验：`uv run pytest`；起服务后
  ```
  curl :8000/api/v1/healthz                                  # §10-9
  curl :8000/api/v1/meta                                     # §10-10
  curl -i :8000/api/v1/checkins                              # §10-11 期望 401
  curl -i -H "Authorization: Bearer wrong" :8000/api/v1/cron/daily   # §10-12 期望 403
  ```
- **评审卡点 1（骨架）**：`/meta` 返回统一信封、错误码与鉴权分支全绿。未过不进 S3。

## S3 web 骨架 + 登录链路（最小切片优先）

- [ ] `web/` 从 master 搬 `package.json`（去掉 Prisma / ai-sdk / ali-oss / ws / proxy-agent，见 `frontend.md` §8）、`tsconfig.json`、`next.config.ts`（`/api/v1/:path*` rewrite）、`eslint.config.mjs`、Tailwind 配置、`components.json`
- [ ] 搬 `src/components/**`（86 个文件；`chatroom/` 不搬）、`src/config`、`src/context`、`src/styles`、`src/types`
- [ ] 改造 `src/lib/auth.ts`：Kysely adapter 连认证四表 + snake_case 字段映射；**删除** `user.create.after → cloneGuideTemplates`（`design.md` D14）
- [ ] 新增 `src/lib/api.ts`（`apiFetch` / `apiFetchPage` / `ApiError` / `streamSSE`）、`use-api.ts`、`error-messages.ts`
- [ ] 新增 `src/app/api/service-token/route.ts`（`jose` + RS256 签发 15 分钟 JWT 到 `summer_service_jwt` cookie）
- [ ] `src/proxy.ts`：受保护路由校验会话 cookie，缺失跳 `/login?returnTo=...`（沿用参考实现的 `proxy.ts` 形态）
- [ ] 搬 15 个页面 + `layout.tsx`：`/`、`/login`、`/register`、`/checkin`、`/dashboard`、`/plans`(+new/[id]/studio)、`/docs`(+[id]/knowledge/[sourceName])、`/agent`、`/profile`、`/statistics`
- [ ] 先打通：登录 → `/meta` → `/dashboard` 空态（其余页面在 S4 补）
- 校验：`cd web; npm run check`；浏览器完成注册与登录，`/dashboard` 渲染空态

## S4 其余页面接接口 + 空态

- [ ] 逐页把数据请求从"直连 Prisma"改为 `apiFetch('/api/v1/...')`（按 `frontend.md` §10 销项表逐页勾选）
- [ ] 六条主路由的空态与失败态（空态必须给"下一步动作"，不是"暂无数据"）
- [ ] `/checkin` 打卡表单：R000 无写接口，提交按钮禁用并给说明文案（不伪造成功）
- [ ] 顶部导航去掉聊天室入口与 `/review`、`/agent/eval` 链接
- [ ] 完成判据：`grep -r "prisma" web/src` 为空；`grep -rl 'fetch("/api/' web/src` 只命中 `lib/api.ts` 与 SSE 封装
- **评审卡点 2**：六条主路由走通接口取数、无控制台报错。未过不进 S5。

## S5 编排、容器与 CI

- [ ] `infra/web.Dockerfile`（多阶段、`node:22-alpine`、standalone、非 root）、`infra/service.Dockerfile`（`python:3.12-slim` + `uv sync --frozen`、非 root、单 worker）
- [ ] `infra/docker-compose.yml`（web / service / db / nginx；db 卷；健康检查顺序；迁移不隐式跑）、`infra/docker-compose.dev.yml`（只起 db）
- [ ] `infra/nginx/*.conf`：`/` 与 `/api/auth/*` → web，`/api/v1/*` → service，`X-Request-Id` 透传
- [ ] 模型池最小切片：`app/llm/pool.py`（档位链、失败降级、限流冷却）+ `usage.py` 记账 + 假 client 单测
- [ ] `.github/workflows/ci.yml` 三工作流（web-check / service-check / docker-build）
- [ ] `docs/tech/` 下"新增一个接口的 5 步"补充本项目的坑（改名检测、server default、pgvector 手写、迁移纪律）
- [ ] 按该文档新增一个示例接口，验证文档可执行
- 校验（`prd.md` §10）：本机无 Docker → 第 15 行标降级验收；CI 无 remote → 第 16 行标降级验收；第 17 行按文档新增示例接口并跑通

## 收尾（Trellis Phase 3.3 / 3.4）

- [ ] 回写 `prd.md` §13 列出的 8 处文档
- [ ] 新建 `.trellis/spec/web/index.md`、`.trellis/spec/service/index.md`
- [ ] `docs/tech/` 与代码一致性复查（契约优先）
- [ ] 提交：按需求 ID 分段提交（`feat(service): ...` / `feat(web): ...` / `chore(infra): ...`）

## 回滚点

| 步骤 | 回滚方式 |
|---|---|
| 任一 S 未过验收 | `git revert` 该段提交；测试库可 `downgrade base` 重建 |
| 迁移出错 | 测试库直接 `downgrade base`；生产库 R000 期间无数据，重建即可 |
| web 搬运引入失败 | 页面按目录粒度回退（搬运是尽力而为，不阻塞 skeleton 验收） |

## 风险与前置提醒

1. **S0 未就绪时不要假装 S2 完成**——第 5~8 条验收必须真跑。
2. **pgvector 必须超级用户**：服务器不用托管 RDS，用官方镜像容器。
3. **破坏性命令前护栏必须先生效**（D7），顺序不能颠倒。
4. 本机无 Docker：第 15 行验收留到服务器/部署阶段，不静默划掉。
