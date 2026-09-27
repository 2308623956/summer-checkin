# 接口总则（API）

> 所有接口由 `service/`（FastAPI）提供；`web/` 只调不改。**这份文档是接口的唯一事实来源**——PRD 3.8 只列职责，签名以这里为准。
> 字段名与 `../data-model/` 完全一致（snake_case）；改动接口必须同时改这里和 PRD 的 3.8 摘要。

## 1. 分册索引与优先级

**P0 = 首版验收（R000–R007、R009）必须联调的接口，写全 schema**；**P1 = 收尾与后续（R008、R010 及增强），只写职责**，做到时再补 schema。

| 分册 | 模块 | 端点数 | P0 / P1 |
|---|---|---|---|
| `01-system.md` | 系统、定时与上传 | 4 | 4 / 0 |
| `02-study.md` | 打卡、计划、任务 | 8 | 6 / 2 |
| `03-agent.md` | 巡检、审批、成本、弱项、通知 | 9 | 8 / 1 |
| `04-quiz.md` | 题库复盘与知识导入 | 6 | 6 / 0 |
| `05-resume.md` | 简历复盘 | 5 | 5 / 0 |
| `06-stats-eval.md` | 统计与回归 | 7 | 0 / 7 |
| **合计** | | **39** | **29 / 10** |

## 2. 前缀、版本与内容协商

- 统一前缀 `/api/v1`；请求与响应均为 `application/json`（UTF-8），流式接口例外（见 §7）。
- 破坏性变更 → `/api/v2`，不长期并存两个版本；非破坏性新增字段不改版本。
- 时间一律 ISO 8601 带时区：`2026-09-25T21:00:00+08:00`；**日期范围参数 `from`/`to` 按业务日（Asia/Shanghai）切分**。
- 字段名与数据模型一致，前端不做 camelCase 转换。

## 3. 鉴权（三种调用方）

| 调用方 | 凭据 | 说明 |
|---|---|---|
| 浏览器（web 页面） | httpOnly cookie 里的短期 JWT | nginx 直达 service，cookie 同域自动携带；`Authorization` 优先于 cookie |
| CLI / CI（eval、脚本） | `Authorization: Bearer <JWT>` | 由 web 的 `/api/auth/*` 换取 |
| 定时触发 | `Authorization: Bearer $CRON_SECRET` | 仅 `POST /cron/daily` 接受；不是用户身份 |

- service 侧**所有查询强制带 `user_id`**（从 JWT `sub` 取），缺失或验签失败返回 `AUTH_REQUIRED`；跨用户访问一律 `NOT_FOUND`（不泄露存在性）。
- 未鉴权可访问的只有 `GET /healthz`（只暴露存活信息）。

## 4. 统一响应与错误

```json
// 成功
{"data": { }}
// 列表
{"data": [ ], "meta": {"nextCursor": null, "total": 42}}
// 失败
{"error": {"code": "VALIDATION_FAILED", "message": "hours 必须在 0–24 之间", "requestId": "…", "details": [{"field": "hours", "issue": "gt"}]}}
```

| HTTP | code | 何时返回 |
|---|---|---|
| 401 | `AUTH_REQUIRED` | 缺凭据 / 验签失败 / JWT 过期 |
| 403 | `FORBIDDEN` | 凭据有效但无权（含 cron secret 错误） |
| 404 | `NOT_FOUND` | 对象不存在或不属于当前用户 |
| 409 | `CONFLICT` | 幂等冲突：重复审批、重复导入、状态已流转 |
| 422 | `VALIDATION_FAILED` | 入参校验失败（带 `details`） |
| 429 | `RATE_LIMITED` / `QUOTA_EXCEEDED` | 频率限制 / 当日 token 配额用尽 |
| 502 | `UPSTREAM_FAILED` | 模型或 OSS 不可用（可重试，`retryable: true`） |
| 500 | `INTERNAL` | 未预期错误（日志里有 `requestId` 全链路） |

- 前端按 `code` 分支，中文文案由前端映射（service 不做文案本地化）。
- `message` 面向开发者，可英文；`details` 仅在 `VALIDATION_FAILED` 出现。

## 5. 幂等（不引入通用幂等键表）

**这是刻意的设计选择**：不建 `idempotencykey` 表（那会是第 31 张表），重试安全靠每个写操作的**天然键**：

| 操作 | 幂等落点 |
|---|---|
| 审批 | `UPDATE agentapproval SET status=… WHERE id=? AND status='pending'`，影响 0 行 → `CONFLICT` |
| agent 工具执行 | `agenttoolcall.idempotency_key` 唯一约束 |
| 题目/资料导入 | `UNIQUE(user_id, source_name)` → `ON CONFLICT DO UPDATE`（先删旧 chunk 再重建） |
| 巡检触发 | 幂等键 `(user_id, 日期, 动作类型)`：当天已有 run 则跳过（`force=true` 覆盖） |
| 打卡 | **允许重复**（一天可以打多次卡），不设幂等键 |

- 写接口接受可选的 `Idempotency-Key` 头（仅用于日志与排查关联，不参与去重）——**审批接口必须带**，用于把"用户点了两次"和"网络重试"区分开。
- 面试问答口径：为什么不用通用幂等表？因为每个写操作的天然键都不同，加一张表只是把"去重逻辑"从业务层搬到基础设施层，还多一处要清理的状态。

## 6. 分页

- 游标分页：`?limit=20&cursor=<opaque>`，`limit` 默认 20、最大 100；响应 `meta.nextCursor`（无更多为 `null`）。
- 排序固定 `created_at DESC, id DESC`（游标编码的就是这两个值），避免 offset 在持续写入时漂移。
- 需要跨页统计的接口（统计面板）不用游标，直接返回聚合结果。

## 7. 流式

- 复盘的单题反馈支持流式：`POST /quiz/sessions/{id}/answers`、`POST /resume/sessions/{id}/answers` 带 `Accept: text/event-stream` 时返回 SSE，事件顺序固定：`meta`（评分维度骨架）→ `delta`（增量文本）→ `result`（结构化结果）→ `done`。
- 不带该头则返回普通 JSON（CLI/CI 用）。
- 首字 ≤ 2 秒、整题 ≤ 8 秒（PRD 3.10）；超时先返回已有内容并标 `partial: true`，不返回半截 JSON。

## 8. 限流、超时与配额

| 项 | 值 | 触发后 |
|---|---|---|
| 巡检单次 | 30 秒 | 中止并走规则降级，run 标 `timeout` |
| 单题反馈 | 8 秒（首字 2 秒） | 返回部分内容，`partial: true` |
| 每日 token | 20k / 用户（PRD 3.9） | `QUOTA_EXCEEDED`，巡检自动降级为规则建议 |
| 写接口频率 | 60 次 / 分钟 / 用户 | `RATE_LIMITED` |

## 9. 新增一个接口的 5 步

1. 在 `api/` 对应分册写契约（路径、鉴权、入参、响应、错误、副作用）；
2. `service/app/schemas/` 建 Pydantic 模型（字段名与数据模型一致）；
3. `service/app/api/v1/` 加**薄**路由：解析 → 校验 → 鉴权 → 调服务层 → 包装响应；
4. `service/app/services/` 写业务规则（事务、幂等、审计都在这一层）；
5. `service/tests/` 加接口测试，并回填 `../README.md` 的追溯表与 PRD 3.8 摘要。

**OpenAPI**：FastAPI 自动生成 `/api/v1/openapi.json`；`/docs` 仅在本地/内网开启（生产用 nginx 屏蔽或加 Basic 认证）。

---

**变更记录**

| 日期 | 变更 |
|---|---|
| 2026-09-25 | 首版：总则 + 38 个端点的分册索引与优先级 |
