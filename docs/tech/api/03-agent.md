# 03 · 巡检、审批、成本、弱项与通知

> 9 个端点：8 个 P0（写全 schema）+ 1 个 P1（只写职责）。
> 数据落在 `agentrun` / `agentstep` / `agentapproval` / `agentdecision` / `agenttoolcall` / `tokenusage` / `usermemory` / `notification`（见 `../data-model/04-agent.md`、`06-usage-and-eval.md`）。

## 3.1 `GET /runs` — 巡检列表（P0）

- **鉴权**：用户 JWT
- **请求**：`status`（可选）、`from`/`to`（可选，按 `created_at`）、`limit`/`cursor`
- **响应 200**

```json
{"data": [{
  "id": "r_…", "mode": "daily-review", "status": "completed", "goal": "每日巡检 2026-09-25",
  "summary": "连续 6 天达标，题库弱项 2 条待复习",
  "current_step": 4, "max_steps": 12,
  "model": "agnes-xxx@low", "prompt_version": "daily-review@1.0.0",
  "started_at": "2026-09-25T21:00:02+08:00", "completed_at": "2026-09-25T21:00:11+08:00",
  "cost_usd": 0.0042, "tokens": 5310,
  "pending_approvals": 1
}],
"meta": {"nextCursor": null, "totals": {"runs": 30, "approvals": 12, "adopted": 9}}}
```

- **排序**：`created_at DESC, id DESC`。
- **用途**：智能体页时间线；`pending_approvals > 0` 时列表项显示"待你确认"徽标。

## 3.2 `GET /runs/{run_id}` — 运行详情（P0）

- **响应 200**

```json
{"data": {
  "run": {"id": "r_…", "status": "completed", "goal": "…", "summary": "…", "error": null,
          "model": "agnes-xxx@low", "prompt_version": "daily-review@1.0.0",
          "started_at": "…", "completed_at": "…"},
  "steps": [{"id": "s_…", "step_number": 1, "kind": "observe", "status": "completed",
             "title": "读取近 7 天学习数据", "detail": "…", "started_at": "…", "completed_at": "…", "duration_ms": 120}],
  "approvals": [{"id": "a_…", "step_id": "s_…", "action": "CREATE_TASK", "status": "pending",
                 "payload": {"title": "补强：并发幂等", "day_number": 12},
                 "created_at": "…", "decided_at": null, "decision_reason": null}],
  "decisions": [{"id": "d_…", "type": "suggestion", "reason": "连续 3 天中断，建议缩小任务量",
                 "action": {"kind": "notification"}, "status": "executed", "feedback": null, "created_at": "…"}],
  "usage": {"tokens_in": 4210, "tokens_out": 1100, "cost_usd": 0.0042, "p95_latency_ms": 3200}
}}
```

- **字段说明**：`steps` 只给展示需要的字段（`input`/`output` 全文仅在 `include=raw` 时返回，避免响应过大）；`approvals` 是这一页的**操作入口**（3.3）；`decisions` 是"建议 + 理由"的台账，抽查依据就在 `reason`。
- **请求参数**：`include`（可选，`raw` 时附 `step.input`/`step.output`/`toolcall.output`）
- **错误**：`NOT_FOUND`。

## 3.3 `POST /runs/{run_id}/approvals/{approval_id}/decide` — 审批（P0，最高优先）

- **鉴权**：用户 JWT；**请求头 `Idempotency-Key` 必填**
- **请求**

| 字段 | 类型 | 必填 | 约束 |
|---|---|---|---|
| `decision` | string | 是 | `approved` / `rejected` |
| `reason` | string | 拒绝时必填 | 1–500 字；写入 `agentdecision.feedback` |

- **响应 200**

```json
{"data": {
  "approval": {"id": "a_…", "status": "approved", "decided_at": "2026-09-25T21:30:00+08:00"},
  "executed": {"type": "plantask_created", "task_id": "t_…"},
  "decision_id": "d_…"
}}
```

- **行为**：条件更新 `WHERE id=? AND status='pending'` → 影响 0 行返回 `CONFLICT`（**这就是"点两次只执行一次"的全部机制**）→ 批准则在**同一事务**里执行写库动作（`CREATE_TASK` → 写 `plantask`；`UPDATE_PLAN` → 改 `plan`）→ 写 `agentdecision`（`reason` 与 `feedback`）。
- **拒绝路径**：不执行动作，只写 `agentdecision`（`status='rejected'`、`feedback=reason`）。
- **错误**：`CONFLICT`（已处理 / 已过期）、`NOT_FOUND`（审批不属于该 run 或该用户）、`VALIDATION_FAILED`（`rejected` 缺 `reason`）、`INTERNAL`（执行失败 → 事务回滚，审批退回 `pending` 并返回可读原因）。
- **边缘 Case**：审批已 `expired`（当日未处理被收尾任务作废）→ `CONFLICT` + `message: "该建议已过期，今晚巡检会重新评估"`；`payload` 指向的计划已归档 → `CONFLICT`，不产生半成品数据。

## 3.4 `POST /runs/{run_id}/cancel` — 取消运行（P1）

**职责**：把运行中的 run 置为取消态，停止后续步骤（已在执行的工具调用不回溯）；返回取消结果。主要用于"手动触发后发现不需要了"。

## 3.5 `GET /usage` — 成本账本（P0）

- **鉴权**：用户 JWT
- **请求**：`from`/`to`（按 `tokenusage.created_at`）、`group_by`（`day` / `surface` / `run`，默认 `day`）、`run_id`（可选，查单次巡检成本）
- **响应 200**

```json
{"data": [{"key": "2026-09-25", "tokens_in": 4210, "tokens_out": 1100, "total_tokens": 5310, "cost_usd": 0.0042, "calls": 6}],
 "meta": {"totals": {"total_tokens": 120340, "cost_usd": 0.0812, "calls": 210}, "unit_price_usd_per_1k": 0.0008}}
```

- **口径**：`cost_usd` = `total_tokens / 1000 × 单价`（单价按 `model` 查配置表，配置进环境变量，不落库）；**页面显示值与 `tokenusage` 求和必须一致**（PRD 3.11 R009 验收）。
- **异常提示**：单日成本 > 近 7 日均值 3 倍时，响应带 `meta.alerts: [{"date": "…", "ratio": 3.4}]`（前端标黄）。

## 3.6 `GET /memories` — 弱项档案（P0）

- **请求**：`type`（默认 `weakness`；可选 `correction` / `fact`）、`from`/`to`（按 `created_at`）、`unresolved_only`（默认 `true`）、`limit`/`cursor`
- **响应 200**

```json
{"data": [{
  "id": "m_…", "type": "weakness", "content": "并发场景下容易漏掉幂等边界",
  "importance": 0.8, "confidence": 0.7, "last_used": "2026-09-24T21:00:00+08:00",
  "created_at": "2026-09-22T23:10:00+08:00",
  "evidence": [{"kind": "quiz", "ref": "cv_…", "date": "2026-09-22", "quote": "我就加个锁吧"}],
  "resolved_at": null
}],
"meta": {"nextCursor": null, "counts": {"unresolved": 5, "resolved": 2}}}
```

- **`evidence` 的来源**：`content` 里约定格式写的出处 + 关联会话/运行（`../data-model/04-agent.md` §4.7 的已知取舍）。**v1 只返回 `content` 与关联 id，不保证结构化 quote**；若统计吃紧再加 `topic` 列。
- **`resolved_at`**：由同一主题的 `correction` 记忆推出（没有该记忆则为 `null`）。

## 3.7 `POST /memories/{id}/resolve` — 标记弱项已纠正（P0）

- **请求**：`{"correction_note": "9-25 复盘能把条件更新讲清楚了"}`（必填，1–500 字）
- **响应 200**：`{"data": {"memory_id": "m_…", "correction_id": "m2_…", "resolved_at": "…"}}`
- **行为**：写一条 `type='correction'` 的 `usermemory`（`content` = 结论 + 证据 + 日期），原弱项不改内容（保留历史），`resolved_at` 由 3.6 的口径推出。
- **错误**：`NOT_FOUND`、`VALIDATION_FAILED`、`CONFLICT`（已纠正过——同主题已有 `correction`）。

## 3.8 `GET /notifications` — 通知列表（P0）

- **请求**：`unread_only`（默认 `false`）、`limit`/`cursor`
- **响应 200**：`{"data": [{"id","type","title","content","read","action_url","created_at"}], "meta": {"nextCursor": null, "unread": 2}}`
- **说明**：巡检的**通知类建议直接写这里**（不需要审批），读写库类必须先过 3.3。

## 3.9 `POST /notifications/{id}/read` — 标记已读（P0）

- **请求**：`{"read": true}`（或 `all: true` 标记全部已读）
- **响应 200**：`{"data": {"updated": 1, "unread": 1}}`
- **幂等**：天然幂等。
- **清理**：已读 30 天后由清理任务删除（`../data-model/README.md` §7）。

---

**变更记录**

| 日期 | 变更 |
|---|---|
| 2026-09-25 | 首版（8 个 P0 全 schema + 1 个 P1 职责） |
