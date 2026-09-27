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
└── guides/                            与栈无关的思考工具，每次动代码前必读
    ├── index.md                       导航 + 本项目分层图 + 改动前搜索习惯
    ├── cross-layer-thinking-guide.md  数据怎么流、在哪变形、谁负责
    └── pre-implementation-checklist.md 动手前检查项 + 反模式
```

**4 个文件。** 包级规约（`spec/web/`、`spec/service/`）**尚未建立**，原因见下。

---

## 为什么没有 `spec/web/` 与 `spec/service/`

Trellis 的包级 spec（`spec/<package>/<layer>/index.md`）要回答"这个包的代码该怎么写"。
本项目此刻**还没有任何实现代码** —— `web/` 与 `service/` 目录都不存在。

在零代码的情况下写包级 spec，写出来的每条规则都无法指向真实文件，只能靠断言。
`trellis-spec-bootstrap` 的完成标准明确要求 spec "describes the project as it exists now"。
所以：

| 包 | spec 状态 | 什么时候建 |
|---|---|---|
| `web`（Next.js 页面与认证） | 未建 | R000 完成后，按真实代码建立 |
| `service`（FastAPI 领域服务） | 未建 | 同上 |

建立时按 `trellis-spec-bootstrap` 做，并确保每个 `index.md` 含两个**逐字一致**的入口标题
（`trellis-before-dev` 与 `trellis-check` 按字符串匹配找它们）：

- `## Pre-Development Checklist`
- `## Quality Check`

> 注意：模板原先的 `Pre-Implementation Checklist` / `Pre-commit Checklist` 命名**匹配不上**，
> 是新旧模板不一致导致的失效入口，建立新 spec 时不要再沿用。

---

## 在那之前，编码规约以 `docs/tech/` 为准

| 要查什么 | 去哪 |
|---|---|
| 服务边界、认证链路、数据所有权、目录结构、硬规则 | `docs/tech/architecture.md`（**动代码前必读**） |
| 统一响应与错误码、幂等、分页、日志与追踪、时间与版本 | `docs/tech/architecture.md` §7 |
| 30 张表的字段、关系、索引、迁移策略 | `docs/tech/data-model/` |
| 39 个端点的出入参、鉴权、分页、限流；新增接口的 5 步 | `docs/tech/api/` |
| service 模块划分、函数清单、agent 运行时、事务与幂等 | `docs/tech/backend.md` |
| 17 个路由、逐页五种状态、组件复用、令牌传递、错误码映射 | `docs/tech/frontend.md` |
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
- 本项目特有的坑，等 `spec/web/`、`spec/service/` 建立后按层归位。
  当前已核实的 service 侧缺陷记录在 `docs/tech/backend.md` §3.4（审批未生效、决策状态自相矛盾）
  与 `docs/tech/integrations.md` §3（embedding 维度、rerank 端点）。
- 跨需求契约一旦变化，回写 `docs/tech/`，不要留在 spec 里。
