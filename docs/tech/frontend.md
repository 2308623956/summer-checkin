# 前端（web / Next.js）

> web 只做两件事：**渲染页面**和**管登录**。所有业务数据都从 `/api/v1/*` 来（service 提供），web 侧不出现任何业务表访问。
> 路由与页面清单来自对参考工程的实测（`src/app` 下 15 个 `page.tsx`），目标结构是 15 个页面 + 2 个新页面 = **17 个**。
> **落地进度**：R000 已建好那 15 个页面（`/review` 与 `/agent/eval` 除外，它们各自等对应需求——复盘与回归评测——再建；现在建出来只有空壳，且会让导航出现点进去没东西的入口）。

## 1. 目标目录结构

```
web/
├── src/app/
│   ├── layout.tsx                  根布局：主题、Toaster、功能开关 Provider
│   ├── page.tsx                    落地页（保留现有动效）
│   ├── (auth)/login|register/      登录 / 注册
│   ├── (dashboard)/                受保护区域（middleware 校验会话）
│   │   ├── checkin/                小岛（打卡 + 连续性 + 3D 岛）
│   │   ├── dashboard/              主页统计
│   │   ├── plans/                  列表 / new / [id] / [id]/studio
│   │   ├── docs/                   列表 / [id] / knowledge/[sourceName]
│   │   ├── review/                 ★ 新增：题库复盘 + 简历复盘（两个标签页）
│   │   ├── statistics/             三视图统计
│   │   └── profile/                个人资料
│   ├── agent/                      教练总览（时间线 / 审批 / 成本）
│   │   └── eval/                   ★ 新增：回归面板
│   └── api/
│       ├── auth/[...all]/          Better Auth（**唯一保留的 Next 路由**）
│       └── service-token/          签发给 service 的短期 JWT（httpOnly cookie）
├── src/components/                 见 §4
├── src/lib/
│   ├── api.ts                      ★ apiFetch / apiFetchPage / ApiError / streamSSE
│   ├── use-api.ts                  ★ useApi 数据钩子（loading/error/data/refresh）
│   ├── auth-client.ts              Better Auth 客户端
│   ├── error-messages.ts           ★ 错误码 → 中文文案与行为
│   └── ui/                         格式化（时间、时长、分数）、常量
└── next.config.ts                  本地开发把 /api/v1/* rewrite 到 service
```

**新增的只有 4 个文件 + 2 个页面**：`api.ts`、`use-api.ts`、`error-messages.ts`、`service-token/route.ts`，加 `/review`、`/agent/eval` 两个页面。其余从参考工程搬运。

## 2. 路由表

| 路径 | 渲染 | 数据来源（service） | 登录 |
|---|---|---|---|
| `/` | 静态 + 客户端动效 | `GET /meta`（功能开关） | 否 |
| `/login` `/register` | 客户端表单 | Better Auth（`server-token` 由认证路由内部调） | 否 |
| `/checkin` | 客户端 | `POST /checkins`、`GET /checkins`、`GET /study/*`（打卡与统计） | 是 |
| `/dashboard` | 客户端 | `GET /stats/overview`、`GET /checkins` | 是 |
| `/plans` | 客户端 | `GET /plans` | 是 |
| `/plans/new` | 客户端表单 | `POST /plans`（P1） | 是 |
| `/plans/[id]` | 客户端 | `GET /plans/{id}`、`GET /plans/{id}/tasks`、`PATCH /tasks/{id}` | 是 |
| `/plans/[id]/studio` | 客户端 | 同上 + `POST /plans/{id}/generate`（P1，草案进审批） | 是 |
| `/docs` | 客户端 | `GET /knowledge/documents`、`POST /knowledge/documents` | 是 |
| `/docs/[id]` | 客户端 | 资料 CRUD（`document` 表对应接口） | 是 |
| `/docs/knowledge/[sourceName]` | 客户端 | `GET /knowledge/documents`（按 `source_name`） | 是 |
| `/review` ★ | 客户端 | `GET /quiz/topics`、`POST /quiz/sessions`、`POST /quiz/sessions/{id}/answers`（SSE）、`GET /quiz/sessions/{id}`、`POST /resume`、`GET /resume/projects`、`POST /resume/sessions*` | 是 |
| `/agent` | 客户端 | `GET /runs`、`GET /runs/{id}`、`POST /runs/{id}/approvals/{aid}/decide`、`GET /usage`、`GET /notifications` | 是 |
| `/agent/eval` ★ | 客户端 | `GET/POST /eval/fixtures`、`POST /eval/runs`、`GET /eval/runs/{id}`（P1） | 是 |
| `/statistics` | 客户端 | `GET /stats/overview`、`GET /stats/review`、`GET /stats/agent-quality` | 是 |
| `/profile` | 客户端 | 认证接口（改密码/头像）+ `POST /uploads/presign` | 是 |

**为什么默认客户端取数**：service 是独立服务，页面首屏若走服务端渲染就得在 web 服务端再造一条"带凭据调 service"的路径（两跳、两份超时与错误处理）。现有代码本来就是客户端 `fetch`（实测 `agent-workspace.tsx`、`docs-client.tsx`、`studio-client.tsx` 等都是），保持它，改造量最小且只有一条数据通路。**例外**：登录态与功能开关（`/meta`）在根布局里拿，避免每个页面各取一次。

## 3. 每页职责与五种状态

状态一律按 **初始 / 触发 / 成功 / 失败 / 空** 五态写清楚，做到时逐条对照（PRD 3.11 R008 要求"每个视图都有数据态与空态，空数据不画空坐标轴"）。

### 3.1 认证：`/login`、`/register`

| 态 | 行为 |
|---|---|
| 初始 | 登录表单（邮箱 + 密码）；已登录访问 → 直接跳 `/dashboard` |
| 触发 | 提交 → 按钮进入 pending，禁用重复提交；成功后调 `/api/service-token` 拿 service JWT |
| 成功 | 跳 `returnTo`（默认 `/dashboard`） |
| 失败 | `VALIDATION_FAILED` → 字段级红字；凭据错 → 表单顶部"邮箱或密码不对" |
| 空 | —（表单页无空态） |

### 3.2 小岛：`/checkin`

| 态 | 行为 |
|---|---|
| 初始 | 今天已打卡 → 显示记录卡 + 连续天数；未打卡 → 显示表单（内容 / 时长 / 主题下拉 / 心情 / 截图） |
| 触发 | 提交打卡 → 乐观更新连续天数；截图先 `POST /uploads/presign` 再直传 OSS 回填 key |
| 成功 | toast"已记录"+ 热力图与连续天数刷新；主题下拉的值与题库主题同源 |
| 失败 | 校验错 → 字段红字；`UPSTREAM_FAILED`（OSS）→"图片上传失败，可先不传图" |
| 空 | 首次使用：显示引导文案（不是空白热力图），3D 岛维持现有空岛状态 |

### 3.3 计划：`/plans`、`/plans/new`、`/plans/[id]`、`/plans/[id]/studio`

| 态 | 行为 |
|---|---|
| 初始 | 列表显示计划卡（进度环 + 任务统计）；详情显示任务分组（按天/周） |
| 触发 | 勾选任务 → `PATCH /tasks/{id}`（乐观更新，失败回滚）；点"生成任务" → 拿 `run_id` 跳 `/agent` |
| 成功 | 任务状态即时反映；生成任务后提示"草案已进入审批，去智能体页确认" |
| 失败 | `NOT_FOUND` → 404 卡；`CONFLICT`（计划已归档）→ 提示后刷新 |
| 空 | 无计划 → "还没有计划，点这里创建一个"；计划无任务 → "导入计划文档后自动拆分" |

### 3.4 资料：`/docs`、`/docs/[id]`、`/docs/knowledge/[sourceName]`

| 态 | 行为 |
|---|---|
| 初始 | 列表按 `source_type` 分组（笔记 / 面经 / 题库） |
| 触发 | 拖拽上传 → `POST /knowledge/documents`（含 `source_name`、`source_type`）；导入中显示进度与"清洗中" |
| 成功 | 显示"抽题 N 道、重复跳过 M 道、警告若干"（对应接口返回的 `warnings`） |
| 失败 | `VALIDATION_FAILED` → 文件类型/大小提示；`CONFLICT` → "同名资料正在导入"；`UPSTREAM_FAILED` → "向量化服务不可用，稍后重试" |
| 空 | 无资料 → 引导卡片（示例题目集格式说明）；主题下无题 → "该主题还没有题目，先导入" |

### 3.5 复盘（新增）：`/review`

| 态 | 行为 |
|---|---|
| 初始 | 两个标签页：**题库**（主题卡：题目数 / 待复习 / 平均分）、**简历**（项目卡：层级覆盖 / 上次复盘 / 弱项数） |
| 触发 | 选主题/项目开一轮 → 问答卡片逐题作答；`Accept: text/event-stream` 拿流式反馈（首字 ≤ 2 秒） |
| 成功 | 每题展示四维评分 + 证据句；本轮结束展示总结 + 弱项清单；补强任务提示"今晚巡检会带进审批" |
| 失败 | 流式中断 → 保留已显示内容并标"评分未完成，可重试本题"；`QUOTA_EXCEEDED` → 横幅"今日 AI 额度用完，明天再来" |
| 空 | 未导入题库/简历 → 引导到 `/docs` 导入；无可复习题 → "这轮没有到期的题，7 天后会重现" |

### 3.6 智能体：`/agent`、`/agent/eval`

| 态 | 行为 |
|---|---|
| 初始 | 若已有 run：显示最新那次的分析与"待你确认"审批卡；成本面板显示近 7 天 |
| 触发 | 批准/拒绝（拒绝必填理由）→ `POST /runs/{id}/approvals/{aid}/decide`，必须带 `Idempotency-Key`；手动触发巡检 → `POST /cron/daily`（仅本地调试入口，生产隐藏） |
| 成功 | 审批卡变为"已执行：已创建任务《…》"并给任务链接；`CONFLICT` → "这条建议已经处理过了"并刷新 |
| 失败 | 执行失败 → 卡片标红给可读原因；`UPSTREAM_FAILED` → "模型暂时不可用，已按规则给出建议" |
| 空 | 没有 run → "今晚 21:00 自动巡检"；没有待审批 → "今天没有需要你确认的建议" |
| `/agent/eval` | 初始：fixture 列表 + 基线指标；触发：选 suite 跑对比；成功：五项对比表 + 逐条 diff；失败：标"退化"并高亮原因；空："从历史 run 固化第一条样本" |

### 3.7 统计与个人：`/statistics`、`/profile`、`/`

| 页 | 五态要点 |
|---|---|
| `/statistics` | 初始：近 7 天概览（时长/复盘次数/弱项存量/采纳率/成本）；触发：切 7/30/全天 + 点弱项看证据；成功：图表与列表刷新；失败：保留上次数据 + 重试；空："还没有复盘数据，先完成一次题库复盘"（**不画空坐标轴**）；弱项可"标记已纠正" |
| `/profile` | 初始：资料卡 + 主题；成功：保存后即时生效；失败：字段红字；空：无头像显示默认 |
| `/` | 落地页，未登录时展示价值主张；已登录时按钮变"进入自习室"；`features.chatroom=false` 时不渲染聊天入口 |

## 4. 组件复用清单

参考工程共 86 个组件文件，按目录核对（实测）：

| 目录 | 文件数 | 处置 |
|---|---|---|
| `ui/` | 22 | **原样搬**（base-ui + shadcn 生成的原子组件） |
| `landing/` | 13 | **原样搬**（落地页动效；只去掉聊天室入口） |
| `focus-room/` | 5 | **原样搬**（打卡主界面） |
| `island/` | 1 | **原样搬**（3D 岛，保留不动） |
| `layout/` | 5 | **改造**：`top-nav.tsx` 去掉 `<ChatRoom />` 与聊天入口；新增"复盘""智能体"入口 |
| `agent/` | 7 | **改造**：`agent-workspace` / `coach-overview` / `decision-timeline` / `notification-center` 的 `fetch` 改走 `apiFetch`；新增审批卡与成本面板；`knowledge-base` 的导入改走 `/knowledge/documents` |
| `plans/` | 7 | **改造**：数据请求改走 `apiFetch`，其余交互保留 |
| `studio/` | 7 | **改造**：同上（文档工作室） |
| `profile/` | 4 | **改造**：头像上传改走 `POST /uploads/presign` |
| `settings/` | 3 | **改造**：主题/偏好保留，去掉与 Prisma 相关的部分 |
| `dashboard/` | 2 | **改造**：数据源改为 `/stats/overview` |
| `statistics/` | 1 | **改造**：接三个 stats 接口 |
| `auth/` | 1 | **改造**：接 Better Auth 客户端与 `service-token` |
| `onboarding/` | 2 | 保留（driver.js 引导），文案与入口同步更新 |
| `calendar/` | 1 | 原样搬 |
| `ai/` | 3 | **改造**：保留问答 UI，数据源改 service；流式改为读 service 的 SSE（不再用 `@ai-sdk/react`） |
| `chatroom/` | 1 | **不搬**（ADR-002） |
| **新增** | — | `review/answer-card.tsx`（问答+评分，题库与简历共用）、`review/score-card.tsx`、`agent/approval-card.tsx`、`agent/cost-panel.tsx`、`eval/fixture-table.tsx`、`eval/diff-table.tsx` |

**共用组件约定**：问答与评分卡两个标签页共用（PRD 2.5）；图表继续用现有自绘组件（**不引图表库**）；Markdown 渲染沿用 `react-markdown` + `rehype-sanitize`（用户内容必须过 sanitize）。

## 5. 登录与令牌传递

```
浏览器 ──登录──► /api/auth/*（Better Auth，写在 web）
                     │ 会话有效时
                     ▼
        /api/service-token（web 侧签发短期 JWT，写 httpOnly cookie）
                     │
浏览器 ──/api/v1/*──► nginx ──► service（验签取 user_id，不访问认证表）
```

- **两个 cookie**：Better Auth 的会话 cookie（页面与 `/api/auth/*` 用）与 `summer_service_jwt`（`/api/v1/*` 用）。后者 `httpOnly`、`SameSite=Lax`、有效期 15 分钟，页面加载时若缺失或剩余 < 5 分钟则静默续签。
- **为什么两个**：会话 cookie 是 Better Auth 的格式，service 不想理解它；JWT 只承载 `sub`（= `user.id`）与 `exp`，把"认证"和"业务鉴权"解耦。签发实现前先读 Better Auth 的 JWT 插件文档（`architecture.md` §3.1 已标注）。
- **受保护路由**：`(dashboard)/**` 与 `/agent/**` 由 `proxy.ts` 校验会话 cookie 存在，缺失 → 302 `/login?returnTo=<path>`。（Next 16 把 `middleware.ts` 改名为 `proxy.ts`，导出的函数也叫 `proxy`；构建时会把它重命名为 `middleware.js`，功能不变。）
- **CLI / CI**：用 `Authorization: Bearer <JWT>`（由 `/api/service-token` 换），service 优先读 header。
- **登出**：清会话 + 清 `summer_service_jwt`。
- **本地开发**：`next.config.ts` 里把 `/api/v1/:path*` rewrite 到 `SUMMER_SERVICE_URL`；生产环境由 nginx 分流，web 无需改配置。

## 6. 取数约定（`src/lib/api.ts`）

只有 4 个导出，页面与组件不得自己拼 `fetch`：

```ts
export class ApiError extends Error {
  constructor(readonly code: string, message: string,
              readonly status: number, readonly requestId?: string,
              readonly details?: { field: string; issue: string }[]) { super(message); }
}

// 解包 {data}；失败抛 ApiError。自动带 cookie；GET 遇 UPSTREAM_FAILED 退避重试 1 次
export async function apiFetch<T>(path: string, init?: RequestInit & { idempotencyKey?: string }): Promise<T>;
export async function apiFetchPage<T>(path: string): Promise<{ data: T[]; meta: { nextCursor: string | null } }>;
// 读 SSE：meta → delta → result → done
export async function streamSSE(path: string, body: unknown, on: { meta?, delta?, result?, done? }): Promise<void>;
```

配套 `useApi<T>(path, deps)`：返回 `{ data, error, loading, refresh }`，**不引 swr/react-query**（现有工程也没有），保持"简约易上手"。

**写操作规则**：
- 审批接口必须带 `idempotencyKey`（`crypto.randomUUID()`，同一个审批卡重试复用同一个 key）。
- 写操作**不自动重试**（幂等由 service 的业务键保证），失败按 §7 提示。
- 乐观更新只用于低风险动作（勾选任务、标记已读），失败回滚并 toast。

## 7. 错误码映射（`src/lib/error-messages.ts`）

| code | 用户文案 | 行为 |
|---|---|---|
| `AUTH_REQUIRED` | 登录已过期，请重新登录 | 清 service cookie → 跳 `/login?returnTo=…` |
| `FORBIDDEN` | 没有权限做这件事 | toast |
| `NOT_FOUND` | 内容不存在或已被删除 | 404 卡或退回列表 |
| `VALIDATION_FAILED` | 按 `details` 显示字段级文案 | 表单字段红字；无 `details` 时顶部提示 |
| `CONFLICT` | 这件事已经处理过了 | toast + 自动刷新当前数据 |
| `RATE_LIMITED` | 操作太频繁，请稍后再试 | 按钮禁用 5 秒 |
| `QUOTA_EXCEEDED` | 今日 AI 额度已用完 | 页面横幅提示，巡检仍会给规则建议 |
| `UPSTREAM_FAILED` | 模型或存储暂时不可用 | 显示可点的"重试"；不自动无限重试 |
| `INTERNAL` | 出错了，请稍后再试 | 附 `requestId`（可复制，便于排查） |

默认兜底文案由 `error-messages.ts` 一处维护，页面不写自己的错误文案。

## 8. 依赖变化（`web/package.json`）

| 移除 | 原因 |
|---|---|
| `@prisma/client`、`@prisma/adapter-pg`、`prisma`、`pg` | schema 归 Alembic，web 不连库 |
| `@ai-sdk/openai`、`ai`、`openai`、`@ai-sdk/react` | LLM 调用与流式都在 service；前端读自定义 SSE |
| `ali-oss` | 预签名归 service |
| `ws` | 聊天室不迁移（ADR-002） |
| `proxy-agent` | 只服务服务端模型调用 |

保留：`better-auth`、`next`、`react`、`tailwindcss`、`@base-ui/react`、`sonner`、`react-hook-form` + `zod`（表单校验）、`react-markdown` 全家桶、`three` + `@react-three/*`（3D 岛）、`gsap`、`motion`、`driver.js`、`date-fns`、图标库、`react-timer-hook`。

## 9. 文案与体验约定

- 空态必须给"下一步动作"，不是一句"暂无数据"（例：无题目 → "先导入题目集"）。
- **禁用话术**（PRD R003 验收）：不说"你必须"、"再不学就完了"；不制造焦虑。
- 加载用骨架屏（`ui/skeleton`），不用整页 spinner。
- 错误文案统一从 §7 取；技术细节（堆栈、SQL）绝不出现在页面上。
- 可访问性最低要求：可键盘操作、焦点可见、按钮有 `aria-label`、颜色对比度达标；只支持桌面 Chrome / Edge / Safari 最新两个版本（PRD 3.10），**不做移动端**。

## 10. 迁移销项表（R000 起逐页勾选）

| 页面 | 已改为调 `/api/v1/*` | 无控制台报错 | 空态 | 备注 |
|---|---|---|---|---|
| `/`、`/login`、`/register` | ☑ | ☑ | — | 认证先通，其余页面才可用 |
| `/checkin` | ☑ | ☑ | ☑ | R000 无写接口，表单禁用并说明原因；主题下拉等 R004 |
| `/dashboard`、`/statistics` | ☑ | ☑ | ☑ | 已接 `/stats/overview`、`/checkins`（R000 返回零值/空数组） |
| `/plans`、`/plans/new`、`/plans/[id]`、`/plans/[id]/studio` | ☑ | ☑ | ☑ | 列表已接 `/plans`；详情与工作室待对应接口 |
| `/docs`、`/docs/[id]`、`/docs/knowledge/[sourceName]` | ☑ | ☑ | ☑ | 导入改 service（待 `POST /knowledge/documents`） |
| `/agent` | ☑ | ☑ | ☑ | 已接 `/runs`；审批卡等 R001 |
| `/agent/eval` | — | — | — | **R000 不建此页**（等回归评测需求） |
| `/review` | — | — | — | **R000 不建此页**（等复盘需求） |
| `/profile` | ☑ | ☑ | — | 已接 `/meta` 与 `/notifications`；头像改 service 预签名 |

**完成判据**（R000 验收）：`web/` 内 `grep -r "prisma" src/` 为空；
`grep -rl 'fetch("/api/' src/` 只命中 `lib/api.ts` 与 `lib/service-token.ts`（令牌与登出的出口）。

---

**变更记录**

| 日期 | 变更 |
|---|---|
| 2026-09-25 | 首版：17 个路由表、五态逐页、组件复用清单、令牌传递、fetcher 与错误码映射、依赖增删、迁移销项表 |
| 2026-09-27 | R000 落地：`middleware.ts` → `proxy.ts`（Next 16 改名）、销项表勾选 15 个页面并标注 `/review` 与 `/agent/eval` 不建的理由 |
