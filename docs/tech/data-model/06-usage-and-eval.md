# 06 · 成本账本与回归门禁

> 4 张表：`tokenusage`（沿用，加一列）+ **新增** `evalfixture`、`evalrun`、`evalresult`。
> **归属**：全部由 `service/` 读写。`eval` 的跑法见 `../README.md` §4（service 内 CLI + CI 调用）。

## 6.1 `tokenusage`

**成本账本**：模型池每次调用记一行。页面上"这次巡检花了多少"就是这张表求和。

| 列 | 类型 | 默认 / 约束 | 说明 |
|---|---|---|---|
| `id` | text | PK | |
| `user_id` | text | NOT NULL → `user.id` CASCADE | |
| `surface` | text | NOT NULL | 调用面：`agent` / `studio` / `chatroom` / `title` / `memory` / `split` / `agent-bg`；本项目新增 `review`（复盘）。**text 列，新增取值无需迁移** |
| `tier` | text | NOT NULL | 档位：`low` / `high`（模型池的档位，不是具体模型名） |
| `model` | text | NOT NULL | 实际使用的模型名 |
| `input_tokens` | integer | NOT NULL, `0` | |
| `output_tokens` | integer | NOT NULL, `0` | |
| `total_tokens` | integer | NOT NULL, `0` | 由前两者相加，写入时算好（便于求和不用表达式） |
| **`run_id`** | text | NULL → `agentrun.id` **SET NULL** | **新增列**：成本归因到具体 run；SET NULL 保证清理 run 时账本不失真 |
| `created_at` | timestamptz | NOT NULL, `now()` | |

**索引**：`INDEX(user_id, created_at)`；建议新增 `INDEX(run_id)`（按 run 汇总成本）。
**本项目用法**：`surface='review'` 记录复盘调用；巡检调用的 `run_id` 必须填，否则"每次巡检成本"算不出来。

## 6.2 `evalfixture`（新增）

**冻结的回归样本**：把真实跑过的巡检/复盘固化成可重放的输入。

| 列 | 类型 | 默认 / 约束 | 说明 |
|---|---|---|---|
| `id` | text | PK | |
| `user_id` | text | NULL → `user.id` CASCADE | NULL = 系统样本（不含个人数据，可进仓库种子） |
| `suite` | text | NOT NULL | 套件：`daily`（巡检）/ `quiz`（题库复盘）/ `resume`（简历复盘） |
| `name` | text | NOT NULL | 样本名，如 `连续中断3天` |
| `source_run_id` | text | NULL → `agentrun.id` **SET NULL** | 来源 run；**被引用的 run 不参与清理** |
| `fixture_schema_version` | integer | NOT NULL, `1` | 输入结构版本：Observe 快照加字段时递增，旧样本批量停用后重新固化（防止老样本"静默照过"） |
| `input` | jsonb | NOT NULL | 冻结的输入：Observe 快照（连续天数、时长、待办、弱项） |
| `expected` | jsonb | NULL | 期望行为（工具选择、关键字段），人工填写；为 NULL 表示"只看是否变差" |
| `tags` | text[] | NOT NULL, `'{}'` | 标签：`regression` / `edge` / `hard` |
| `enabled` | boolean | NOT NULL, `true` | 关掉即不参与重放 |
| `created_at` | timestamptz | NOT NULL, `now()` | |

**索引**：`UNIQUE(user_id, suite, name)`、`INDEX(suite, enabled)`。
**怎么来的**（一键固化）：在智能体页某次 run 上点"固化为样本" → 取该 run 的 Observe 步骤 `input` 作为 `input`，`expected` 留空，标签 `regression`。

## 6.3 `evalrun`（新增）

**一次重放**：同一套 fixture 在某个 prompt/模型组合下跑一遍。

| 列 | 类型 | 默认 / 约束 | 说明 |
|---|---|---|---|
| `id` | text | PK | |
| `user_id` | text | NULL → `user.id` CASCADE | |
| `suite` | text | NOT NULL | 与 fixture 对应 |
| `prompt_version` | text | NOT NULL | 被测提示词版本，如 `daily-review@1.1.0` |
| `model` | text | NOT NULL | 被测模型 |
| `baseline_run_id` | text | NULL → `evalrun.id` **SET NULL** | 对比基线（上次通过的 run） |
| `status` | text | NOT NULL, `'running'` | `running` / `passed` / `failed` / `error` |
| `total` | integer | NOT NULL, `0` | 样本数 |
| `passed` | integer | NOT NULL, `0` | |
| `failed` | integer | NOT NULL, `0` | |
| `pass_rate` | double precision | NULL | `passed / total` |
| `cost_usd` | numeric(12,6) | NULL | 本轮总成本（按 `tokenusage` 折算） |
| `p95_latency_ms` | integer | NULL | P95 单样本延迟 |
| `git_sha` | text | NULL | 代码版本，出问题时能回到那一刻 |
| `started_at` / `completed_at` | timestamptz | NULL | |
| `created_at` | timestamptz | NOT NULL, `now()` | |

**索引**：`INDEX(user_id, created_at)`、`INDEX(suite, status)`、`INDEX(prompt_version)`。

## 6.4 `evalresult`（新增）

**单样本结果**：一次重放里每条 fixture 一行。

| 列 | 类型 | 默认 / 约束 | 说明 |
|---|---|---|---|
| `id` | text | PK | |
| `eval_run_id` | text | NOT NULL → `evalrun.id` CASCADE | |
| `fixture_id` | text | NOT NULL → `evalfixture.id` CASCADE | |
| `status` | text | NOT NULL | `pass` / `fail` / `error` |
| `actual` | jsonb | NULL | 实际输出（工具选择、理由、动作） |
| `expected` | jsonb | NULL | 当时的期望快照（fixture 后来改了也能对比） |
| `diff` | jsonb | NULL | 差异摘要：哪个字段变了、从什么变成什么 |
| `score` | double precision | NULL | 评分类样本（复盘）的分数 |
| `latency_ms` | integer | NULL | |
| `cost_usd` | numeric(12,6) | NULL | |
| `tokens_in` / `tokens_out` | integer | NOT NULL, `0` | |
| `created_at` | timestamptz | NOT NULL, `now()` | |

**索引**：`UNIQUE(eval_run_id, fixture_id)`、`INDEX(fixture_id, status)`。

## 6.5 判定规则（CI 门禁）

一次 `evalrun` 判 `failed` 的条件（任一成立）：

| 指标 | 退化判定 |
|---|---|
| 通过率 | 低于基线 5 个百分点以上 |
| 任一样本 | `status='fail'` 且该样本带 `regression` 标签 |
| 评分漂移 | 同一 fixture 的 `score` 平均下降 > 0.5（5 分制） |
| 成本 | 单样本平均成本比基线高 30% 以上 |
| 延迟 | P95 比基线高 50% 以上 |

CI 只在**改了提示词、模型池配置或 agent 运行时**时跑 `eval`；日常提交不跑（省成本、省时间）。

## 6.6 新增汇总（30 = 27 + 3）

| 变更 | 对象 | 说明 |
|---|---|---|
| 新增表 | `evalfixture`、`evalrun`、`evalresult` | 回归门禁 |
| 新增列 | `agentrun.model`、`agentrun.prompt_version` | 回归对比的可比性前提 |
| 新增列 | `tokenusage.run_id` | 成本归因到具体 run |
| 新增取值 | `tokenusage.surface='review'`、`usermemory.type='weakness'/'correction'`、`agentapproval.status='expired'` | 均为 text 列，**无需迁移** |
| 新增索引 | `agentrun(user_id, prompt_version)`、`tokenusage(run_id)` | 按版本与 run 汇总 |

---

**变更记录**

| 日期 | 变更 |
|---|---|
| 2026-09-25 | 首版（`tokenusage` 全字段 + 3 张新表全字段 + 门禁判定规则） |
