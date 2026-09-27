# 04 · Agent 运行、审批、记忆与通知

> 9 张表：`agentrun`、`agentstep`、`agentapproval`、`agenttoolcall`、`agentdecision`、`agentschedule`、`usermemory`、`aihistory`、`notification`。
> **归属**：全部由 `service/` 读写（agent 运行时在 Python 侧）；页面在 `web/` 的"智能体"页与通知铃。
> 这组表是原项目最值钱的部分——**完整的执行轨迹 + 人工审批 + 决策理由**。本项目只做两处加列与行为修补，结构不动。

## 4.1 `agentrun`

一次 agent 运行（本项目：一次每日巡检）。

| 列 | 类型 | 默认 / 约束 | 说明 |
|---|---|---|---|
| `id` | text | PK | |
| `user_id` | text | NOT NULL → `user.id` CASCADE | |
| `mode` | text | NOT NULL, `'planner'` | 运行模式：`daily-review`（每日巡检）/ `resume-review`（简历复盘）/ `planner`（计划草案） |
| `goal` | text | NOT NULL | 本次目标，如 `每日巡检 2026-09-25` |
| `status` | text | NOT NULL, `'queued'` | `queued` → `running` → `completed` / `failed` / `cancelled` / `timeout` |
| `current_step` | integer | NOT NULL, `0` | 已执行步数 |
| `max_steps` | integer | NOT NULL, `12` | 步数上限（防失控） |
| `summary` | text | NULL | 结束后的一句话结论 |
| `error` | text | NULL | 失败原因 |
| `started_at` | timestamptz | NULL | |
| `completed_at` | timestamptz | NULL | |
| **`model`** | text | NULL | **新增列**：本次实际使用的模型（含档位），如 `agnes-xxx@low` |
| **`prompt_version`** | text | NULL | **新增列**：提示词版本，`daily-review@1.0.0` |
| `created_at` | timestamptz | NOT NULL, `now()` | |
| `updated_at` | timestamptz | NOT NULL, `now()` | |

**索引**：`INDEX(user_id, updated_at)`、`INDEX(user_id, status)`；建议新增 `INDEX(user_id, prompt_version)`（回归对比要按版本筛）。
**为什么加这两列**：回归面板要回答"换了模型/prompt 之后变好了吗"，没有版本就无法对比。加列不破坏任何既有查询。

## 4.2 `agentstep`

运行中的一步（Observe / Analyze / Plan / Execute 各算一步）。

| 列 | 类型 | 默认 / 约束 | 说明 |
|---|---|---|---|
| `id` | text | PK | |
| `run_id` | text | NOT NULL → `agentrun.id` CASCADE | |
| `step_number` | integer | NOT NULL | 步序 |
| `kind` | text | NOT NULL | 步骤类型：`observe` / `analyze` / `plan`（分级并落审批行）/ `execute`（通知类立即执行；**审批放行后的执行也写回原 run**，见 `../backend.md` §3.4） |
| `status` | text | NOT NULL, `'pending'` | `pending` / `running` / `completed` / `failed` / `skipped` |
| `title` | text | NOT NULL | 时间线上显示的一行 |
| `detail` | text | NULL | 展开细节 |
| `input` | jsonb | NULL | 该步输入（含上下文快照） |
| `output` | jsonb | NULL | 该步输出 |
| `error` | text | NULL | |
| `started_at` / `completed_at` | timestamptz | NULL | |
| `created_at` | timestamptz | NOT NULL, `now()` | |

**索引**：`UNIQUE(run_id, step_number)`、`INDEX(run_id, status)`。
**本项目用法**：`input` 里的 Observe 快照是**冻结 fixture 的素材来源**（回归重放用它做输入）。

## 4.3 `agentapproval`

**审批边界所在**：写库类动作在这里等人工点头，未批准不得执行。

| 列 | 类型 | 默认 / 约束 | 说明 |
|---|---|---|---|
| `id` | text | PK | |
| `run_id` | text | NOT NULL → `agentrun.id` CASCADE | |
| `step_id` | text | NULL → `agentstep.id`（不级联） | |
| `action` | text | NOT NULL | 动作类型，如 `CREATE_TASK` / `UPDATE_PLAN` |
| `status` | text | NOT NULL, `'pending'` | `pending` / `approved` / `rejected` / **`expired`（本项目新增取值）** |
| `payload` | jsonb | NULL | 待执行动作的参数（页面要展示"将创建什么"） |
| `decision_reason` | text | NULL | 审批理由（拒绝时必填，进 `agentdecision.feedback`） |
| `decided_at` | timestamptz | NULL | |
| `created_at` | timestamptz | NOT NULL, `now()` | |

**索引**：`INDEX(run_id, status)`；建议新增 `INDEX(user_id, status)` 需 join，故不建（按 run 查足够）。
**幂等**：批准/拒绝一律用**条件更新** `UPDATE agentapproval SET status='approved', decided_at=now() WHERE id=? AND status='pending'`，影响 0 行 → 返回 `CONFLICT`。这是"点两次只执行一次"的全部机制，不依赖分布式锁。
**过期**：写库类建议当日未处理 → 由当日收尾任务置为 `expired`（`status` 是 text，无需迁移）。

## 4.4 `agenttoolcall`

一次工具调用（含幂等键）。

| 列 | 类型 | 默认 / 约束 | 说明 |
|---|---|---|---|
| `id` | text | PK | |
| `run_id` | text | NOT NULL → `agentrun.id` CASCADE | |
| `step_id` | text | NULL → `agentstep.id`（不级联） | |
| `tool_name` | text | NOT NULL | 工具名 |
| `status` | text | NOT NULL, `'pending'` | |
| `idempotency_key` | text | **UNIQUE**, NULL | 幂等键：`{run_id}:{action}:{业务主键}`，重放同一个动作会撞唯一约束 |
| `input` / `output` | jsonb | NULL | |
| `error` | text | NULL | |
| `started_at` / `completed_at` | timestamptz | NULL | |
| `created_at` | timestamptz | NOT NULL, `now()` | |

**索引**：`UNIQUE(idempotency_key)`、`INDEX(run_id, status)`、`INDEX(run_id, tool_name)`。
**本项目用法**：这是"重复执行不会写两次"的第二道保险（第一道是 4.3 的条件更新）。

## 4.5 `agentdecision`

**决策台账**：每条建议都有一行，带理由，供"建议采纳率"与抽查用。

| 列 | 类型 | 默认 / 约束 | 说明 |
|---|---|---|---|
| `id` | text | PK | |
| `user_id` | text | NOT NULL → `user.id` CASCADE | |
| `run_id` | text | NULL → `agentrun.id` **SET NULL** | run 被清理后决策仍留存（90 天清理不影响采纳率统计） |
| `type` | text | NOT NULL | 决策类型 |
| `reason` | text | NOT NULL | **必填**：为什么给这条建议（面试抽查的就是它） |
| `action` | jsonb | NOT NULL | 动作内容（通知类 / 写库类） |
| `status` | text | NOT NULL, `'executed'` | `pending`（写库类等审批）/ `executed` / `rejected` / `failed` |
| `feedback` | text | NULL | 用户拒绝或纠正时写的理由 |
| `created_at` | timestamptz | NOT NULL, `now()` | |

**索引**：`INDEX(user_id, created_at)`、`INDEX(user_id, type)`、`INDEX(run_id)`。

## 4.6 `agentschedule`

巡检计划（本项目：每日 21:00）。

| 列 | 类型 | 默认 / 约束 | 说明 |
|---|---|---|---|
| `id` | text | PK | |
| `user_id` | text | NOT NULL → `user.id` CASCADE | |
| `type` | text | NOT NULL, `'daily_review'` | |
| `cron` | text | NOT NULL, `'0 9 * * *'` | **本项目改为默认 `0 21 * * *`**（只改默认值，列不变） |
| `enabled` | boolean | NOT NULL, `true` | |
| `last_run_at` | timestamptz | NULL | |
| `next_run_at` | timestamptz | NULL | 调度器按它取到期任务 |
| `created_at` / `updated_at` | timestamptz | NOT NULL, `now()` | |

**索引**：`UNIQUE(user_id, type)`、`INDEX(enabled, next_run_at)`（调度查询走这条）。

## 4.7 `usermemory`

长期记忆，本项目同时是**弱项档案**。

| 列 | 类型 | 默认 / 约束 | 说明 |
|---|---|---|---|
| `id` | text | PK | |
| `user_id` | text | NOT NULL → `user.id` CASCADE | |
| `type` | text | NOT NULL, `'fact'` | **本项目约定新增取值**：`weakness`（弱项）、`correction`（已纠正） |
| `content` | text | NOT NULL | 结论 + 证据 + 日期的结构化文本（见下） |
| `embedding` | vector(1024) | **NULL** | 可空：生成失败时留空而不是丢掉整条记忆 |
| `importance` | double precision | NOT NULL, `0.5` | 权重（统计"最该补的三个弱项"按它排序） |
| `confidence` | double precision | NOT NULL, `0.5` | 置信度（评分证据不足时降低） |
| `last_used` | timestamptz | NULL | 上次被引用时间（长期没用到的不再顶上来） |
| `created_at` | timestamptz | NOT NULL, `now()` | |

**索引**：`INDEX(user_id, type)`、`INDEX(user_id, importance)`、`INDEX(user_id, last_used)`、`HNSW(embedding vector_cosine_ops)`。
**内容约定**（不新增列，靠文本约定 + 后续按需解析）：

```
结论：并发场景下容易漏掉幂等边界
证据：2026-09-24 题库复盘第 3 题未提到条件更新；09-22 简历复盘 L2 追问未答出
状态：未纠正（在同一 type=correction 的记录里留存纠正证据）
```

**已知取舍**：没有独立"主题"列，统计"每个主题的弱项数"需要解析 `content` 前缀。若第 2 周发现统计吃紧，再加 `topic` 列（一条迁移），不在首版过度设计。

## 4.8 `aihistory`

单次问答历史（不构成会话）。

| 列 | 类型 | 默认 / 约束 | 说明 |
|---|---|---|---|
| `id` | text | PK | |
| `user_id` | text | NOT NULL → `user.id` CASCADE | |
| `message` | text | NOT NULL | 提问 |
| `response` | text | NOT NULL | 回答 |
| `created_at` | timestamptz | NOT NULL, `now()` | |

**索引**：`INDEX(user_id, created_at)`。
**本项目用法**：保留（"快速问一句"的落点）；复盘与巡检不写它（写 `conversation` 与 `agentrun`）。

## 4.9 `notification`

站内通知。

| 列 | 类型 | 默认 / 约束 | 说明 |
|---|---|---|---|
| `id` | text | PK | |
| `user_id` | text | NOT NULL → `user.id` CASCADE | |
| `type` | text | NOT NULL, `'reminder'` | 通知类型（提醒/巡检/复盘） |
| `title` | text | NOT NULL | |
| `content` | text | NOT NULL | |
| `read` | boolean | NOT NULL, `false` | |
| `action_url` | text | NULL | 点击跳转（如 `/agent?run=...`） |
| `created_at` | timestamptz | NOT NULL, `now()` | |

**索引**：`INDEX(user_id, read, created_at)`（未读角标）、`INDEX(user_id, type)`。
**本项目用法**：巡检里**通知类建议不需要审批**，直接写这里；写库类必须先过 4.3。

---

**变更记录**

| 日期 | 变更 |
|---|---|
| 2026-09-25 | 首版（9 张表全字段；`agentrun` 新增 `model` / `prompt_version`；`agentapproval.status` 新增取值 `expired`） |
