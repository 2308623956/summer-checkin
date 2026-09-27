# 执行计划：清理 .trellis/spec/

> 配套 `prd.md`（需求/验收）与 `design.md`（结构与取舍）。本文只给顺序、命令与卡点。

## 卡点 0（前置，未完成不得删文件）

**仓库是 unborn HEAD —— 没有任何提交，删掉的 31 个文件将无法恢复。**

```powershell
cd D:\workspacePy\Agent\summer-checkin
git rev-parse --verify HEAD    # 预期失败：fatal: Needed a single revision
git status --porcelain         # 6 个顶层未跟踪项
```

先做基线提交：

```powershell
git add -A
git commit -m "chore: baseline docs and trellis setup before spec cleanup"
```

**连带效应（已确认，需接受）**：`.trellis/config.yaml` 的 `session_auto_commit` 默认 `true`，
但 `safe_commit` 在无 HEAD 时检测不到变更会提前返回。基线提交之后，`task.py archive` 与
`add_session.py` 就会真的自动提交（`chore(task): archive …` / `chore: record journal`）。
这是 Trellis 的设计行为。

**若坚持不提交**：跳过本节，但删掉的 31 个文件无法用 git 恢复，只能靠 npm 包里的模板副本手工还原。

## 步骤 1：删除四个错栈目录（31 个文件）

```powershell
cd D:\workspacePy\Agent\summer-checkin
Remove-Item -Recurse -Force .trellis\spec\backend, .trellis\spec\frontend, .trellis\spec\shared, .trellis\spec\big-question
```

验证只剩 `README.md` 与 `guides/`：

```powershell
Get-ChildItem .trellis\spec -Recurse -File | Select-Object -ExpandProperty FullName
```

## 步骤 2：声明 packages

`.trellis/config.yaml`，在 "Monorepo / Packages" 段（第 53-77 行）取消注释并写入：

```yaml
packages:
  web:
    path: web
  service:
    path: service
```

不设 `default_package`（理由见 `design.md` §4）。验证：

```powershell
python ./.trellis/scripts/get_context.py --mode packages
```

预期两包均显示 `Spec: not configured`（准确状态），并出现 `### Shared Guides (always included)`。

## 步骤 3：重写 `guides/index.md`

- 标题：`# Thinking Guides for Next.js Full-Stack Projects` → 本项目（去掉 Next.js 专属措辞）。
- `## Next.js-Specific Layers` → `## 本项目的图层`，图层图改为：

  ```
  web（Next.js 页面与认证）
        |  只经 /api/v1/*（src/lib/api.ts 是唯一取数出口）
        v
  nginx（路径分流：/ 与 /api/auth/* → web；/api/v1/* → service）
        |
        v
  service（FastAPI：业务逻辑的唯一所有者）
        |
        v
  PostgreSQL 16 + pgvector（Alembic 唯一拥有 schema）
  ```

- `## The Pre-Modification Rule` 里的 `rg` 命令改 `grep`（本机无 `rg`，实测）。
- `Available Thinking Guides` 表保留 2 个条目（本任务不新增 `pitfalls.md`，见 `prd.md` Non-Goals）。
- 末尾 `**Language**: All documentation must be written in **English**` 改为中文优先
  （本项目 spec 与 docs/ 均为中文）。

## 步骤 4：重写 `guides/cross-layer-thinking-guide.md`

保留骨架（分层识别 → 数据流方向 → 每层格式 → 转换点 → 边界问题 → 鉴权上下文 → 边缘 Case），
替换内容：

- `### 1. Layer Identification` 的层清单改为 `页面/组件 → fetch(api.ts) → nginx → service 路由 → service 服务层 → DB`。
- `### 3.1 Serialization Boundary` 保留（仍然适用：JSON over HTTP）。
- `## Common Patterns` 五个模式（Server Component Data Fetch / React Query / Optimistic / Server Action / Middleware）
  改为本项目的真实模式：**客户端 `useApi` 取数**（`docs/tech/frontend.md` §6）、
  **SSE 流式**（`streamSSE`，`frontend.md` §7）、**错误码分支**（`error-messages.ts`）。
- `## Pre-Implementation Checklist`（第 20 行）**改名为 `## 动手前检查项`** ——
  避免与 `trellis-before-dev` 要找的 `Pre-Development Checklist` 混淆（见 `design.md` §5）。
- 删掉 oRPC / Drizzle / React Query / Zod-on-oRPC 的示例代码。

## 步骤 5：重写 `guides/pre-implementation-checklist.md`

- `### 5. API Routes & oRPC Procedures` → `### 5. 接口`，内容改为：**新增/修改接口必须走
  `docs/tech/api/README.md` §9 的 5 步**；web 侧只允许经 `src/lib/api.ts` 调用，禁止直连数据库。
- `### 3. Types & Schemas` 删 oRPC 类型推导，保留 zod 用法（真实依赖 zod ^4.4.3，已核实）。
- 删 `### Manual Query Keys`（React Query 专属）与相关反模式。
- `## Quick Decision Tree` 的 oRPC 分支改 `/api/v1/*` 分支。
- 指向 `docs/tech/` 的具体章节而不是复制其内容。

## 步骤 6：重写根 `spec/README.md`

结构树改为实际 4 个文件；技术栈写真实值（Next 16.2.10 / React 19.2.4 / Tailwind v4 /
`@base-ui/react` 1.6 / Better Auth 1.6.23 / zod 4.4 / react-hook-form 7.81；service 侧
FastAPI + SQLAlchemy 2.0 + Alembic + Python 3.12）；**加一段明确说明**：

> `web/` 与 `service/` 的包级 spec（`spec/web/`、`spec/service/`）尚未建立 —— 它们需要真实代码作为依据，
> 将在 R000 完成后按 `trellis-spec-bootstrap` 建立。在那之前，编码规约以 `docs/tech/` 为准。

## 步骤 7：验证（`design.md` §6 的六条命令）

逐条对照 `prd.md` 的 Acceptance Criteria 勾选。重点确认：

```powershell
grep -ri "orpc\|drizzle\|prisma" .trellis/spec/          # 应为空
grep -rn "rg " .trellis/spec/guides/                     # 应为空（本机无 rg）
python ./.trellis/scripts/get_context.py --mode packages  # 两包 + Shared Guides
```

## 步骤 8：提交

```powershell
git add .trellis/spec .trellis/config.yaml
git commit -m "docs(spec): drop oRPC/Drizzle templates, keep rewritten guides"
```

## 回滚点

| 位置 | 回滚方式 |
|---|---|
| 卡点 0 之后 | `git checkout .trellis/spec .trellis/config.yaml`（回到基线） |
| 卡点 0 未做 | **无法用 git 回滚**；31 个文件的原始版本可从 npm 包 `@mindfoldhq/trellis` 的 `dist/templates/` 取回 |

## 完成后仍开放的事项（不在本任务内）

- `spec/web/`、`spec/service/` 未建 —— 归 R000 交付物（`prd.md` Requirement 4）。
- service 侧的 5 个真实的坑（审批不生效 `runtime.ts:786-788`、决策状态矛盾 `:811` vs `:808`、
  Observe 不读弱项、embedding 维度静默失效、rerank 端点 404）未写入 spec ——
  它们已在 `docs/tech/backend.md` §3.4 与 `docs/tech/integrations.md` §3 有完整论述，
  随 R000 的 `spec/service/` 迁入。
- `.trellis/tasks/00-bootstrap-guidelines/` 仍是 `in_progress`，前提不成立，待决定归档或改写。
