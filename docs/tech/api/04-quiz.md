# 04 · 题库复盘与知识导入

> 6 个端点，全部 P0。
> 数据落在 `knowledgedoc` / `documentchunk` / `conversation` / `conversationmessage` / `usermemory`（见 `../data-model/03-knowledge.md`、`05-conversation.md`）。

## 4.0 内容约定（写代码前先看）

| 项 | 约定 |
|---|---|
| 主题 | `source_name = 'quiz:<主题>'`，首版两个主题：`quiz:agent-basics`、`quiz:backend`（PRD 3.9） |
| 一题一块 | 一道题 = 一个 `documentchunk`（`source_type='quiz'`），**`question_id` 就是该 chunk 的 id** |
| 题干 / 答案 | 同一块内容里用固定分隔符 `\n---答案---\n`：分隔符前是题干，后面是答案要点。接口只把题干返回给前端 |
| 去重 | 导入时对新题与已有题做向量比对，**余弦 ≥ 0.88 视为重复**，重复题不入库（PRD 3.9） |
| 最短重现 | 同一题 7 天内不再抽到（PRD 3.9），判定依据是 `conversationmessage` 里的历史 `question_id` |
| 评分 | 四个维度 `coverage` / `accuracy` / `structure` / `depth`，1–5 分，**每个维度必须带证据**，无证据标 `null` + `invalid: true` |

## 4.1 `GET /quiz/topics` — 主题列表（P0）

- **鉴权**：用户 JWT
- **响应 200**

```json
{"data": [{
  "topic": "agent-basics", "display_name": "Agent 应用开发",
  "question_count": 42, "due_count": 17, "last_reviewed_at": "2026-09-24T22:10:00+08:00",
  "avg_score": 3.4
}],
"meta": {"topics": 2, "total_questions": 80}}
```

- **口径**：`question_count` = 该主题下 `documentchunk` 行数；`due_count` = 7 天内未被复盘的题数；`avg_score` 取最近 30 天（无数据为 `null`）。
- **空态**：没有任何主题时返回 `{"data": [], "meta": {"topics": 0}}`，前端提示"先导入题目集"。

## 4.2 `POST /quiz/sessions` — 开一轮题库复盘（P0）

- **请求**

| 字段 | 类型 | 必填 | 约束 |
|---|---|---|---|
| `topic` | string | 是 | 必须是 4.1 返回的主题（去掉 `quiz:` 前缀） |
| `size` | integer | 否 | 默认 5，上限 20（PRD 3.9） |
| `include_due_only` | boolean | 否 | 默认 `true`：优先抽 7 天内没做过的题 |

- **响应 201**

```json
{"data": {
  "session_id": "cv_…", "conversation_id": "cv_…", "topic": "backend", "size": 5,
  "questions": [{"index": 1, "question_id": "ch_…", "text": "……"}, "…"],
  "created_at": "2026-09-25T22:00:00+08:00"
}}
```

- **行为**：创建 `conversation`（`title = "复盘 · 题库 · backend · 2026-09-25"`）；抽题（向量检索 + `due` 过滤 + 随机）；把首题作为 assistant 消息写入 `conversationmessage`；`session_id` 就是 `conversation.id`（**不另建会话表**）。
- **分数不足**：可用题少于 `size` 时按实际数量返回，`size` 回填实际值，不报错。
- **错误**：`VALIDATION_FAILED`（主题不存在 / `size` 越界）、`NOT_FOUND`（主题下无题 → 用 `NOT_FOUND` + `message: "该主题还没有题目，请先导入"`）。

## 4.3 `POST /quiz/sessions/{session_id}/answers` — 提交作答并评分（P0）

- **鉴权**：用户 JWT；`Accept: text/event-stream` 时返回 SSE（见总则 §7）
- **请求**

| 字段 | 类型 | 必填 | 约束 |
|---|---|---|---|
| `question_id` | string | 是 | 必须是本轮抽到的题，且是当前未答的题 |
| `answer` | string | 是 | 1–4000 字 |

- **响应 200（JSON）**

```json
{"data": {
  "question_id": "ch_…",
  "score": {"coverage": 3, "accuracy": 4, "structure": 3, "depth": 2},
  "evidence": [{"dimension": "depth", "quote": "我就加个锁吧", "note": "停在加锁，未提条件更新与幂等键"}],
  "invalid": false,
  "weaknesses": [{"memory_id": "m_…", "content": "并发下的幂等边界"}],
  "next_question": {"index": 3, "question_id": "ch_…", "text": "……"},
  "partial": false
}}
```

- **行为**：写两条 `conversationmessage`（user 作答 + assistant 评分，评分用 `../data-model/05-conversation.md` §5.2 的 Markdown 约定）；弱项按 4.0 的去重阈值合并进 `usermemory`；模型不可用 → `score` 各维度为 `null`、`invalid: true`、`weaknesses: []`，**接口仍返回 200**（不阻断复盘）。
- **`next_question`**：本轮还有题则为下一题，全部答完为 `null`（前端据此跳总结页）。
- **错误**：`NOT_FOUND`、`VALIDATION_FAILED`（`question_id` 不在本轮 / 作答超长）、`UPSTREAM_FAILED`（仅当流式已开始后失败：返回已有内容并标 `partial: true`，`message` 说明"评分未完成，可重试本题"）。

## 4.4 `GET /quiz/sessions/{session_id}` — 本轮总结（P0）

- **响应 200**

```json
{"data": {
  "session": {"id": "cv_…", "topic": "backend", "size": 5, "answered": 5, "status": "completed",
              "started_at": "…", "completed_at": "…"},
  "scores": {"avg": 3.1, "by_dimension": {"coverage": 3.2, "accuracy": 3.6, "structure": 3.0, "depth": 2.6}},
  "weaknesses": [{"memory_id": "m_…", "content": "并发下的幂等边界", "evidence": "第 3 题"}],
  "next_actions": [{"kind": "review_task", "title": "补强：并发幂等边界", "requires_approval": true}]
}}
```

- **`status`**：`in_progress` / `completed`（全部答完即完成）。
- **`next_actions` 说明**：这里只是**建议**；要真正生成任务，前端调用审批路径（`POST /runs/{run_id}/approvals/{id}/decide`）——v1 由巡检在当晚把补强任务带进审批，本字段用于即时提示。
- **错误**：`NOT_FOUND`。

## 4.5 `POST /knowledge/documents` — 导入资料 / 题目集（P0）

- **鉴权**：用户 JWT
- **请求**：`multipart/form-data`（`file`）或 `application/json`（`text` + `source_name` + `source_type`）

| 字段 | 类型 | 必填 | 约束 |
|---|---|---|---|
| `source_name` | string | 是 | 题目集用 `quiz:<主题>`；其他资料自定义，长度 ≤ 128 |
| `source_type` | string | 是 | `quiz` / `text` / `md` / `pdf` / `docx` |
| `file` 或 `text` | file / string | 是 | 单个文件 ≤ 5 MB；文本 ≤ 200k 字 |

- **响应 201**

```json
{"data": {
  "doc_id": "kd_…", "source_name": "quiz:backend", "source_type": "quiz",
  "chunk_count": 38, "questions_extracted": 38, "duplicates_skipped": 4,
  "warnings": ["第 12 段没有题号，已作为资料保存"]
}}
```

- **清洗管线（5 步，R005）**：抽取文本 → 归一化（去空行/统一题号） → 分行识别题目 → 去重（余弦 ≥ 0.88） → 切块 + embedding 入库。
- **幂等**：`UNIQUE(user_id, source_name)` → 重复导入同一 `source_name` 时**整主题重建**（先删旧 chunk，再写新 chunk，同一事务）。
- **降级**：向量化失败 → 该题仍入库（`embedding` 为 NULL 会有问题，故**题目必须带向量**；失败则整题跳过并计入 `warnings`），检索走关键词兜底（PRD 3.10 可靠性）。
- **错误**：`VALIDATION_FAILED`（文件类型/大小、`source_name` 超长）、`CONFLICT`（导入正在进行中，同名导入并发）、`UPSTREAM_FAILED`（embedding 服务不可用 → 整体失败，不留半套数据）。

## 4.6 `GET /knowledge/documents` — 资料列表（P0）

- **请求**：`source_type`（可选）、`limit`/`cursor`
- **响应 200**：`{"data": [{"doc_id","source_name","source_type","chunk_count","question_count","created_at"}], "meta": {"nextCursor": null}}`
- **用途**：管理页看"导入了什么、有多少题"；也是排查"为什么搜不到"的第一站。

---

**变更记录**

| 日期 | 变更 |
|---|---|
| 2026-09-25 | 首版（6 个端点全 schema + 内容约定） |
