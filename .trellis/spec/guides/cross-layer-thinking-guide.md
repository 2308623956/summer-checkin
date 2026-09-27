# 跨层思考指南

> **用途**：一次改动跨过多层时，先把"数据怎么流、在哪变形、谁负责"想清楚。
>
> 本项目只有一条数据通路，但它穿过**两个进程**（Next.js 与 FastAPI）和**一个反向代理**（nginx），
> 每一段都是独立的失效点。

---

## 什么时候用这份指南

- [ ] 改动跨 3 层以上（页面 → `api.ts` → nginx → service 路由 → 服务层 → DB）
- [ ] 数据格式在层之间发生变化
- [ ] 多个消费方需要同一份数据
- [ ] 不确定某段逻辑该放哪一层
- [ ] 要接外部服务或第三方 API

---

## 动手前检查项

### 1. 识别涉及哪些层

| 层 | 位置 | 职责 |
|---|---|---|
| 页面 / 组件 | `web/src/app/`、`web/src/components/` | 渲染与交互。**不直连数据库** |
| 取数出口 | `web/src/lib/api.ts` | `apiFetch` / `apiFetchPage` / `streamSSE`。**唯一取数出口** |
| 认证 | `web/src/app/api/auth/`、`service-token/route.ts` | better-auth + 签发 15 分钟 JWT |
| 反向代理 | `infra/nginx/*.conf` | 路径分流：`/` 与 `/api/auth/*` → web；`/api/v1/*` → service |
| 接口层 | `service/app/api/v1/` | 薄：解析 → 校验 → 鉴权 → 调服务层 |
| 服务层 | `service/app/services/` | 业务逻辑与事务。**唯一允许写业务数据的地方** |
| 数据层 | `service/app/models/`、`alembic/` | SQLAlchemy 模型；schema 由 Alembic 唯一拥有 |

### 2. 数据流方向

```
读：DB → service 服务层 → service 路由（Pydantic 序列化）
        → nginx → fetch(api.ts) → useApi hook → 组件 → UI

写：UI → 表单校验 → apiFetch → nginx → service 路由（Pydantic 校验）
        → 服务层（事务）→ DB → 统一信封返回 → UI 更新
```

### 3. 每层的格式

| 层 | 数据形态 | 注意 |
|---|---|---|
| PostgreSQL | `timestamptz`（UTC）、`vector(1024)`、`jsonb` | 时间统一存 UTC |
| SQLAlchemy 模型 | Python `datetime` / `list[float]` / `dict` | |
| Pydantic schema | 校验后的对象 | 出入参都以 `docs/tech/api/` 为准 |
| JSON over HTTP | ISO 8601 字符串 | **跨进程只有 JSON** |
| `apiFetch` | 解析信封后的对象 | 成功 `{data}`；失败抛 `ApiError` |
| React 组件 | props / state | 不使用 React Query（本项目不引入） |
| UI | 渲染结果 | Tailwind v4 + `@base-ui/react` |

### 3.1 两个序列化边界（关键）

**本项目有两个序列化边界，不是一个**：

1. **service ↔ web**（跨进程）：只有 JSON 能过。`datetime` 必须序列化成 ISO 字符串，
   `vector` 不出现在接口里，`Decimal` 转数字。
2. **web 服务端 ↔ web 客户端**（Next.js RSC 边界）：只有可序列化的值能过。

| 可序列化（安全） | 不可序列化（会炸） |
|---|---|
| `string` / `number` / `boolean` / `null` | `Date` 对象 |
| 普通对象、数组 | `Map` / `Set` |
| `undefined`（作为缺省） | 函数、类实例 |
| | `BigInt` / `Symbol` |

**常见的坑**：service 返回 ISO 字符串，前端某处 `new Date(...)` 之后直接当 props 传给客户端组件——
`Date` 对象不过 RSC 边界。要在服务端显式转回字符串。

### 4. 数据在哪些点变形

**格式在哪变？谁负责？**

| 从 | 到 | 由谁转换 | 位置 |
|---|---|---|---|
| DB `timestamptz` | Python `datetime`（UTC） | SQLAlchemy | 自动 |
| Python `datetime` | ISO 字符串 | Pydantic 序列化 | service 路由返回 |
| ISO 字符串 | 展示字符串 | 格式化函数 | `web/src/lib/ui/` |
| 用户输入 | 校验后的数据 | Pydantic | service 路由入口 |
| 用户输入（前端） | 表单状态 | zod / react-hook-form | 组件内 |
| 错误码 | 中文文案 | 映射表 | `web/src/lib/error-messages.ts` |

**前端校验与后端校验都要有**：前端为了体验，后端为了正确。不要因为前端校验了就省掉后端。

### 5. 边界提问（重要）

**页面 / `api.ts` 边界：**

- 这个请求走 `apiFetch` 了吗？（**不允许组件里直接 `fetch("/api/v1/...")`**）
- 失败态想清楚了吗？`ApiError.code` 的每个分支对应什么 UI？
- 空数据与加载中分别显示什么？（本项目要求每个页面有五种状态）

**`api.ts` / nginx 边界：**

- 路径前缀是 `/api/v1/` 吗？（否则 nginx 会把它交给 web，404）
- 需要带凭据吗？（默认带 httpOnly cookie 里的短期 JWT）
- 本地开发与线上的差别：本地用 `next.config.ts` 的 rewrite 直连 service，
  线上走 nginx。**不要只在本地验证就当作线上通过**。

**nginx / service 边界：**

- 这个接口的三种调用方想清楚了吗？（浏览器 cookie JWT / CLI Bearer / cron secret）
- 超时与限额是多少？（见 `docs/tech/api/README.md` §8）

**service 路由 / 服务层边界：**

- 路由层保持"薄"了吗？（解析、校验、鉴权、调用，不写业务逻辑）
- 事务边界在哪？写多张表时必须在一个事务里
- 幂等怎么做？（见 `docs/tech/architecture.md` §7.2：审批靠状态机条件更新，
  工具执行靠 `idempotency_key` 唯一约束）

**服务层 / DB 边界：**

- 时间存的是 UTC 吗？
- 查询带 `user_id` 过滤了吗？（**所有业务查询都必须按用户隔离**）
- schema 变更走 Alembic 了吗？（**不允许手改表**）

### 6. 认证上下文

- web 侧：better-auth 管会话，**只存在于 web**
- service 侧：只验签，**不碰认证表**（`user` / `session` / `account` 属于 web 的 better-auth）
- 跨进程传递：web 签发 15 分钟短期 JWT，service 用公钥验签
- 每个请求带 `X-Request-Id`，nginx → service 透传，响应与日志都带

**常见错误**：在 service 里想当然地去查 `session` 表；或者在 web 的页面里直接读业务表。
两者都违反 `docs/tech/architecture.md` §2 的服务边界。

### 7. 边缘情况

- [ ] 空数据（`data: []`）时页面显示什么？**不画空坐标轴**
- [ ] service 挂了 / 超时了，页面显示什么？
- [ ] 用户未登录 / JWT 过期（15 分钟）时怎么处理？
- [ ] 同一操作重复提交会怎样？（幂等）
- [ ] LLM 不可用时（额度耗尽 / 超时）降级到什么？
- [ ] 时间跨时区怎么办？（存 UTC，展示按本地）

---

## 本项目的真实模式

### 模式 A：客户端取数（默认方式）

页面是客户端组件，经 `useApi` 调 `apiFetch`：

```typescript
// 组件内
const { data, loading, error, refresh } = useApi(() => apiFetchPage<Checkin>("/checkins"));

if (loading) return <Skeleton />;
if (error) return <ErrorState code={error.code} />;   // 文案由 error-messages.ts 映射
if (!data?.length) return <EmptyState />;             // 空态，不是白屏
return <List items={data} />;
```

**为什么默认客户端取数**：service 是独立服务，页面首屏若走 SSR 就得在 web 服务端再造一条
"带凭据调 service"的路径（两跳、两份超时与错误处理）。例外是登录态与功能开关（`/meta`），
在根布局里拿，避免每页各取一次。

### 模式 B：流式（SSE）

复盘评分这类长任务用 SSE，页面消费增量：

```typescript
await streamSSE("/quiz/sessions/123/answers", body, {
  onDelta: (t) => append(t),
  onResult: (r) => setScore(r),
  onError: (e) => showError(e),
});
```

**注意**：SSE 的失败发生在流的中间，`onError` 必须能处理"已经渲染了一半"的状态。

### 模式 C：写操作 + 刷新

写接口返回统一信封，成功后刷新相关数据或做乐观更新：

```typescript
try {
  await apiFetch("/checkins", { method: "POST", body });
  refresh();
} catch (e) {
  if (e instanceof ApiError && e.code === "VALIDATION_FAILED") {
    setFieldError(e.message);   // 不清空表单
  }
}
```

### 模式 D：认证路由（web 独有的 Next API）

`/api/auth/[...all]` 与 `/api/service-token` 是**唯一保留的 Next 路由**。
其余业务接口全部在 service。新增业务接口时不要往 `web/src/app/api/` 里加。

### 模式 E：cron / CLI 调用 service

定时巡检走 `POST /api/v1/cron/daily`，用 cron secret 鉴权；
回归面板的 eval 由 service 内的 CLI + CI 触发。这两种调用方没有浏览器 cookie。

---

## 常见 bug 的经验教训

| 症状 | 原因 | 怎么避免 |
|---|---|---|
| 线上 404，本地正常 | 忘了 `/api/v1/` 前缀，请求被 nginx 交给 web | 路径一律走 `apiFetch`，不要手拼 |
| 时间差 8 小时 | 某一层按本地时区处理了 | 存 UTC，展示再转；不要中途转 |
| 页面白屏 | 只写了成功态 | 五种状态都要有（初始/触发/成功/失败/空） |
| 越权读到别人的数据 | 查询没带 `user_id` 过滤 | 所有业务查询按用户隔离 |
| 接口改字段后前端崩 | 契约改动没同步 | 改接口先改 `docs/tech/api/`，再改两边 |
| 迁移与模型不一致 | 手改了表或漏了迁移 | schema 只由 Alembic 改，`alembic check` 必须无漂移 |
| JWT 过期后请求全挂 | 15 分钟有效期没做刷新 | 401 走重新签发路径 |

**契约的唯一事实来源是 `docs/tech/`**。发现代码与文档不一致时，以"文档先改、代码跟进"为准
（`docs/README.md` §3）。

---

## 检查清单模板

跨层改动可以照这个写进任务的 `design.md`：

```
## 改动：<名称>

### 涉及的层
- [ ] 页面 / 组件
- [ ] api.ts
- [ ] nginx（是否需要改分流？）
- [ ] service 路由
- [ ] service 服务层
- [ ] DB / 迁移

### 数据流
（写清楚从哪到哪，经过哪些层）

### 每层的格式
（列表：层 → 格式）

### 变形点
（谁负责转换，在哪转换）

### 鉴权
（哪种调用方，怎么带凭据）

### 边缘情况
- [ ] 空态
- [ ] 失败态
- [ ] 未登录 / JWT 过期
- [ ] 重复提交
- [ ] 降级路径
```

---

## 跨层评审的心态

### 对比陷阱

看到"另一处是这么写的"就照抄。**先确认那一处是对的**——参考项目 `summer-checkin-master/`
里有已知缺陷（审批未生效、决策状态自相矛盾），照抄会把 bug 带过来。

### 数据出口检查

每一份数据都要问：**它从哪来？到哪去？中途谁改了它？**

### 评审三问

1. 这个改动的**最小行为差异**是什么？（不是"改了哪些文件"）
2. 这个行为**实际住在哪一层**？（不是"哪里最好改"）
3. 我**没有**做什么？（明确划出边界）

### 验证 vs 确认

- **验证**：我自己跑一遍，它确实按预期工作
- **确认**：我看了代码，觉得它应该工作

验收标准要的是前者。`ruff check` + `pytest` / `npm run check` 跑过才算。

---

## 出问题时

1. 先定位**是哪一层的边界**失效（不是"哪个文件有 bug"）
2. 用 `X-Request-Id` 串起 nginx 与 service 的日志
3. 检查契约：`docs/tech/api/` 与实际返回是否一致
4. 修完把教训写回本指南的"经验教训"表
