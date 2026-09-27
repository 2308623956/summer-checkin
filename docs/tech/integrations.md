# 外部依赖与部署（integrations）

> 这份文档管"边界之外"的一切：模型与向量服务、对象存储、数据库与容器、环境变量、流水线、上线与回滚。
> 业务规则不在这里（见 `backend.md` / `api/`）；模型清单来自参考实现实测（`src/lib/model-pool.ts` 587 行、`src/lib/oss.ts`、`prisma/migrate-to-pgvector.sql`）。

## 1. 外部依赖总览

| 依赖 | 用途 | 凭据 | 不可用时的行为 |
|---|---|---|---|
| Agnes AI（OpenAI 兼容） | HIGH / LOW 档首选模型（免费） | `SUMMER_AGNES_API_KEY` + `BASE_URL` | 换阿里云端点；全挂走规则兜底 |
| 阿里云百炼（compatible-mode） | 模型降级链 | `SUMMER_ALIYUN_API_KEY` | 403 配额 → 换下一个模型；全挂 → 规则兜底 |
| 阿里云百炼（rerank 原生端点） | 检索精排 | 同上百炼 key | 跳过精排，用向量序 |
| 阿里云百炼（embedding） | 向量化（1024 维） | `SUMMER_EMBEDDING_API_KEY` | 检索回落关键词；导入整体失败 |
| 阿里云 OSS | 头像 / 壁纸 / 打卡截图直传 | `SUMMER_OSS_*` | 上传报 `UPSTREAM_FAILED`，打卡可先不传图 |
| PostgreSQL 16 + pgvector 0.8.6 | 唯一数据库 | `SUMMER_DATABASE_URL` | 服务不可用（`/healthz` 报 `degraded`） |
| nginx | 同域分流 | 无 | 整站不可用（单入口） |

## 2. 模型池

**代码位置**：`service/app/llm/pool.py`（Python 重写 `src/lib/model-pool.ts`），单价表 `pricing.py`，记账 `usage.py`。

### 2.1 两个 provider、两条档位链

| provider | base URL | key 回退 |
|---|---|---|
| agnes | `SUMMER_AGNES_BASE_URL`（默认 `https://api.agnes-ai.cn/v1`） | `SUMMER_AGNES_API_KEY` → `SUMMER_DASHSCOPE_API_KEY` |
| aliyun | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `SUMMER_ALIYUN_API_KEY` → `SUMMER_EMBEDDING_API_KEY`（同一个百炼 key，实测就是这么复用的） |

| 档位 | 用在 | 链顺序 |
|---|---|---|
| HIGH | 巡检分析、计划草案、文档工作室 | `agnes-2.5-flash` → 阿里云 max / plus / deepseek / kimi / glm 系（按强度递减） |
| LOW | 标题生成、记忆抽取、任务拆分 | `agnes-2.5-flash` → `qwen-flash` → `qwen3.x-flash` → `qwen-turbo` |
| EMBEDDING | 知识库 / 记忆向量化 | `text-embedding-v4` → `text-embedding-v3` |
| RERANK | 召回后精排 | `qwen3-rerank` / `qwen3.7-text-rerank` / `gte-rerank-v2` |

**链是代码常量，不进环境变量**。原因：把 17 个模型名放进 `.env` 只会带来"配错一个名字 → 静默降级到最弱模型"的故障，而链的改动本来就是发版行为。文档只锁三条不可突破的约束：

1. **embedding 链只能放 1024 维模型**（历史事故见 §3.1）；
2. **rerank 必须走原生端点** `POST /api/v1/services/rerank/text-rerank/text-rerank`——`compatible-mode/v1/reranks` 实测 **404**（2026-09-23），`compatible-api/v1/reranks` 是另一条路由；两种信封都要能解析，端点写错会退化成"全 0 分的原序"，必须避免静默失效；
3. **模型名必须传完整快照字符串**（如 `qwen3.8-max`），禁止简写——简写会命中平台的"最新别名"，导致回归对比失去意义。

### 2.2 配额、限流与熔断（实测语义）

| 情况 | 判定 | 动作 |
|---|---|---|
| 免费额度用尽 | 403 `AllocationQuota.FreeTierOnly` | 标记该模型 `exhausted` → **永久跳过**，换链上下一个 |
| 限流 | 429 | `mark_rate_limited(model, 60s)`，冷却期内不选它 |
| 5xx / 超时 | 网络类错误 | 换下一个模型，本轮最多重试 2 次 |
| 链上全部不可用 | — | 抛 `UpstreamFailed` → 运行时走规则兜底（`fallback_analysis`） |

阿里云百炼的免费额度是**每个模型独立**的（100 万 tokens/模型，有效期 2026-11-07），所以"链"同时也是"额度池"，这是本项目成本能压到近 0 的原因。

### 2.3 成本口径（面试要说准）

- **记账**：每次调用写 `tokenusage`（`input_tokens` / `output_tokens` / `total_tokens` / `model` / `tier` / `surface` / `run_id`）；`total_tokens <= 0` 或写库失败**不阻断主流程**（记账是旁路）。
- **成本**：`tokens × 单价`（`pricing.py`，USD/1M tokens），在**聚合时**计算——改价不追溯历史，这条取舍要主动说明；唯一例外是 `evalrun.cost_usd`，它是跑那一刻的快照，因为要和基线比。
- **三条上限**：
  1. 用户交互面（复盘作答、计划草案）：`SUMMER_AI_TOKEN_LIMIT` = **100000** tokens/天（0=不限；VIP 不限但仍记账）；
  2. 巡检：**20k tokens/天/用户**（PRD 3.9），超限当轮只出规则建议；
  3. 全局：`SUMMER_DAILY_BUDGET_USD`（默认 3），当日估算成本超了停 LLM，巡检降级并记警告日志。
- **诚实表述**：目前跑在免费额度上，现金成本≈0；成本账本是"按单价估算要花多少"，不是账单。不要把它讲成"我每天花 X 元"。

### 2.4 流式与超时

- 复盘作答走 SSE（`meta → delta → result → done`），首字目标 ≤ 2 秒；后端用 `streamTextWithFallback` 的等价实现（Python 侧 `httpx` 流式 + 逐块转发）。
- 每次 LLM 调用独立超时（分析 30 秒）；巡检整轮另有 30 秒总超时（`backend.md` §3.5）。
- rerank 单次请求 **8 秒超时**（参考实现如此），超时即放弃精排用向量序。

## 3. Embedding 与 pgvector 检索链路

### 3.1 维度契约（踩过坑，写在最前面）

- 列类型是 `vector(1024)`；链上每个模型输出必须都是 1024 维。
- 实测：`text-embedding-v4` = 1024 ✅，`text-embedding-v3` = 1024 ✅，**`text-embedding-v2` = 1536 ❌ 且直接忽略 `dimensions` 参数**，`v1` = 1536 ❌。所以 v2/v1 **绝不能进链**。
- 历史事故：旧实现把向量存 `jsonb` + 应用层 JS 余弦 + `LIMIT 1000` 静默截断。v2 的 1536 维写进库**不报错**，只因长度不等而余弦恒为 0——静默永远检索不到。本地库实测遗留 **116 条 1536/512 维数据**（历史上换过三次向量模型）。现在：列上是 `vector(1024)`，写库前断言维度，不符**直接抛错**。

### 3.2 检索链路（5 步）

```
query 文本
 ├─1 embed(query) → vector[1024]（embedding 链，失败则跳第 2 步走关键词兜底）
 ├─2 库内检索：ORDER BY embedding <=> $1::vector LIMIT k
 │   （强制 user_id 过滤；可选 source_name / source_type 过滤）
 ├─3 可选精排：rerank(query, candidates) → 重排序（8 秒超时，失败即用原序）
 ├─4 去重与截断：同一 chunk 只留一次，最多 6 段进上下文
 └─5 拼上下文 → 交给 LLM（每题都要能追回 chunk id，用于证据展示）
```

**SQL 现状与迁移要点**（参考实现 `src/lib/rag/retriever.ts` 实测）：

```sql
SELECT id, content, source_name, chunk_index,
       (embedding <=> $1::vector) AS distance
FROM documentchunk
WHERE user_id = $2
ORDER BY embedding <=> $1::vector
LIMIT $3;                      -- topK 默认 5
```

- `<=>` 是余弦**距离**（= 1 − 余弦相似度），升序即最相似；相似度阈值按 `1 - distance` 比。
- 向量以 JSON 数组字面量字符串传参（`"[0.1,0.2,...]"`），由 `::vector` 解析；Python 侧用 asyncpg 同样传字符串参数，**不要自己拼 SQL**。
- **空向量必须调用方挡住**：`'[]'::vector` 会让 PostgreSQL 直接报错（已有单测盯着这条）。
- 索引：`CREATE INDEX ... ON documentchunk USING hnsw (embedding vector_cosine_ops)`，`usermemory` 同样一张；在 Alembic `0001_initial` 里建；`CREATE EXTENSION IF NOT EXISTS vector` 由迁移执行（db 容器默认用户是超级用户，够用）。

### 3.3 阈值表（一处定义，多处引用）

| 场景 | 值 | 出处 |
|---|---|---|
| 题目/弱项去重 | 余弦相似度 ≥ **0.88** 视为重复 | PRD 3.9 |
| 弱项合并（写入 `usermemory` 前） | ≥ **0.88** 合并 | `backend.md` §2.2 `upsert_weakness` |
| 记忆检索 | 取 20 条 | `backend.md` §3.1 |
| chunk 检索 | `k = 5`（题库抽题 `k = size`） | 本节 §3.2 |

### 3.4 降级

| 失败 | 行为 |
|---|---|
| embedding 服务不可用 | 检索回落关键词 `ILIKE`；导入**整体失败**（不留半套数据） |
| rerank 超时或不可用 | 用向量序，日志记 `rerank_skipped=true` |
| pgvector 扩展缺失 | 迁移阶段就该报错；运行时若报错按 `Internal` 处理并告警 |

## 4. OSS 预签名与 key 规范

**端点**：`POST /api/v1/uploads/presign`（接口细节见 `api/01-system.md` §1.4）；**密钥只在 service**，web 侧不安装 `ali-oss`。

| 项 | 规范 |
|---|---|
| 用途白名单 | `avatars` / `wallpapers` / `checkins`（新增用途就加一项，密钥前缀与校验逻辑自动复用） |
| key 格式 | `{purpose}/{user_id}/{毫秒时间戳}-{8 字节随机 hex}.{ext}` |
| 扩展名白名单 | `png` / `jpg` / `jpeg` / `webp` / `gif` |
| 签名 | `PUT`，有效期 **300 秒**；`Content-Type` 参与签名——浏览器 PUT 时必须带**同一个** Content-Type，否则 OSS 返回 403 |
| 返回 | `{upload_url, key, public_url, expires_in}` |
| 归属校验 | `is_owned_url()`：必须匹配 `{OSS_PUBLIC_BASE_URL}/{purpose}/{user_id}/` 前缀，防 URL 注入 |
| 入库校验 | 写库前 `HEAD` 一次拿 `content-length`，超过上限拒绝（防超大文件混进业务表） |
| 换图清理 | 旧对象 `DELETE` 是 best-effort，失败只记日志，不阻断 |

## 5. 环境变量与密钥清单

### 5.1 service（前缀 `SUMMER_`）

| 变量 | 用途 | 必填 | 备注 |
|---|---|---|---|
| `SUMMER_DATABASE_URL` | PostgreSQL 连接 | ✅ | 缺失**拒绝启动** |
| `SUMMER_JWT_PUBLIC_KEY` | 校验 web 签发的 JWT | ✅ | 缺失拒绝启动（不允许静默无鉴权） |
| `SUMMER_CRON_SECRET` | `POST /cron/daily` 的 Bearer | ✅ | `openssl rand -hex 32` |
| `SUMMER_AGNES_API_KEY` / `_BASE_URL` | 首选模型 | ✅ | 免费额度 |
| `SUMMER_ALIYUN_API_KEY` | 降级链 | ✅ | 与 `EMBEDDING_API_KEY` 同一个 key |
| `SUMMER_EMBEDDING_API_KEY` | 向量化 | ✅ | 作为 `ALIYUN_API_KEY` 的兜底 |
| `SUMMER_OSS_ACCESS_KEY_ID` / `_SECRET` / `_BUCKET` / `_REGION` / `_PUBLIC_BASE_URL` | 预签名 | ✅ | bucket `summer-checkin-app`，`oss-cn-guangzhou` |
| `SUMMER_AI_TOKEN_LIMIT` | 交互面日限额 | 否 | 默认/线上 **100000**（0=不限） |
| `SUMMER_AGENT_DAILY_TOKENS` | 巡检日上限 | 否 | 默认 **20000** |
| `SUMMER_DAILY_BUDGET_USD` | 全局日预算 | 否 | 默认 3 |
| `SUMMER_SCHEDULE_CRON` | 巡检时间 | 否 | 默认 `0 21 * * *` |
| `SUMMER_TZ` | 业务日时区 | 否 | 默认 `Asia/Shanghai` |
| `SUMMER_LOG_LEVEL` | 日志级别 | 否 | 默认 `info` |

### 5.2 web

| 变量 | 用途 | 必填 |
|---|---|---|
| `DATABASE_URL` | Better Auth / Kysely（**只连认证表**） | ✅ |
| `BETTER_AUTH_SECRET` | 会话签名（`openssl rand -base64 32`） | ✅ |
| `BETTER_AUTH_URL` | 认证回调地址（与对外域名一致） | ✅ |
| `NEXT_SERVER_ACTIONS_ENCRYPTION_KEY` | Server Actions（`openssl rand -hex 32`） | ✅ |
| `SUMMER_JWT_PRIVATE_KEY` | 签发给 service 的 JWT | ✅ |
| `SUMMER_SERVICE_URL` | 仅本地开发 rewrite 用 | 否 |

### 5.3 密钥纪律

- `.env` 一律进 `.gitignore`；仓库只留 `.env.example`（占位值，不写真值）。
- 生产用 compose 的 `env_file` + 服务器文件权限 `600`；容器内不通过 `docker inspect` 可读（避免把密钥写进命令行参数）。
- 日志与错误响应**不得**出现 key、简历正文、作答原文。
- 轮换：JWT 用**双公钥过渡**（service 同时接受新旧公钥 → web 换签发密钥 → 观察一个周期后移除旧公钥）；OSS / 模型 key 轮换走"新建 key → 更新 env → 重启 → 观察 → 禁用旧 key"。

## 6. Docker Compose

### 6.1 生产（`infra/docker-compose.yml`）

| 服务 | 镜像 / 构建 | 端口 | 说明 |
|---|---|---|---|
| `nginx` | `nginx:alpine` | `80` / `443`（**唯一暴露**） | `/` 与 `/api/auth/*` → web；`/api/v1/*` → service；带 `X-Request-Id` 透传 |
| `web` | `infra/web.Dockerfile`（多阶段，`node:22-alpine`，standalone 输出） | 内部 3000 | 非 root；运行时只带 standalone + static + public |
| `service` | `infra/service.Dockerfile`（`python:3.12-slim` + `uv sync --frozen`） | 内部 8000 | 非 root；启动 `uvicorn --workers 1` |
| `db` | `pgvector/pgvector:pg16` | 内部 5432 | 卷 `db_data`；`pg_isready` 健康检查 |

- **`service` 必须单 worker**：APScheduler 跑在进程内，多 worker 会让巡检重复触发。要扩并发就把调度拆成独立 `scheduler` 容器并用 advisory lock 防重——**这是升级路径，不是首版要做的事**。
- 启动顺序：`db` 健康 → `service` 健康（`GET /healthz`）→ `web` → `nginx`。
- **迁移不隐式执行**：发版时单独跑 `docker compose run --rm service alembic upgrade head`（参考工程的 `docker-entrypoint.sh` 也没有跑迁移，这条沿用）。
- 卷：`db_data`（数据库）、`service_tmp`（资料解析临时目录，`tmpfs` 亦可）；`docker compose down` **不带 `-v`**，卷不随容器删除。
- PDF/Word 解析的 Python 依赖在 **service 镜像**里（`pypdf` / `python-docx`），web 镜像不再装 python（参考实现把 PyPDF2 装进了 web 镜像，重写后这一步挪走）。

### 6.2 开发（`infra/docker-compose.dev.yml`）

只起 `db`（pgvector 镜像、映射 5432、自动建扩展）；web 用 `pnpm dev`，service 用 `uvicorn --reload`，前端通过 `next.config.ts` 的 rewrite 访问 `/api/v1/*`。**不装本地 PostgreSQL**，从 R000 起就靠容器。

## 7. CI/CD 流水线

参考工程现有 `.github/workflows/ci.yml`（node 22 + `prisma generate` + `next typegen` + typecheck + lint + test，**不跑 `next build`**——因为 build 需要真实环境变量）。重写后拆成三个工作流：

| 工作流 | 触发 | 步骤 | 门禁 |
|---|---|---|---|
| `ci.yml` → `web-check` | push / PR | `pnpm install --frozen-lockfile` → `next typegen` → `typecheck` → `lint` → `vitest` | 全绿；另加"web 不含 prisma 引用"的 grep 守卫 |
| `ci.yml` → `service-check` | push / PR | postgres(pgvector) service container → `uv sync` → `ruff check` → `ruff format --check` → `pytest` → `alembic upgrade head` → `alembic check` | 全绿；含 `execute_action` 调用点守卫单测 |
| `ci.yml` → `docker-build` | push / PR | buildx 构建 web 与 service 镜像（PR 只构建不推送；main 推送 `ghcr.io/<owner>/summer-checkin-{web,service}:{sha,latest}`） | 构建成功即通过 |
| `eval-gate.yml` | `paths: service/app/agent/prompts.py, service/app/llm/**, service/app/rag/**` + 手动 | 起 db，跑 `python -m app.eval --suite daily --baseline <上次>` | 五项指标超阈值即 fail（PRD 3.9） |
| `deploy.yml` | 手动 `workflow_dispatch`（输入镜像 tag） | 推镜像 → SSH 到服务器 `docker compose pull && up -d` → 跑迁移 → 健康检查 | 健康检查失败即标红并提示回滚 |

- 缓存：`pnpm store`、`uv cache`、buildx `type=gha`。
- 不在 CI 里连生产库；`eval-gate` 用**离线 fixture + 记录下来的模型输出**，只有手动触发时才真调模型（省额度、防噪声）。

## 8. 灰度与回滚

单台服务器 + compose，所以"灰度"分两类，**别把不存在的蓝绿部署写进简历**。

### 8.1 代码灰度（nginx 权重）

```nginx
upstream service_pool {
  server service-a:8000 weight=9;   # 旧版本
  server service-b:8000 weight=1;   # 新版本
}
```

起两个 service 容器（同一数据库），观察 24 小时的错误率与 P95；无异常把权重换成 `10/0`，再下线旧容器。

**前提是 schema 向前兼容**，迁移按三步走：① 只加表/加列（不加无默认的 `NOT NULL`、不改列类型）；② 新旧代码并存期间都能读写（旧代码忽略新列）；③ 删旧列放到**下一个**发布。

### 8.2 prompt / 模型灰度（更常用）

改 prompt 或换模型**不发版也能灰度**：写进 `SUMMER_PROMPT_VERSION`，先只落库不通知（"影子建议"）跑 3 天，对比建议采纳率、成本与 P95，再切主链。回归面板（`/agent/eval`）就是这条流程的仪表盘。

### 8.3 回滚步骤

1. **先止损**：把 nginx 权重回 100% 旧版本（或 `docker compose stop service-b`）。
2. **切镜像**：若新版本已是主版本，`SUMMER_IMAGE_TAG=<上一个 sha> docker compose up -d service`——**镜像永远按 sha 保留，不用 `latest` 回滚**。
3. **数据库**：默认**不 downgrade**。只有确认新迁移没有写数据时，才 `alembic downgrade -1`；否则写一条正向修复迁移（`0002_fix_*`）。
4. **验证**：`GET /healthz` → 打开智能体页看最近一次 run → 手动触发一次巡检 → 批准一条建议（确认审批链路与写库都正常）。
5. **记录**：把事故、影响面、回滚耗时写进发布记录（面试时这是"我处理过线上问题"的素材）。

### 8.4 例行运维

- **备份**：每日 03:00 `pg_dump` 到服务器本地，保留 7 天（`infra/backup.sh`），每月手动下载一份到本地。
- **发布窗口**：21:00 巡检前后 30 分钟不发布（避免 run 半途重启）。
- **日志**：`docker compose logs --since 1h service`；按 `X-Request-Id` 串起 nginx 与 service 两侧。
- **告警**：成本突增、巡检连续失败、`/healthz` 连续 `degraded`——首版靠服务器上的定时脚本发通知，不引入监控系统。

---

**变更记录**

| 日期 | 变更 |
|---|---|
| 2026-09-25 | 首版：依赖总览、模型池与成本口径、embedding/pgvector 链路、OSS 规范、环境变量清单、Compose 与流水线、灰度与回滚 |
