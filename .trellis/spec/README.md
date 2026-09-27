# 项目开发规约（.trellis/spec/）

> 本目录存放**编码视角**的规约：怎么分层、禁止什么、跑什么命令验证。
>
> **契约的唯一事实来源是 `docs/tech/`** —— 数据模型、接口定义、架构边界、第三方集成都在那里。
> 本目录不复制契约内容，只写"写代码时要注意什么"，需要细节时指向 `docs/tech/`。

---

## 当前结构

```
.trellis/spec/
├── README.md（本文）
├── guides/                            与栈无关的思考工具，每次动代码前必读
│   ├── index.md                       导航 + 本项目分层图 + 改动前搜索习惯
│   ├── cross-layer-thinking-guide.md  数据怎么流、在哪变形、谁负责
│   └── pre-implementation-checklist.md 动手前检查项 + 反模式
├── service/index.md                   FastAPI 侧：分层、迁移纪律、三条硬规则
└── web/index.md                       Next.js 侧：取数出口、认证链路、路由守卫
```

**6 个文件。**

---

## 包级规约的建立与维护

`spec/service/index.md` 与 `spec/web/index.md` 于 R000（双服务骨架）后建立，
内容全部来自真实代码与实测结论，不含模板占位。

两个 `index.md` 都含两个**逐字一致**的入口标题（`trellis-before-dev` 与 `trellis-check`
按字符串匹配找它们）：

- `## Pre-Development Checklist`
- `## Quality Check`

> 注意：模板原先的 `Pre-Implementation Checklist` / `Pre-commit Checklist` 命名**匹配不上**，
> 是新旧模板不一致导致的失效入口；上面这两个名字不要改。

后续需求（R001 起）把新的坑按层补进对应文件；跨需求契约一旦变化，回写 `docs/tech/`，不要留在 spec 里。

---

## 在那之前，编码规约以 `docs/tech/` 为准

| 要查什么 | 去哪 |
|---|---|
| 服务边界、认证链路、数据所有权、目录结构、硬规则 | `docs/tech/architecture.md`（**动代码前必读**） |
| 统一响应与错误码、幂等、分页、日志与追踪、时间与版本 | `docs/tech/architecture.md` §7 |
| 31 张表的字段、关系、索引、迁移策略 | `docs/tech/data-model/` |
| 39 个端点的出入参、鉴权、分页、限流；新增接口的 5 步 | `docs/tech/api/` |
| service 模块划分、函数清单、agent 运行时、事务与幂等 | `docs/tech/backend.md` |
| 页面路由、逐页五种状态、组件复用、令牌传递、错误码映射 | `docs/tech/frontend.md` |
| 模型池、embedding 与 pgvector、OSS、环境变量、Compose、CI/CD | `docs/tech/integrations.md` |
| 每条技术决策的背景、被否方案、代价 | `docs/tech/decisions/` |

**冲突优先级**：`docs/tech/`（现状契约） > 任务 `.trellis/tasks/*/design.md`（本任务方案） >
`docs/PRD.md`（需求摘要）。发现不一致就当场改，不留"以后统一"。

---

## 本项目的技术栈（当前版本）

与 `docs/tech/architecture.md` §1 保持一致：

| 侧 | 技术 |
|---|---|
| **web** | Next.js 16.2.10、React 19.2.4、Tailwind v4、`@base-ui/react` 1.6、Better Auth 1.6.23、zod ^4.4、react-hook-form ^7.81 |
| **service** | FastAPI、Python 3.12、SQLAlchemy 2.0（async）、Alembic、Pydantic v2、APScheduler、ruff、pytest |
| **数据** | PostgreSQL 16 + pgvector（`vector(1024)` + HNSW） |
| **部署** | Docker Compose（web / service / db / nginx 四容器）+ nginx 路径分流 |

### 明确不使用的（模板里出现过，实测 0 处引用）

引入这些依赖是本项目最容易犯的错：

| 不使用 | 为什么 | 用什么代替 |
|---|---|---|
| **oRPC** | 从未使用 | web 用 `fetch` 调 REST（`src/lib/api.ts`） |
| **Prisma** | 已退场 | SQLAlchemy 模型 + Alembic 迁移 |
| **Drizzle ORM** | 从未使用 | 同上 |
| **React Query / `@tanstack/react-query`** | 从未使用 | 自写 `useApi` hook |
| **Radix UI** | 从未使用 | `@base-ui/react` |
| **Turborepo / pnpm workspaces** | 单仓两目录 | 直接两个目录 |
| **Vercel AI SDK** | service 是 Python | Python 侧 LLM 调用 |

---

## 语言约定

本目录与 `docs/` 一致，**用中文书写**。代码与标识符用英文。

---

## 维护

- 修完非平凡 bug 后，把教训补进
  `guides/pre-implementation-checklist.md` 的"经验教训"表（症状 → 原因 → 怎么避免）。
- 本项目特有的坑按层归位到 `service/index.md` 或 `web/index.md` 的"常见错误"表。
  service 侧已核实的参考实现缺陷记录在 `docs/tech/backend.md` §3.4（审批未生效、决策状态自相矛盾）
  与 `docs/tech/integrations.md` §3（embedding 维度、rerank 端点）。
- 跨需求契约一旦变化，回写 `docs/tech/`，不要留在 spec 里。
