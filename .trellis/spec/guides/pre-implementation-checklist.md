# 动手前检查清单

> **用途**：写代码之前花 5 分钟过一遍，省下 50 分钟调试。
>
> 这份清单针对本项目的真实链路：`web(Next.js) → nginx → service(FastAPI) → PostgreSQL`。

---

## 为什么需要这份清单

不是能力问题，是**没想到**：

- 没想到同一个常量在别处已经定义过 → 两份定义漂移
- 没想到这个接口其实已经有了 → 接口膨胀
- 没想到改的是跨层契约 → 前端悄悄崩掉
- 没想到要写空态和失败态 → 线上白屏

---

## 检查清单

### 1. 常量与配置

- [ ] **先搜索再新增**：这个常量/配置是不是已经存在？
  ```bash
  grep -rn "MAX_UPLOAD_SIZE" web/src/ service/app/
  ```
- [ ] **放在正确的层**：前端展示用的放 `web/src/lib/ui/`；业务阈值放 service；
      跨需求的阈值（如检索阈值、去重阈值）只在 `docs/tech/integrations.md` §3.3 定义一处
- [ ] **环境变量前缀对**：service 用 `SUMMER_`，web 沿用 `BETTER_AUTH_*` / `DATABASE_URL` / `OSS_*`
      （见 `docs/tech/integrations.md` §5）
- [ ] **密钥不进代码、不进日志**

### 2. 逻辑与模式

- [ ] **这段逻辑该住哪一层？** 业务规则住 service 服务层，不在路由层、不在组件里
- [ ] **有没有现成的？** 先看 `service/app/services/` 的既有函数
- [ ] **是不是重复了？** 见过类似的代码就抽出来
- [ ] **事务边界对吗？** 写多张表必须在一个事务里
- [ ] **幂等想了吗？** 见 `docs/tech/architecture.md` §7.2
- [ ] **并发想了吗？** 两个标签页同时点批准会怎样？（审批靠状态机条件更新）

### 3. 类型与 Schema

- [ ] **出入参都有 schema**：service 侧 Pydantic，web 侧表单校验用 zod ^4.4 + react-hook-form
- [ ] **接口契约先改文档**：改任何接口前，先改 `docs/tech/api/`，再改两端
- [ ] **没有 `any`**：web 侧不写 `any`，service 侧不写裸 `dict`
- [ ] **错误码用约定的枚举**：`AUTH_REQUIRED` / `FORBIDDEN` / `NOT_FOUND` /
      `VALIDATION_FAILED` / `CONFLICT` / `RATE_LIMITED` / `QUOTA_EXCEEDED` /
      `UPSTREAM_FAILED` / `INTERNAL`（`docs/tech/architecture.md` §7.1）
- [ ] **不要重复定义后端类型**：接口返回的类型从契约来，不要在前端手抄一份

### 4. UI 组件

- [ ] **服务端 / 客户端边界对吗？** 需要交互与状态才加 `'use client'`
- [ ] **能复用已有的吗？** 见 `docs/tech/frontend.md` §4 的组件复用清单
- [ ] **五种状态都有了吗？** 初始 / 触发 / 成功 / 失败 / 空
      （每个页面的五态在 `docs/tech/frontend.md` §3 逐页写明）
- [ ] **空态不是白屏**：空数据要有引导文案，**不画空坐标轴**
- [ ] **文案规范**：不用惩罚式语气，失败要有可行动的下一步（`docs/tech/frontend.md` §9）
- [ ] **UI 库用 `@base-ui/react`**（**不要引入 Radix UI** —— 本项目不用，实测参考项目 0 处引用）

### 5. 接口

- [ ] **先查有没有现成的**：`docs/tech/api/` 有 39 个端点的清单
- [ ] **新增接口走 5 步**：见 `docs/tech/api/README.md` §9
- [ ] **路径前缀 `/api/v1/`**：否则 nginx 会把它交给 web，线上 404
- [ ] **web 侧只经 `src/lib/api.ts`**：不允许组件里直接 `fetch("/api/v1/...")`，
      更不允许直连数据库
- [ ] **鉴权方式对**：三种调用方（浏览器 cookie JWT / CLI Bearer / cron secret）
- [ ] **分页用游标**：`nextCursor`，默认 20、最大 100
- [ ] **不在 `web/src/app/api/` 加业务接口**：那里只留 better-auth 与 `service-token`

### 6. 依赖

- [ ] **真的需要新依赖吗？** 能不能用已有的
- [ ] **不要引入这些**（Trellis 模板里出现过但本项目不用，实测 0 处引用）：
  - **oRPC** —— 从未使用；web 用 `fetch` 调 REST
  - **Drizzle / Prisma** —— Prisma 已退场，schema 归 Alembic；Drizzle 从未使用
  - **React Query / `@tanstack/react-query`** —— 用自写的 `useApi`
  - **Radix UI** —— 用 `@base-ui/react`
  - **Turborepo / pnpm workspaces** —— 单仓两目录，不用 workspace 工具
  - **Vercel AI SDK** —— service 是 Python，LLM 调用在 Python 侧
- [ ] **版本对齐 `docs/tech/architecture.md` §1**：Next 16.2.10 / React 19.2.4 /
      Tailwind v4 / Better Auth 1.6.23 / Python 3.12 / SQLAlchemy 2.0

---

## 快速决策树

```
要改动什么？
│
├── 一个常量 / 配置值
│   └─ 先 grep 全仓 → 存在就复用 → 不存在再按层放
│
├── 新逻辑
│   ├─ 是业务规则？ → service/app/services/（不在路由层、不在组件里）
│   └─ 是展示逻辑？ → web/src/lib/ui/
│
├── 一个类型 / schema
│   ├─ 跨进程契约？ → 先改 docs/tech/api/，service 侧 Pydantic，web 侧从契约来
│   └─ 仅前端内部？ → web/src/lib/ 或组件旁
│
├── 一个组件 / hook
│   ├─ 需要交互？ → 'use client' + useApi
│   └─ 纯展示？ → 服务端组件
│
└── 一个接口
    ├─ 已有类似的？ → 复用（先查 docs/tech/api/）
    └─ 确实要新增 → 走 docs/tech/api/README.md §9 的 5 步
```

---

## 要跨层验证什么

| 层边界 | 验证什么 |
|---|---|
| 页面 / `api.ts` | 五种状态齐全；错误码都有对应文案 |
| `api.ts` / nginx | 路径前缀 `/api/v1/`；凭据带上；本地与线上的差别 |
| nginx / service | 调用方类型；超时与限额；`X-Request-Id` 透传 |
| service 路由 / 服务层 | 路由保持薄；事务边界；幂等 |
| 服务层 / DB | UTC；`user_id` 过滤；schema 只走 Alembic |
| web / better-auth | 只在 web 侧；service 只验签、不碰认证表 |

---

## 反模式

### 在组件里直接 fetch

```typescript
// 错：绕过了统一取数出口，错误处理与凭据传递都要重写一遍
const res = await fetch("/api/v1/checkins");

// 对：走 apiFetch，信封与 ApiError 统一处理
const data = await apiFetch<Checkin>("/checkins");
```

### 在前端重复定义后端类型

```typescript
// 错：手抄一份，契约一变就漂移
type Checkin = { id: string; date: string; hours: number; /* 抄漏了字段 */ };

// 对：契约以 docs/tech/api/ 为准，类型跟着接口定义走
```

### 把业务逻辑写进路由层

```python
# 错：路由层直接写业务与事务
@router.post("/checkins")
async def create_checkin(body: CheckinIn, db: AsyncSession = Depends(get_db)):
    ...  # 校验、业务规则、写多张表全塞这里

# 对：路由薄，业务在服务层
@router.post("/checkins")
async def create_checkin(body: CheckinIn, user=Depends(current_user), db=...):
    return await checkin_service.create(db, user.id, body)
```

### 不必要地使用客户端组件

纯展示的组件不需要 `'use client'`；加上去会白送一份 JS 到浏览器。

### 只在本地直连端口验证

本地开发用 rewrite 直连 service，线上走 nginx。**本地通不代表线上通** ——
路径分流、超时、`X-Request-Id` 透传都只有过 nginx 才验证到。

### 手改数据库

schema 由 Alembic 唯一拥有。手改表会让模型与迁移漂移，`alembic check` 会报错。
改结构 = 写迁移 + 改模型 + 两者一致。

---

## 什么时候用这份清单

| 情况 | 用哪份 |
|---|---|
| 就要动手写一个功能 | 这份 |
| 改动跨 3 层以上 | 先看[跨层思考指南](./cross-layer-thinking-guide.md) |
| 改动超过一个文件 | 在任务的 `design.md` 里写下变更边界（见下） |
| 只是改个文案 | 不用，直接改 |

### 非平凡改动要先写下变更边界

Trellis 的 `trellis-before-dev` 要求：改动超过一个文件、跨层、改公开接口、或改别人写的代码时，
先写清楚：

- 现在是什么行为、应该变成什么行为（**最小行为差异**）
- 这个行为**实际住在哪一层**（不是"哪里最容易改"）
- 预计改哪些文件，每个为什么必要
- **明确不做什么**
- 如果做了局部重构，怎么证明行为没变

---

## 与其他指南的关系

- [跨层思考指南](./cross-layer-thinking-guide.md) —— 数据怎么流、在哪变形、谁负责
- `docs/tech/architecture.md` —— 服务边界、认证、数据所有权、硬规则（**动代码前必读**）
- `docs/tech/api/README.md` §9 —— 新增一个接口的 5 步
- `docs/README.md` §3 —— 文档维护规则与冲突优先级

**契约的唯一事实来源是 `docs/tech/`**，本目录只讲"怎么想、怎么查"，不复制契约内容。

---

## 经验教训

修完非平凡 bug 后，把教训补到这里（症状 → 原因 → 怎么避免）：

| 症状 | 原因 | 怎么避免 |
|---|---|---|
| 线上 404，本地正常 | 漏了 `/api/v1/` 前缀 | 一律走 `apiFetch` |
| 时间差 8 小时 | 中途按本地时区处理 | 存 UTC，展示再转 |
| 页面白屏 | 只写了成功态 | 五种状态齐全 |
| 越权读数据 | 查询漏了 `user_id` | 所有业务查询按用户隔离 |
| 迁移漂移 | 手改了表 | 只走 Alembic，`alembic check` 无漂移 |
| `npm run check` 全绿但 `next build` 失败 | typecheck 与 lint 看不见构建期的预渲染约束 | 交付前**两个都跑**（R000 实测：`useSearchParams` 缺 Suspense、reactCompiler 缺 babel 插件都只有构建能抓到） |
| `alembic` 报 `UnicodeDecodeError` | `alembic.ini` 里有非 ASCII 字符，被按系统 locale 解码 | `alembic.ini` 只写 ASCII |
| `alembic check` 报漂移但代码没改 | 表达式索引（`desc("col")`）反射不回来 | 用普通 btree |
| 测试在导入期报配置校验失败 | 环境变量设在了 `Settings` 实例化之后 | 在任何 app 导入之前设好 |

### 验证命令

改动完成后按项目实际方式验证：

```bash
# web 侧（web/ 目录下）
npm run check        # = typecheck + lint + test（vitest）
npm run build        # 构建期问题只有它能抓到（用占位环境变量即可）

# service 侧（service/ 目录下）
uv run ruff check .
uv run pytest        # 不需要数据库

# 数据基线（service/ 目录下，离线，不需要连库）
SUMMER_DATABASE_URL="postgresql+asyncpg://ci:ci@localhost:5432/summer_checkin_test" \
  uv run alembic upgrade head --sql | grep -c "CREATE TABLE"   # 期望 32

# 真库（需要 SUMMER_DATABASE_URL 指向 _test 库）
uv run alembic upgrade head && uv run alembic check
```

**验证 ≠ 确认**：跑过才算验证；"看了代码觉得应该没问题"只是确认。
