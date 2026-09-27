# 02 · 打卡、计划与任务

> 8 个端点：6 个 P0（写全 schema）+ 2 个 P1（只写职责）。
> 数据落在 `checkin` / `studyrecord` / `plan` / `plantask`（见 `../data-model/02-study.md`）。

## 2.1 `POST /checkins` — 写一次打卡（P0）

- **鉴权**：用户 JWT
- **请求**

| 字段 | 类型 | 必填 | 约束 |
|---|---|---|---|
| `content` | string | 是 | 1–2000 字；"今天做了什么" |
| `hours` | number | 是 | 0–24，最多一位小数 |
| `subject` | string | 否 | ≤ 64 字；**必须与题库主题 / `plantask.category` 用同一套字符串**，否则复盘对不上 |
| `mood` | string | 否 | ≤ 32 字 |
| `screenshot` | string | 否 | OSS key（由 `POST /uploads/presign` 拿到，见 `01-system.md` §1.4） |
| `plan_id` | string | 否 | 关联计划；必须是自己的且 `status='active'` |
| `source_task_id` | string | 否 | 由哪个任务完成而来；给了就把它置 `done` |
| `checkin_date` | string(date-time) | 否 | 默认 now；仅允许"今天"或"昨天"（补打卡） |

- **响应 201**

```json
{"data": {
  "id": "c_…", "checkin_date": "2026-09-25T22:31:00+08:00",
  "streak_days": 6,
  "study_record": {"date": "2026-09-25", "total_minutes": 185, "subject": "后端知识"}
}}
```

- **副作用（同一事务）**：写 `checkin` → 按 `(user_id, date, subject)` 累加 `studyrecord` → 若带 `source_task_id`，把 `plantask.status='done'`、`completed_at=now()`。
- **幂等**：**刻意不做**——同一天允许多次打卡（每次都是独立事实），不设幂等键。
- **错误**：`AUTH_REQUIRED`、`VALIDATION_FAILED`（`hours` 越界 / `checkin_date` 超出允许范围 / `subject` 超长）、`NOT_FOUND`（`plan_id` 不属于自己）、`CONFLICT`（`plan_id` 已归档）。
- **前端约定**：`streak_days` 由服务端算（按 `checkin_date` 去重后向前连续天数），前端不自己算。

## 2.2 `GET /checkins` — 打卡列表 + 区间汇总（P0）

- **鉴权**：用户 JWT
- **请求**：`from`（date，必填）、`to`（date，必填，`to ≥ from`，跨度 ≤ 366 天）、`subject`（可选）、`limit`/`cursor`（见总则 §6）
- **响应 200**

```json
{"data": [{
  "id": "c_…", "content": "…", "hours": 3.0, "subject": "后端知识",
  "checkin_date": "2026-09-25T22:31:00+08:00", "created_at": "2026-09-25T22:31:00+08:00",
  "plan_id": "p_…", "source_task_id": "t_…"
}],
"meta": {"nextCursor": null, "totals": {"days": 6, "hours": 18.5, "streak_days": 6}}}
```

- **排序**：`checkin_date DESC, id DESC`（游标编码这两列）。
- **错误**：`VALIDATION_FAILED`（缺 `from`/`to`、跨度超限）。

## 2.3 `GET /plans` — 计划列表（P0）

- **鉴权**：用户 JWT
- **请求**：`status`（可选，`active` / `archived`，默认 `active`）、`limit`/`cursor`
- **响应 200**：`{"data": [{"id","name","goal","status","start_date","updated_at","task_stats":{"total":12,"done":7}}], "meta": {...}}`
- **错误**：`AUTH_REQUIRED`。

## 2.4 `GET /plans/{id}` — 计划详情（P0）

- **响应 200**：计划全字段 + `document`（Markdown）+ `subjects`（该计划下打卡出现过的 `subject` 去重列表）+ `progress`（`{task_total, task_done, checkin_days, hours}`）+ `tasks_source_hash` + `tasks_splitting_at`
- **错误**：`NOT_FOUND`（不属于当前用户一律 404，不泄露存在性）。

## 2.5 `GET /plans/{id}/tasks` — 任务列表（P0）

- **请求**：`status`（可选 `pending`/`done`/`skipped`）、`day_number`（可选）、`limit`/`cursor`
- **响应 200**：`{"data": [{"id","title","description","day_number","week_number","category","status","priority","completed_at"}], "meta": {"nextCursor": null, "counts": {"pending": 5, "done": 7}}}`
- **排序**：`day_number ASC NULLS LAST, created_at ASC`（任务列表按计划顺序读，不按写入时间）——此接口的游标编码 `(day_number, created_at, id)`。

## 2.6 `PATCH /tasks/{id}` — 更新任务状态（P0）

- **请求**：`{"status": "done" | "pending" | "skipped"}`
- **响应 200**：`{"data": {"id","status","completed_at"}}`
- **幂等**：天然幂等——重复设成同一状态返回 200，不报 `CONFLICT`（与审批不同：这里没有"只能发生一次"的业务含义）。
- **副作用**：`status='done'` 写 `completed_at=now()`；改回 `pending` 清空 `completed_at`。
- **错误**：`NOT_FOUND`、`VALIDATION_FAILED`（非法状态值）。

## 2.7 `POST /plans` — 新建计划（P1）

**职责**：创建一条 `plan`（`name` 必填，`goal`/`description`/`start_date` 可选），返回 201 与新计划对象。起草任务走 2.8。聚合校验（同名计划是否允许）留给实现时定，本文档不预设。

## 2.8 `POST /plans/{id}/generate` — 按目标生成任务草案（P1）

**职责**：拿 `goal` 调模型产出任务草案，**草案一律先进审批**（写 `agentrun` + `agentapproval`，不直接写 `plantask`），返回 202 与 `run_id`，前端跳智能体页看审批卡。`runner` 细节见 `../architecture.md` §5.1——它与每日巡检共用同一条"写库动作必须审批"的路径。

---

**变更记录**

| 日期 | 变更 |
|---|---|
| 2026-09-25 | 首版（6 个 P0 全 schema + 2 个 P1 职责） |
