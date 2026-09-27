# 05 · 简历复盘

> 5 个端点，全部 P0。
> 数据落在 `knowledgedoc` / `documentchunk` / `conversation` / `conversationmessage` / `usermemory` / `agentrun`（见 `../data-model/03-knowledge.md`、`04-agent.md`、`05-conversation.md`）。

## 5.0 内容约定

| 项 | 约定 |
|---|---|
| 入库 | `source_name = 'resume:main'`（一份简历一条 `knowledgedoc`）；`source_type = 'resume'` |
| 切块 | **一个项目一块**（`documentchunk`），`chunk_index` 保持简历顺序；`project_id` 就是该 chunk 的 id |
| 追问层级 | L1 事实 → L2 取舍 → L3 数字与失败（PRD 3.4）；同一项目最多 3 层 |
| 卡住判定 | L2/L3 未答出即记弱项，证据是用户原话 |
| 收尾 | 连续 2 个项目卡在同一层 → 本轮提前结束并给学习建议 |
| 脱敏 | 入库前对手机号/身份证正则脱敏；脱敏命中时响应带 `warnings`，且该文本**不进入任何跨主题检索上下文** |

## 5.1 `POST /resume` — 导入简历（P0）

- **鉴权**：用户 JWT
- **请求**：`application/json`（`text`）或 `multipart/form-data`（`file`）
- **响应 201**

```json
{"data": {
  "doc_id": "kd_…", "source_name": "resume:main",
  "projects": [{"project_id": "ch_…", "name": "Summer Checkin", "summary": "学习与复盘平台", "level_covered": ["L1"]}],
  "warnings": ["检测到手机号并已脱敏"]
}}
```

- **行为**：抽取文本 → 脱敏 → 按"项目"切块（识别小标题/时间线）→ embedding → 写 `knowledgedoc`（`UNIQUE(user_id, source_name)`，重复导入即重建）→ 返回抽取到的项目列表。
- **边缘 Case**：PDF 提取失败 → 保留已提取部分 + `warnings` 提示粘贴补充；项目描述过短（< 80 字）→ 仍然入库，但标记 `summary: null`，复盘时先问澄清问题，**不编造追问前提**。
- **错误**：`VALIDATION_FAILED`（文件类型/大小、正文过短）、`UPSTREAM_FAILED`（embedding 不可用 → 整体失败）。

## 5.2 `GET /resume/projects` — 项目条目列表（P0）

- **响应 200**

```json
{"data": [{
  "project_id": "ch_…", "name": "Summer Checkin", "summary": "学习与复盘平台",
  "levels_covered": ["L1", "L2"], "last_reviewed_at": "2026-09-23T22:40:00+08:00",
  "avg_score": 3.7, "weakness_count": 1
}],
"meta": {"projects": 3}}
```

- **口径**：`last_reviewed_at` / `avg_score` 来自该 `project_id` 的历史会话；`weakness_count` 来自关联 `usermemory`。
- **空态**：未导入简历 → `{"data": [], "meta": {"projects": 0}}`，前端提示"先导入简历"。

## 5.3 `POST /resume/sessions` — 开一轮项目追问（P0）

- **请求**

| 字段 | 类型 | 必填 | 约束 |
|---|---|---|---|
| `project_id` | string | 是 | 必须是 5.2 返回的项目 |
| `start_level` | string | 否 | `L1`（默认）/ `L2` / `L3`；从上次卡住的层开始可加速 |

- **响应 201**

```json
{"data": {
  "session_id": "cv_…", "conversation_id": "cv_…", "project_id": "ch_…",
  "level": "L1", "question": "这个系统里你负责哪部分？",
  "created_at": "2026-09-25T22:00:00+08:00"
}}
```

- **行为**：创建 `conversation`（`title = "复盘 · 简历 · Summer Checkin"`）→ 取该项目块 + 过往弱项作为上下文 → 生成 L1 问题 → 写 assistant 消息。
- **错误**：`NOT_FOUND`（项目不属于自己）。

## 5.4 `POST /resume/sessions/{session_id}/answers` — 作答与继续追问（P0）

- **鉴权**：用户 JWT；`Accept: text/event-stream` 时返回 SSE
- **请求**：`{"answer": "…"}`（1–4000 字）
- **响应 200（JSON）**

```json
{"data": {
  "level": "L2",
  "score": {"specificity": 4, "tradeoff": 2, "evidence": 3, "depth": 2},
  "evidence": [{"dimension": "tradeoff", "quote": "当时没想那么多", "note": "未给出取舍与代价"}],
  "weaknesses": [{"memory_id": "m_…", "content": "讲不清方案取舍"}],
  "next_question": {"level": "L2", "text": "为什么选 A 不选 B？代价是什么？"},
  "curtail_reason": null,
  "done": false
}}
```

- **四维口径**（PRD 3.11 R006）：`specificity`（具体性）、`tradeoff`（取舍）、`evidence`（数字与证据）、`depth`（深度）；每题评分必须带证据，无证据标 `invalid: true`。
- **`next_question` 为 `null` 的两种情况**：`curtail_reason = "same_level_twice"`（连续 2 个项目卡同层，提前收尾）或全部项目问完（`done: true`）。
- **重评稳定性**：同一份作答重评两次分差 ≤ 1 分（PRD 3.11）——靠固定评分维度与温度参数实现，实现时在配置里写死。
- **行为**：写 `conversationmessage`（作答 + 反馈）；弱项合并进 `usermemory`；**本轮挂一条 `agentrun`**（`mode='resume-review'`），使简历复盘同样进时间线与成本账本。
- **错误**：`NOT_FOUND`、`VALIDATION_FAILED`、`UPSTREAM_FAILED`（流式开始后失败 → `partial: true`）。

## 5.5 `GET /resume/sessions/{session_id}` — 本轮总结（P0）

- **响应 200**

```json
{"data": {
  "session": {"id": "cv_…", "project_id": "ch_…", "status": "completed",
              "levels": ["L1", "L2", "L3"], "answered": 5, "started_at": "…", "completed_at": "…"},
  "scores": {"avg": 3.2, "by_dimension": {"specificity": 3.8, "tradeoff": 2.6, "evidence": 3.1, "depth": 2.7}},
  "weaknesses": [{"memory_id": "m_…", "content": "讲不清方案取舍", "evidence": "L2 第 2 问"}],
  "curtail_reason": null,
  "next_actions": [{"kind": "review_task", "title": "补强：讲清方案取舍", "requires_approval": true}]
}
```

- **说明**：`curtail_reason` 非空时前端显式提示"本轮提前结束，原因是连续两题卡在同一层"，并展示学习建议。
- **错误**：`NOT_FOUND`。

---

**变更记录**

| 日期 | 变更 |
|---|---|
| 2026-09-25 | 首版（5 个端点全 schema + 内容约定） |
