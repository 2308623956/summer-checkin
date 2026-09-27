# 后端（service / FastAPI）

> service 是唯一碰业务数据的地方。这份文档回答三件事：**代码放哪、函数长什么样、出事时按什么顺序降级**。
> 边界与硬规则见 `architecture.md` §2；接口签名见 `api/`；表结构见 `data-model/`。参考实现是老工程的 `src/lib/agent/runtime.ts`（886 行）+ `model-pool.ts`（587 行）+ `memory.ts`（469 行），**Python 重写，不逐行翻译**。

## 1. 模块划分

```
service/app/
├── main.py                    应用装配：路由、异常处理器、requestId 中间件、启动自检
├── core/
│   ├── config.py              Settings（pydantic-settings，前缀 SUMMER_）
│   ├── security.py            JWT 验签（JWKS/共享密钥）、require_user、require_cron_secret
│   ├── ids.py                 uuid7()
│   ├── response.py            ok() / list_ok() 包装（唯一出口，路由里不手拼）
│   ├── errors.py              AppError 及子类 + 异常处理器（映射 HTTP 与错误码）
│   ├── pagination.py          encode_cursor / decode_cursor
│   └── logging.py             structlog 配置与字段约定
├── db/
│   ├── base.py                DeclarativeBase
│   └── session.py             async engine、get_session 依赖（**事务边界在这里**）
├── models/                    30 张表的 SQLAlchemy 模型（按域一文件）
├── schemas/                   Pydantic 出入参（按域一文件，字段名与 models 一致）
├── api/v1/                    薄路由：解析 → 校验 → 鉴权 → 调 service → 包装响应
│   └── system.py study.py agent.py quiz.py resume.py stats.py eval.py uploads.py
├── services/                  业务规则、事务、幂等、审计都在这一层
│   └── checkin.py plan.py agent.py review.py quiz.py resume.py
│       knowledge.py memory.py notification.py stats.py usage.py upload.py
├── agent/                     巡检运行时（只做"读与建议"，写库经审批层）
│   ├── runtime.py observe.py analyze.py plan.py execute.py prompts.py report.py scheduler.py
├── llm/
│   ├── pool.py                模型池：档位链、失败降级、限流冷却、耗尽标记
│   ├── embeddings.py          1024 维断言 + 链式降级
│   └── usage.py               记账与当日限额
├── rag/
│   ├── cleaning.py            资料/题库清洗（抽取 → 归一化 → 识题 → 去重 → 切块）
│   ├── chunking.py            切块策略（一题一块 / 一项目一块）
│   └── retrieve.py            向量检索（带 user_id 过滤）
└── eval/                      cli.py runner.py metrics.py（CLI 与接口共用同一实现）
```

**四条分层规则**（与 `architecture.md` §2 一致）：路由不写业务；service 不拼 HTTP 响应；`agent/` 不直接写业务表（写库只走审批层）；`llm/` 与 `rag/` 不感知业务表结构。

## 2. 函数清单

### 2.1 `core`

| 函数 | 签名 | 职责 |
|---|---|---|
| `require_user` | `(request) -> User` | 从 `Authorization` 或同域 cookie 取 JWT → 验签 → 取 `sub`；失败抛 `AuthRequired` |
| `require_cron_secret` | `(request) -> None` | 比对 `SUMMER_CRON_SECRET`；失败抛 `Forbidden` |
| `ok` / `list_ok` | `(data, meta=None) -> dict` | 统一成功响应；`list_ok` 自动补 `nextCursor: null` |
| `encode_cursor` / `decode_cursor` | `(created_at, id) -> str` / `(str) -> tuple` | 不透明游标（base64），非法游标抛 `ValidationFailed` |
| `uuid7` | `() -> str` | 时间有序主键 |

### 2.2 `services`

| 模块 | 函数 | 职责 |
|---|---|---|
| `checkin` | `create_checkin(user_id, payload) -> CheckinResult` | 单事务：写 `checkin` → 累加 `studyrecord` → 完成 `plantask`；返回 `streak_days` |
| | `list_checkins(user_id, *, from_, to, subject, cursor, limit) -> Page` | 列表 + 区间汇总（`days/hours/streak_days`） |
| | `compute_streak(user_id) -> int` | **唯一实现**：按 `checkin_date` 去重向前连续；`/checkins` 与统计共用 |
| `plan` | `list_plans` / `get_plan` / `list_tasks` / `update_task_status` | 计划与任务的读写（状态流转天然幂等） |
| `agent` | `list_runs` / `get_run(run_id, *, include_raw)` | 巡检读路径（含 `usage` 汇总） |
| | `decide_approval(user_id, run_id, approval_id, decision, reason) -> DecisionResult` | **审批唯一入口**：条件更新 → 执行写库动作 → 写 `agentdecision`（全在一个事务） |
| | `expire_stale_approvals(day) -> int` | 当日收尾：把写库类 `pending` 置 `expired` |
| `review` | `start_quiz_session` / `answer_question` / `get_session_summary` | 题库复盘编排（与简历共用消息与评分口径） |
| | `start_resume_session` / `answer_resume_question` | 简历复盘编排（L1/L2/L3 追问、卡层收尾） |
| `knowledge` | `import_document(user_id, *, source_name, source_type, file_or_text) -> ImportResult` | 清洗管线 5 步 + 幂等重建 |
| | `list_documents(user_id, *, source_type, cursor, limit)` | 资料列表 |
| `memory` | `upsert_weakness(user_id, content, embedding, evidence) -> MemoryRef` | 相似度 ≥ 0.88 合并（保留最早与最新证据） |
| | `list_memories` / `resolve_weakness(memory_id, note)` | 弱项列表与"已纠正"（写 `correction`） |
| `stats` | `overview` / `review_quality` / `agent_quality` | 三个只读聚合（口径见 `api/06-stats-eval.md`） |
| `usage` | `summarize(user_id, *, from_, to, group_by, run_id)` | 成本聚合；单价来自配置 |
| `notification` | `create` / `list` / `mark_read` / `cleanup_old` | 通知；`create` 带每日节流去重（同类型同日仅一条） |
| `upload` | `presign(user_id, purpose, content_type, size) -> PresignResult` | OSS key 前缀强制 `purpose/user_id/` |

### 2.3 `agent`（巡检运行时）

| 函数 | 签名 | 职责 |
|---|---|---|
| `run_daily_review` | `(user_id, *, day, force=False) -> RunResult` | 编排一轮：Observe → Analyze → Plan → 通知类直接执行 / 写库类进审批 |
| `observe` | `(user_id) -> LearningContext` | 读上下文（见 §3.1），**只读** |
| `analyze` | `(context, memories, user_id) -> Analysis` | LLM 结构化分析（tier `high`，`json_object`，温度 0.3）；失败回落 `fallback_analysis` |
| `fallback_analysis` | `(context) -> Analysis` | 规则兜底（纯函数，可单测） |
| `to_approvals` | `(analysis) -> tuple[list[Action], list[Action]]` | 按风险分级拆分：通知类 / 写库类；执行建议条数上限 |
| `execute_action` | `(user_id, action, *, approval_id) -> ExecutionResult` | **只能由 `services.agent.decide_approval` 调用**（见 §3.4） |
| `scheduler` | `start()` / `register_daily(21:00)` | APScheduler 注册；同一份实现被 `POST /cron/daily` 复用 |

### 2.4 `llm` / `rag`

| 模块 | 函数 | 职责 |
|---|---|---|
| `llm.pool` | `completions_with_fallback(tier, call, *, user_id, surface) -> Result` | 按档位链依次尝试；配额错/限流错分别处理；成功后记账 |
| | `mark_exhausted(model)` / `mark_rate_limited(model, cooldown=60s)` | 熔断与冷却（沿用参考实现语义） |
| | `is_quota_error(err) -> bool` | 区分"配额用尽"与"暂时失败"，决定是换模型还是重试 |
| `llm.embeddings` | `embed(texts) -> list[vector[1024]]` | **维度断言 1024**，不符直接抛错（绝不写库） |
| `llm.usage` | `record(usage)` / `today_usage(user_id)` | 记账与当日限额；`vip` 只影响限额判断，不改鉴权 |
| `rag.retrieve` | `search(user_id, query, *, k, source_name=None, source_type=None)` | 向量检索（强制 `user_id`）；embedding 不可用时回落关键词 `ILIKE` |

## 3. Agent 运行时（重写的重点）

### 3.1 Observe — 输入与输出

**输出 `LearningContext`（Pydantic 模型，落进 `agentstep.input`）**

| 字段 | 来源 | 与参考实现的差异 |
|---|---|---|
| `profile.goal_memories` | `usermemory.type='goal'` | 不变 |
| `profile.active_plan_count` / `active_plan_names` | `plan.status='active'` | 不变 |
| `stats.streak` | `checkin.checkin_date` 去重向前连续 | 不变（算法抽到 `services.checkin.compute_streak`，**只此一处**） |
| `stats.total_checkins` | `checkin` 计数 | 不变 |
| `focus.today_minutes` / `today_sessions` | `studyrecord` 当日 | 不变 |
| `plans[].progress` / `task_stats` | `plantask` 聚合 | 不变 |
| `pending_tasks[]` | `plantask` 取 20 条（优先级、天序） | 不变 |
| `recent_checkins[]` | 最近 7 次日期 | 不变 |
| **`weaknesses[]`** | `usermemory.type='weakness'` 未纠正，按 `importance` 取 10 条 | **新增**：参考实现完全没读弱项，复盘闭环接不上 |
| **`review`** | 最近 7 天复盘次数、平均分、未复盘的题库主题 | **新增**：巡检才能说"你 5 天没复盘了" |
| **`plan_progress` 只读最近 30 天打卡** | `checkin` | **收紧**：参考实现把全部打卡拉回来只用日期（有用户几千行），改窗口查询 |

**性能**：5~7 个查询并行（`asyncio.gather`），单轮 Observe 目标 < 300 ms；**不允许在 Observe 里调 LLM**。

### 3.2 Analyze — 输入与输出

- **输入**：`LearningContext` + 检索到的长期记忆（`usermemory`，向量相关度 + 重要度，取 20 条）。
- **调用**：tier `high`，`temperature=0.3`，`max_tokens=16384`，`response_format=json_object`，prompt 版本常量 `AGENT_PROMPT_VERSION`（写进 `agentrun.prompt_version`）。
- **输出**：`Analysis { status: on_track | need_attention | need_adjustment | at_risk, summary, findings[], actions[] }`；`findings` ≤ 5 条，`actions` ≤ 3 条（写进 prompt，也做服务端硬校验）。
- **校验**：JSON 解析失败、字段缺失、`actions` 里出现未知 `type` → 该条丢弃并记 `agentstep.output.dropped`；**全部不可用**时走 §3.5 的降级阶梯。

### 3.3 Plan — 风险分级（这一步决定"谁能不经审批"）

| 动作类型 | 风险级 | 处理 |
|---|---|---|
| `SEND_REMINDER` / `ENCOURAGE` / `GENERATE_REPORT` | 通知类 | **直接执行**（写 `notification`），写 `agentdecision(status='executed')` |
| `ADJUST_PLAN`（仅生成通知/建议） | 通知类 | 同上 |
| `CREATE_TASK` / `UPDATE_PLAN`（真改库） | 写库类 | 写 `agentapproval(status='pending')` + `agentdecision(status='pending')`，**等审批** |

限额在 Plan 阶段硬校验（PRD 3.9）：建议 ≤ 3 条/天，其中写库类 ≤ 1 条/天；超出部分降级为通知类或丢弃，并在 `agentstep.output` 记原因。

这一步写一条 `agentstep(kind='plan')`，`output` 记下"哪些建议被分级成写库类、哪些被限额丢弃"——时间线上因此能看清"建议是怎么被拦下来的"，而不是只看到一个总结果。

### 3.4 Execute — 审批才是闸门（**参考实现的缺陷在这里被修掉**）

**参考实现的问题**（`summer-checkin-master/src/lib/agent/runtime.ts`，可对照行号）：

1. 第 741–763 行把 findings / actions 写成 `agentapproval(status='pending')`，注释写明"UI 可展示"——**它只是展示品**；
2. 第 766 行进入 Step 4，第 786–788 行**无条件执行全部 actions**；
3. `executeAction` 的 `CREATE_TASK` 分支（第 484–493 行）**直接 `plantask.create`**，此时审批仍是 `pending`；
4. 第 800–812 行写 `agentdecision(status='pending')`，但 `action` 里又记着 `executed: true`——状态自相矛盾，"建议采纳率"没法算。

**本项目的规则**：

```
run_daily_review()：Observe → Analyze → to_approvals()
    ├── 通知类 → execute 立即写 notification + decision(executed)
    └── 写库类 → 只写 agentapproval(pending) + decision(pending)，本轮到此为止

用户点批准 → services.agent.decide_approval()
    └── 同一事务： 条件更新 approval(pending→approved)
                 → execute_action()（写 plantask / 改 plan）
                 → decision(pending→executed)
```

- `execute_action()` 的调用者**只有** `decide_approval`——用一条单测钉死：`grep -r "execute_action" app/ | grep -v services/agent.py` 必须为空（写进 CI）。
- 批准后**在原 run 上追加一条 `agentstep(kind='execute')`**（`step_number` 取当前最大值 +1），让时间线显示"这一步是被审批放行的"，而不是凭空多出一个任务。
- R001 验收就落在这条链上：构造一条含 `CREATE_TASK` 的巡检 → 未审批时 `plantask` 零新增 → 批准后新增 1 行 → 拒绝时零新增且写 `feedback`。

### 3.5 降级阶梯（按发生顺序）

| 失败点 | 行为 | 用户可见结果 |
|---|---|---|
| LLM 分析失败 / 返回空 / JSON 不合法 | `fallback_analysis()`：规则产出 findings 与 actions | 仍有建议，`agentstep.kind='analyze'` 标 `degraded: true` |
| 模型链全不可用 / 当日配额用尽 | 同上；run 记 `model=null`、`error=QUOTA_EXCEEDED` | 巡检照跑，建议来自规则 |
| 本轮超时（30 秒，PRD 3.9） | 中止 Analyze/Execute，`run.status='timeout'`，已完成步骤保留 | 页面显示"今晚分析超时，已按规则给出建议" |
| 单个动作执行失败 | 该动作回滚，`agentdecision.status='failed'` + 原因；**不影响其他动作** | 审批卡标红 + 可读原因 |
| 通知写入失败 | 只记日志，不影响 run 成败 | 无感知 |
| 数据库写失败 | 事务回滚；run → `failed`，`running` 步骤 → `failed` | 页面显示失败原因 |
| embedding 不可用（复盘/导入） | 检索回落关键词；导入整体失败（不留半套） | "检索降级"提示；导入报 `UPSTREAM_FAILED` |

### 3.6 run 与 step 的状态取值（**与接口文档一致**）

- `agentrun.status`：`queued` → `running` → `completed` / `failed` / `cancelled` / `timeout`
- `agentstep.status`：`pending` / `running` / `completed` / `failed` / `skipped`
- `agentapproval.status`：`pending` / `approved` / `rejected` / `expired`（本项目新增最后一个）
- `agentdecision.status`：`pending`（写库类等审批）/ `executed` / `rejected` / `failed`
- `mode`：`daily-review`（每日巡检）/ `resume-review`（简历复盘）/ `planner`（计划任务草案）

> 参考实现用的是 `completed`（不是 `succeeded`），本项目沿用 `completed`，`api/` 里的示例同步为这个值。

## 4. 事务与幂等落点

| 操作 | 事务边界 | 幂等机制 | 失败处理 |
|---|---|---|---|
| 打卡 | 单事务：`checkin` + `studyrecord` + `plantask` 完成 | 无（同一天允许多次打卡） | 整体回滚，返回 `VALIDATION_FAILED` 或 `NOT_FOUND` |
| 审批批准 | 单事务：条件更新 + 写库动作 + decision | `UPDATE … WHERE id=? AND status='pending'`，0 行 → `CONFLICT` | 回滚，审批退回 `pending`，返回可读原因 |
| 审批拒绝 | 单事务：条件更新 + decision(feedback) | 同上 | 同上 |
| 巡检一轮 | **多事务**：run 创建 → 步骤更新 → 审批/决策 → run 收尾 | 幂等键 `(user_id, 日期, 动作类型)`；当天已有 run 跳过 | 单用户失败不阻断其他用户；失败详情写 `run.error` |
| 工具调用 | 与所属动作同一事务 | `agenttoolcall.idempotency_key` 唯一约束 | 唯一键冲突 → 直接返回既有结果 |
| 资料/题库导入 | 单事务：删旧 chunk → 写 `knowledgedoc` → 批量写 chunk | `UNIQUE(user_id, source_name)`；并发导入同名 → `CONFLICT` | 整体回滚，不留半套数据 |
| 复盘一轮 | 每题一个事务（message + 弱项合并） | 无（作答天然幂等：同题重答覆盖评分 message 不行——**同题重答即追加**，以最后一次为准） | 单题失败不影响本轮其余题 |
| 标记弱项已纠正 | 单事务：写 correction + 关联 | 同主题已有 correction → `CONFLICT` | 回滚 |
| 评测重放 | 每样本一个事务；汇总一条 `evalrun` | `(suite, prompt_version, model, git_sha)` 重复触发 → 返回既有结果 | 环境不可用 → `status='error'`，**不算退化** |

**连接与隔离**：一个请求一个 session；`decide_approval` 使用 `SELECT … FOR UPDATE` 之外的路径——**只靠条件更新的原子性**，不引入分布式锁（单实例部署，这条足够且可解释）。

## 5. 错误与日志规范

### 5.1 异常层级（`core/errors.py`）

```
AppError(code, message, http_status, retryable=False, details=None)
├── AuthRequired        AUTH_REQUIRED      401
├── Forbidden           FORBIDDEN          403
├── NotFound            NOT_FOUND          404
├── Conflict            CONFLICT           409
├── ValidationFailed    VALIDATION_FAILED  422  (details=[{field, issue}])
├── RateLimited         RATE_LIMITED       429
├── QuotaExceeded       QUOTA_EXCEEDED     429
├── UpstreamFailed      UPSTREAM_FAILED    502  (retryable=True)
└── Internal            INTERNAL           500
```

- service 层只抛这些；路由层不 `try/except`（全局异常处理器统一包装）。
- 第三方库异常（httpx/oss2/asyncpg）在边界处转成 `UpstreamFailed` 或 `Internal`，**绝不把原始堆栈透给前端**。
- 未捕获异常 → `INTERNAL` + `requestId`，日志里带完整堆栈。

### 5.2 日志

- 结构化（JSON），每行必带：`ts` / `level` / `event` / `request_id` / `route` / `status` / `duration_ms`；有用户与运行时补 `user_id` / `run_id`。
- `logger.info("[agent] run_finished", run_id=…, actions=…, tokens=…, duration_ms=…)` 这类事件名固定，便于按 event 聚合。
- **不记**：简历正文、题库正文、用户作答原文（这些在库里，日志只记 id 与长度）。
- `X-Request-Id` 由 nginx 生成或透传，service 全程带上，响应回写同值。
- agent 的每一步落库（`agentstep` / `agenttoolcall`），日志只是索引；**排查以库为准**。

### 5.3 启动自检（`main.py`）

缺 `SUMMER_DATABASE_URL` 或 JWT 公钥 → **明确报错并拒绝启动**（不允许静默降级成无鉴权）；数据库连不上 → 打印可读原因后退出；迁移由部署脚本执行，容器启动**不隐式跑**。

## 6. 测试策略

| 层 | 工具 | 覆盖 |
|---|---|---|
| 纯函数 | pytest | `fallback_analysis`、`compute_streak`、游标编解码、清洗管线（用固定样例文本） |
| service 层 | pytest + 测试库（pgvector 容器） | 审批条件更新与并发、导入幂等重建、事务回滚 |
| 接口层 | httpx `AsyncClient` | 响应信封、错误码映射、鉴权（cookie 与 Bearer）、分页 |
| 契约守卫 | 单测 | `execute_action` 的调用者只有 `services/agent.py`；`web/` 侧无业务表访问 |
| eval | pytest + `app/eval` CLI | 固定 fixture 离线重放，指标与判定规则（`data-model/06` §6.5） |

CI 流水线：`ruff check` → `pytest` → `alembic upgrade head`（空库）→ `alembic check` → eval 冒烟（改 prompt/模型时才跑全量）。

## 7. 与参考实现的差异清单（迁移时逐个对照）

| # | 参考实现 | 本项目 | 原因 |
|---|---|---|---|
| 1 | 审批行仅作展示，执行不校验 | 审批是执行闸门 | R001 验收 |
| 2 | `agentdecision.status` 恒为 `pending` | 按真实流转（pending/executed/rejected/failed） | 采纳率要能算 |
| 3 | Observe 不读弱项与复盘 | 新增 `weaknesses` / `review` | 复盘闭环 |
| 4 | 不记录 `model` / `prompt_version` | 每次 run 都记 | 回归对比 |
| 5 | 无超时上限 | 30 秒 + 阶梯降级 | PRD 3.9 |
| 6 | 单文件 886 行 | 拆 `observe/analyze/plan/execute` | 可读可测 |
| 7 | `CREATE_TASK` 无幂等键 | 工具调用带 `idempotency_key` | 重放安全 |
| 8 | Observe 全量拉打卡 | 窗口查询（30 天） | 数据量上来会拖慢 |
| 9 | 规则建议文案较口语化 | 保留"先看再说"的语气，但禁用话术（PRD R003 验收） | 面试演示一致性 |

---

**变更记录**

| 日期 | 变更 |
|---|---|
| 2026-09-25 | 首版：模块划分、函数清单、运行时四步与降级阶梯、事务与幂等、错误与日志、测试策略、与参考实现的差异清单 |
