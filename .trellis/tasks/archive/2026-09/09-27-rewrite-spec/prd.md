# 清理 .trellis/spec/：删除模板、保留 guides、包级 spec 推迟到 R000

> 状态：规划完成，待评审后 `task.py start` ｜ 对应需求：无（工程基建，非 R00X）｜ 依赖：无
> 配套：`design.md`（结构与取舍）、`implement.md`（顺序与验证命令）

## Goal

`trellis init` 装进来的 `.trellis/spec/` 是通用的 **Next.js + oRPC + Drizzle + Prisma + better-auth** 模板，
与本项目真实技术栈（`docs/tech/architecture.md`：web = Next.js 页面与认证，service = FastAPI + SQLAlchemy +
Alembic）不符。实测 **356 处** oRPC / Drizzle / Prisma 命中，遍布全部 5 个目录。

`trellis-before-dev`（步骤 4）与 `trellis-check`（第 2.2 步）会在写代码前把这些文件当"项目规约"读进来。
留着它等于**每次开工先被灌一遍错误的技术选型**。

**本任务只做清理，不新建内容**：删掉 31 个错栈文件，保留并重写 `guides/` 3 个（与栈无关的思考工具）
和根 `README.md`。`spec/web/`、`spec/service/` 推迟到 R000 —— 那时有真实代码可作证据。

## 确认的事实（已核实，非假设）

| # | 事实 | 证据 |
|---|---|---|
| 1 | spec 共 35 个 md：根 `README.md` 1 + backend 10 / frontend 12 / shared 4 / big-question 5 / guides 3 | 分组统计 |
| 2 | oRPC / Drizzle / Prisma 命中 **356 处**，覆盖全部 5 个目录 | 全量 grep |
| 3 | **无任何文件以标题形式含 `Pre-Development Checklist`**（0 处命中） | 正则 `^#+.*Pre-Development Checklist` |
| 4 | **无任何文件以标题形式含 `Quality Check`**；3 处命中均为正文里的链接文字 "Quality Checklist" | 正则 + 逐条核对 |
| 5 | `guides/cross-layer-thinking-guide.md:20` 有一个 `## Pre-Implementation Checklist` —— 与 `trellis-before-dev` 要找的 `Pre-Development Checklist` **差一个词**，匹配不上 | 字符串逐一比对 |
| 6 | 5 个 `index.md`（backend / frontend / shared / big-question / guides）都不含上述两个入口标题 | 同 3、4 |
| 7 | 模板声称的栈：Next.js 15 + React 19 + oRPC + Drizzle + Turborepo + pnpm + Radix UI + Sentry | `spec/README.md:61-68` |
| 8 | **`web/` 与 `service/` 都还不存在**（零实现代码） | 路径检测为 False |
| 9 | 模板要求的三样在真实项目里**根本不用**：`useQuery`/`@tanstack` 命中 0 次、`@radix-ui` 命中 0 次；真实用 `@base-ui/react`（14 次）+ 自写 hook（`src/lib/use-todos.ts`） | 全量 grep + `summer-checkin-master/package.json` |
| 10 | 真实 web 侧依赖版本：Next 16.2.10 / React 19.2.4 / zod ^4.4.3 / react-hook-form ^7.81 / sonner ^2.0.7 / three ^0.185.1 | master `package.json` |
| 11 | **`.trellis/spec/` 被 `trellis update` 列为 "User data (preserved)"** | `trellis update --dry-run` 实测输出 |
| 12 | ⇒ 删除 spec 后 `trellis update` **不会**把模板补回来 | 同 11 |
| 13 | `config.yaml` 中**没有 `registry:` 段**，所以也没有"从上游刷新 spec"的通道 | 检查 config.yaml + `registry-config.js` |
| 14 | `docs/tech/` 已覆盖大量本该在 spec 的约定：目录结构、统一响应与错误码、幂等、分页、日志与追踪、时间与版本、新增接口 5 步、17 个路由与逐页五态 | `tech/architecture.md` §4/§7；`tech/api/README.md` §9；`tech/frontend.md` §1-§3 |
| 15 | monorepo 模式下 spec 层 = `spec/<package>/` 的**子目录**（`guides` 始终单独列出） | `common/packages_context.py:30-41, 204-208` |

## Requirements

1. **删除 31 个错栈文件**：`spec/backend/`（10）、`spec/frontend/`（12）、`spec/shared/`（4）、
   `spec/big-question/`（5，含其 `index.md`）。依据事实 11-13：删了就永久删除，不会回流。
2. **保留并重写 `spec/guides/` 3 个文件**：它是 Phase 2 步骤 6 的硬命令
   （`cat .trellis/spec/guides/index.md`，SKILL.md 标注 "This step is **mandatory** before writing any code"），
   且内容是与栈无关的思考工具 —— 只需把 oRPC / Drizzle / React Query / Next.js 15 的示例与图层图
   换成本项目真实链路（web → nginx → service → DB）。**重写它不产生任何虚构**，因为它描述的是
   `docs/tech/architecture.md` 已定的契约。
3. **保留并重写根 `spec/README.md`**：结构树改为实际文件集合（4 个），写真实技术栈，
   并明确说明 **`spec/web/` 与 `spec/service/` 为何缺席、何时补**，避免后来者以为漏了。
4. **不建 `spec/web/` 与 `spec/service/`**（本任务的 Non-Goal 核心）：零代码时写出来的规约无法指向真实文件，
   只能靠断言；`trellis-spec-bootstrap` 的 Done Criteria 要求 spec "describes the project as it exists now"。
   包级 spec 归入 R000 的交付物，用真实代码当证据。
5. **`.trellis/config.yaml` 声明 `packages: {web, service}`**：这是 `docs/tech/architecture.md` §4 已定的
   项目结构事实，同时让 `task.py --package web|service` 从 R000 起可用。
   两包此刻都没有 spec 目录 → `--mode packages` 显示 "Spec: not configured"，**这是准确状态，不是缺陷**。
6. **不把 `docs/tech/` 的契约抄进 spec 或 guides**：`docs/README.md` §3 规定"单一事实来源"。
   spec 只写**编码视角**（怎么分层、禁止什么、跑什么命令），契约细节一律指向 `docs/tech/`。
7. **修正 guides 里的失效命令**：`guides/index.md` 用了 `rg`，本机未安装（实测 `rg` 不存在，
   只有 `findstr` / `Select-String`）。改为 `grep`。

## Non-Goals

- **不建 `spec/web/`、`spec/service/`**（Requirement 4）。这是本任务最重要的边界。
- 不改 `docs/tech/`、`docs/PRD.md`（它们是本任务的输入与事实来源）。
- 不写实现代码，不创建 `web/` 与 `service/` 目录（属 R000）。
- 不改 `.trellis/workflow.md`；`.trellis/config.yaml` 只加 `packages`。
- 不新增 `guides/pitfalls.md`：已核实的 5 个真实的坑**全在 service 侧**，其完整论述已在
  `docs/tech/backend.md` §3.4、`docs/tech/integrations.md` §3 有了归属。现在写进 web 侧 guides 会张冠李戴；
  随 R000 的 `spec/service/` 一并迁入。
- 不追求"补齐两个入口标题"：那两个标题属于 `<package>/<layer>/index.md`，
  随包级 spec 一起推迟到 R000。

## Acceptance Criteria

- [ ] `spec/backend/`、`spec/frontend/`、`spec/shared/`、`spec/big-question/` 四个目录**已删除**。
- [ ] `.trellis/spec/` 下只剩 4 个文件：`README.md`、`guides/{index,cross-layer-thinking-guide,pre-implementation-checklist}.md`。
- [ ] `grep -ri "orpc\|drizzle\|prisma" .trellis/spec/` 无命中（或仅剩"已被否"的一句说明）。
- [ ] `grep -ri "next.js 15\|turborepo\|pnpm\|sentry\|radix\|react-query\|@tanstack" .trellis/spec/`
      只应出现在"本项目不使用"的语境里，不得作为推荐做法出现。
- [ ] `python ./.trellis/scripts/get_context.py --mode packages` 输出：`web` 与 `service` 两包
      （均显示 "Spec: not configured"）+ `### Shared Guides (always included)` 指向 `guides/index.md`。
- [ ] `cat .trellis/spec/guides/index.md` 可读，且图层图为 `web(Next.js) → nginx → service(FastAPI) → PostgreSQL`，
      不再是 `Server Component → oRPC → Drizzle`。
- [ ] `guides/index.md` 里不再有 `rg ` 命令（本机无 rg）。
- [ ] `spec/README.md` 的结构树与实际 4 个文件一致（无死链、无未列出的文件），
      且含一句明确说明"`web/`、`service/` 的 spec 在 R000 建立"。
- [ ] 无占位文本、空标题、复制来的与栈无关的样板。

## Notes

- **R000 期间的规约缺口由 `docs/tech/` 兜住**：`AGENTS.md`（托管块之外）已写明
  `docs/tech/` > 任务 `design.md` > `docs/PRD.md` 的优先级，并指向 `docs/tech/architecture.md` §4 目录、
  §7 统一响应与错误码/幂等/日志、`api/README.md` §9 新增接口 5 步。所以删掉 spec 内容不会让 R000 无规可依。
- 本任务不改 `.trellis/tasks/00-bootstrap-guidelines/`（仍是 `in_progress`）。它的前提是"扫描已有代码填充 spec"，
  零代码时不成立；本任务完成后应决定归档或改写它 —— 但那是一件事，不是这件事。
