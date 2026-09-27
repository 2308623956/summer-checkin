# 06 · 统计与回归

> 7 个端点，**全部 P1（只写职责）**——它们对应 R008（统计面板，D22–23）与 R010（回归面板，D24–26），做到时再补全 schema。
> 数据来源：统计走聚合查询（**无新表**）；回归用 `evalfixture` / `evalrun` / `evalresult`（见 `../data-model/06-usage-and-eval.md`）。

## 6.1 `GET /stats/overview` — 学习概览（P1）

**职责**：按 `range`（`7d` / `30d` / `all`，默认 `7d`）返回学习面聚合：打卡天数、连续天数、总时长、任务完成率、按日热力图数据、科目分布。

**关键口径**：全部按 `checkin_date`（业务日）聚合，不按 `created_at`；连续天数与 `GET /checkins` 的 `streak_days` 必须同源同算法（**一处实现两处复用**，不允许各算各的）。

**空态**：无数据时返回零值对象，前端显示空态文案，不画空坐标轴（PRD 3.11 R008）。

## 6.2 `GET /stats/review` — 复盘质量曲线（P1）

**职责**：复盘次数、平均分（题库四维 / 简历四维分开）、弱项存量与已纠正数、弱项按主题与项目的分布、最近 N 次的分数序列。

**关键口径**：
- 分数从 `conversationmessage` 的 Markdown 约定段落解析（`../data-model/05-conversation.md` §5.2 的已知取舍）——**解析逻辑只此一处**，不要在多个接口里各写一遍；
- 题库与简历的维度名不同，返回时用统一结构 `{"scale": "quiz|resume", "dimensions": {...}}`。

**用途**：支撑"弱项曲线"和"标记已纠正后曲线同步变化"（PRD 3.11 R007）。

## 6.3 `GET /stats/agent-quality` — agent 质量与成本（P1）

**职责**：建议采纳率（`agentdecision` 里批准 / 全部）、审批平均处理时延、每次巡检的平均成本与 tokens、P95 延迟、按 `model` 与 `prompt_version` 分组的对比。

**关键口径**：
- 采纳率 = 已决策的 `agentapproval` 中 `status='approved'` 占比（`pending` / `expired` 不计入分母，另列展示）；
- P95 延迟由 `agentstep.started_at/completed_at` 回算（**无需新增埋点**，PRD 3.5）；
- 单日成本 > 近 7 日均值 3 倍时返回 `alerts`，前端标黄。

## 6.4 `GET /eval/fixtures` — 样本列表（P1）

**职责**：按 `suite`（`daily` / `quiz` / `resume`）列出固化样本：`name`、`tags`、`enabled`、`fixture_schema_version`、来源 run、最近一次重放结果。

**口径**：`enabled=false` 的样本默认不返回（加 `include_disabled=true` 才返回）；`fixture_schema_version` 与当前版本不一致的样本在列表里标"待重新固化"。

## 6.5 `POST /eval/fixtures` — 固化一条样本（P1）

**职责**：从一次真实 run 固化样本——取该 run 的 `agentstep(kind='observe').input` 作为 `input`，`expected` 允许留空（留空即"只看是否变差"），并**在固化时脱敏**（真实敏感内容不落库进仓库，PRD 3.6）。

**幂等**：`UNIQUE(user_id, suite, name)` → 同名重复固化返回 `CONFLICT`。

**被引用的 run 不参与清理**（90 天规则里有这条豁免，见 `../data-model/README.md` §7）。

## 6.6 `POST /eval/runs` — 触发一次重放（P1）

**职责**：给定 `suite` + `prompt_version` + `model`，对全部 `enabled` 样本离线重放，写一条 `evalrun` 与逐条 `evalresult`，返回 202 与 `eval_run_id`。

**守卫**：未标 `prompt_version` → 拒绝运行（`VALIDATION_FAILED`）；模型供应商不可用 → `evalrun.status='error'` 且**不算退化**（PRD 3.6）。

**执行方式**：service 内的 CLI 是同一实现（`python -m app.eval --suite daily`），CI 调 CLI 做门禁——**接口与 CLI 共用同一套 service 函数**，避免两条实现分叉。

## 6.7 `GET /eval/runs/{eval_run_id}` — 重放结果与 diff（P1）

**职责**：返回五项指标对比（通过率、评分漂移、成本、P95 延迟、工具选择正确率）、与 `baseline_run_id` 的差值、逐条 `evalresult` 的 `diff`，以及最终判定 `passed` / `failed` / `error`。

**判定规则**：见 `../data-model/06-usage-and-eval.md` §6.5（阈值来自 PRD 3.9）；**判定在 service 算，不在前端算**——CI 读的是同一个结论。

**待补**：面板需要"历史重放列表"时再加 `GET /eval/runs?suite=`（带分页），本文档先不占坑。

---

**变更记录**

| 日期 | 变更 |
|---|---|
| 2026-09-25 | 首版（7 个端点，P1：只写职责与关键口径） |
