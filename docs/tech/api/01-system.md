# 01 · 系统与定时

> 4 个端点，全部 P0。这一册是"服务活着、能被调度、前端知道有什么功能、图片能传上去"的最小集合。

## 1.1 `GET /healthz` — 存活与依赖状态（P0）

- **鉴权**：无（nginx 与 docker healthcheck 要能打）
- **请求**：无参数
- **响应 200**

```json
{"data": {"status": "ok", "version": "0.1.0", "db": "ok", "uptime_s": 812}}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `status` | string | `ok` / `degraded`（db 连不上时为 `degraded`，仍返回 200，由探针决定是否重启） |
| `version` | string | service 版本（同 `/meta`） |
| `db` | string | `ok` / `down`（`SELECT 1` 结果） |
| `uptime_s` | integer | 进程存活秒数 |

- **不返回**：模型池状态、配额余量（这些进 `/meta`，避免探针接口暴露配置）。
- **错误**：无（依赖故障通过 `db: "down"` 表达）。

## 1.2 `GET /meta` — 版本与功能开关（P0）

- **鉴权**：可选（带凭据时返回该用户的配额余量；不带则 `quota` 为 `null`）
- **请求**：无参数
- **响应 200**

```json
{"data": {
  "version": "0.1.0",
  "env": "production",
  "api_version": "v1",
  "features": {"chatroom": false, "resume_review": true, "quiz_import": true, "eval": true},
  "limits": {"checkin_max_hours": 24, "quiz_size_max": 20, "agent_daily_tokens": 20000},
  "quota": {"used_tokens_today": 3210, "limit_tokens": 20000, "resets_at": "2026-09-26T00:00:00+08:00"}
}
```

- **用途**：W1 骨架的"端到端一条真实链路"就是它——页面顶栏显示版本，功能开关决定入口显隐（聊天室关闭）。
- **前端约定**：`features` 里没有的键按 `false` 处理，前端不得硬编码开关。

## 1.3 `POST /cron/daily` — 触发当日巡检（P0）

- **鉴权**：`Authorization: Bearer $CRON_SECRET`（**不是**用户 JWT）；错误 secret → `FORBIDDEN`
- **调用方**：service 内的 APScheduler（默认 21:00）或外部 cron / CI
- **请求**

| 字段 | 类型 | 必填 | 约束 |
|---|---|---|---|
| `date` | string(date) | 否 | 业务日，默认今天（Asia/Shanghai）；补跑历史日时用 |
| `user_id` | string | 否 | 只跑某个用户（调试用）；缺省跑全部到期用户 |
| `force` | boolean | 否 | 默认 `false`；`true` 时忽略"当天已有 run"的跳过规则 |

- **响应 200**

```json
{"data": {
  "triggered": 1,
  "skipped": [{"user_id": "u_…", "reason": "already_ran"}],
  "runs": [{"run_id": "r_…", "user_id": "u_…", "status": "completed", "approvals_created": 1, "notifications_created": 2}],
  "duration_ms": 8420
}}
```

- **行为**：找出 `agentschedule.enabled = true AND next_run_at <= now()` 的用户；无 schedule 者回退到"有活跃计划的用户"；逐个执行巡检（见 `../architecture.md` §5.1）。
- **幂等**：同一 `(user_id, date)` 已有 `agentrun` 则跳过（`skip.reason = "already_ran"`），`force=true` 覆盖。
- **错误**：`FORBIDDEN`（secret 错）、`VALIDATION_FAILED`（`date` 格式）、`UPSTREAM_FAILED`（模型全不可用——此时仍应产出规则建议，只有连规则都跑不动才报错）。
- **副作用**：写 `agentrun` / `agentstep` / `agenttoolcall` / `agentapproval` / `agentdecision` / `tokenusage` / `notification`；更新 `agentschedule.last_run_at`、`next_run_at`。
- **注意**：cron 失败不影响主站（PRD 3.10）；单用户失败不阻断其他用户，失败详情在各自 `run.error`。

## 1.4 `POST /uploads/presign` — 签发直传 URL（P0）

- **鉴权**：用户 JWT
- **用途**：头像、打卡截图等**图片**直传阿里云 OSS。**密钥只留在 service**（`../architecture.md` §2）；题库/简历这类资料文件不走这里，直接 `POST /knowledge/documents` / `POST /resume` 交给 service 解析。
- **请求**

| 字段 | 类型 | 必填 | 约束 |
|---|---|---|---|
| `purpose` | string | 是 | 白名单 `avatars` / `wallpapers` / `checkins`（新增用途加一项即可复用） |
| `content_type` | string | 是 | `image/png` / `image/jpeg` / `image/webp` / `image/gif` |
| `size` | integer | 是 | 字节数，≤ 5 MB |

- **响应 200**

```json
{"data": {"upload_url": "https://…", "key": "avatars/u_…/1766092800000-3f9a2c1b7d4e8a05.png", "public_url": "https://…/avatars/u_…/…png", "expires_in": 300, "method": "PUT"}}
```

- **行为**：key 格式 `{purpose}/{user_id}/{毫秒时间戳}-{8 字节随机 hex}.{ext}`；URL **300 秒**有效；`Content-Type` 参与签名——浏览器 PUT 时必须带同一个值，否则 OSS 返回 403；PUT 成功后把 `key` 回填到 `POST /checkins`（`screenshot`）或头像更新接口（头像会 best-effort 删旧对象）。
- **入库校验**：写业务表前 `HEAD` 一次拿 `content-length`，超上限拒绝（防超大文件混进业务表）。
- **错误**：`VALIDATION_FAILED`（用途/类型/大小不符）、`UPSTREAM_FAILED`（OSS 不可用，`retryable: true`）。
- **安全**：key 前缀强制为 `purpose + "/" + user_id + "/"`，前端无法指定其他用户的路径；回填的 URL 用同一前缀校验（防 URL 注入）。密钥只在 service（见 `../integrations.md` §4）。

---

**变更记录**

| 日期 | 变更 |
|---|---|
| 2026-09-25 | 首版（4 个端点全 schema） |
