# 02 · 学习计划与打卡

> 6 张表：`plan`、`plantask`、`todo`、`checkin`、`studyrecord`、`plantemplate`。
> **归属**：接口由 `service/` 提供；页面在 `web/` 的"计划 / 打卡 / 主页"。
> 这是原项目最核心的既有数据，**结构不动**——巡检 agent 的输入（连续天数、时长、待办）全部来自这里。

## 2.1 `plan`

一个学习计划（可含 Markdown 计划文档，文档改动会触发任务重拆）。

| 列 | 类型 | 默认 / 约束 | 说明 |
|---|---|---|---|
| `id` | text | PK | |
| `user_id` | text | NOT NULL → `user.id` CASCADE | |
| `name` | text | NOT NULL | 计划名 |
| `description` | text | NULL | 简介 |
| `goal` | text | NULL | 目标（SMART 目标写在这里，巡检会引用） |
| `document` | text | NULL | Markdown 计划正文 |
| `tasks_source_hash` | text | NULL | 上次拆任务所用文档的哈希，用于判断"文档改了 → 任务过期" |
| `tasks_splitting_at` | timestamptz | NULL | 非空 = 后台正在拆任务，前端显示"刷新中" |
| `start_date` | timestamptz | NULL | 计划开始日 |
| `status` | text | NOT NULL, `'active'` | `active` / `archived` |
| `created_at` | timestamptz | NOT NULL, `now()` | |
| `updated_at` | timestamptz | NOT NULL, `now()` | |

**索引**：无额外索引（按 `user_id` 走全表小结果集）。
**关系**：1-N → `plantask`（CASCADE）；1-N → `checkin`（**不级联**，删计划不清打卡）。

## 2.2 `plantask`

计划下的任务条目（按天/周编排），也是审批通过后**补强任务**的落地表。

| 列 | 类型 | 默认 / 约束 | 说明 |
|---|---|---|---|
| `id` | text | PK | |
| `plan_id` | text | NOT NULL → `plan.id` CASCADE | |
| `user_id` | text | NOT NULL → `user.id` CASCADE | 冗余，便于按用户查（避免每查都 join plan） |
| `title` | text | NOT NULL | |
| `description` | text | NULL | |
| `day_number` | integer | NULL | 第几天（与 `start_date` 组合出日期） |
| `week_number` | integer | NULL | 第几周 |
| `category` | text | NOT NULL, `'study'` | 任务类别；补强任务沿用现有取值，来源靠 `agentdecision.action` 追 |
| `status` | text | NOT NULL, `'pending'` | `pending` / `done` / `skipped` |
| `priority` | text | NOT NULL, `'normal'` | `low` / `normal` / `high` |
| `completed_at` | timestamptz | NULL | |
| `created_at` | timestamptz | NOT NULL, `now()` | |
| `updated_at` | timestamptz | NOT NULL, `now()` | |

**索引**：`INDEX(plan_id)`、`INDEX(user_id, status)`、`INDEX(user_id, day_number)`。
**本项目用法**：**只有审批通过后**才允许由 agent 写入本表（原实现在巡检路径上直接写入，是必须修的缺陷——见 `../../PRD.md` R001）。

## 2.3 `todo`

轻量待办（不挂在计划下）。

| 列 | 类型 | 默认 / 约束 | 说明 |
|---|---|---|---|
| `id` | text | PK | |
| `user_id` | text | NOT NULL → `user.id` CASCADE | |
| `title` | text | NOT NULL | |
| `completed` | boolean | NOT NULL, `false` | |
| `created_at` | timestamptz | NOT NULL, `now()` | |
| `updated_at` | timestamptz | NOT NULL, `now()` | |

**索引**：`INDEX(user_id, completed)`、`INDEX(user_id, created_at)`。
**本项目用法**：巡检 Observe 阶段读"未完成待办数"作为"任务量是否过载"的依据。

## 2.4 `checkin`

一次打卡记录，是统计与巡检的主要事实表。

| 列 | 类型 | 默认 / 约束 | 说明 |
|---|---|---|---|
| `id` | text | PK | |
| `user_id` | text | NOT NULL → `user.id` CASCADE | |
| `plan_id` | text | NULL → `plan.id`（不级联） | 关联计划 |
| `source_task_id` | text | NULL | 由哪个计划任务完成而来（**无外键**，与参考实现一致） |
| `content` | text | NOT NULL | 今天做了什么（复盘与巡检都引用它） |
| `hours` | double precision | NOT NULL, `0` | 学习小时数 |
| `subject` | text | NULL | 科目/主题——**与题库主题、`plantask.category` 用同一套字符串**，这是"学了什么 → 复盘什么"对得上的关键 |
| `mood` | text | NULL | 心情 |
| `screenshot` | text | NULL | 截图 URL（OSS） |
| `checkin_date` | timestamptz | NOT NULL, `now()` | **业务日期**（可能与 `created_at` 跨日：凌晨补打卡） |
| `created_at` | timestamptz | NOT NULL, `now()` | 记录写入时间 |
| `updated_at` | timestamptz | NOT NULL, `now()` | |

**索引**：`INDEX(user_id, checkin_date)`（统计与连续天数）、`INDEX(source_task_id)`。
**本项目用法**：连续天数、7 天时长、科目分布都从这一张表算；**统计一律按 `checkin_date`，不按 `created_at`**。

## 2.5 `studyrecord`

按日聚合的学习时长（打卡之外的手工补录也算）。

| 列 | 类型 | 默认 / 约束 | 说明 |
|---|---|---|---|
| `id` | text | PK | |
| `user_id` | text | NOT NULL → `user.id` CASCADE | |
| `date` | timestamptz | NOT NULL | 归属日期 |
| `total_minutes` | double precision | NOT NULL, `0` | 当日总分钟数 |
| `subject` | text | NULL | 科目 |
| `checkin_id` | text | NULL | 若由打卡生成，指向 `checkin.id`（无外键） |
| `created_at` | timestamptz | NOT NULL, `now()` | |

**索引**：`INDEX(user_id, date)`。
**本项目用法**：热力图与"近 7 天时长"的读路径；写入由 service 在打卡成功后同步。

## 2.6 `plantemplate`

新用户引导用的计划模板（注册时克隆给新用户）。

| 列 | 类型 | 默认 / 约束 | 说明 |
|---|---|---|---|
| `id` | text | PK | |
| `name` | text | NOT NULL | |
| `description` | text | NULL | |
| `goal` | text | NULL | |
| `document` | text | NULL | Markdown，含"## 任务安排"段落，克隆后据此生成任务 |
| `created_at` | timestamptz | NOT NULL, `now()` | |

**索引**：无。
**本项目用法**：单用户自用阶段用不到，保留（数据量极小），避免删表引发的连锁改动。

---

**变更记录**

| 日期 | 变更 |
|---|---|
| 2026-09-25 | 首版（6 张表全字段） |
