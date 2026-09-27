# 设计：清理 .trellis/spec/（删除模板 + 保留 guides + 包级 spec 推迟）

> 配套 `prd.md`（需求与验收）。本文只回答"怎么改"，不重复需求。

## 1. 目标形态

```
.trellis/spec/
├── README.md                          ← 重写：结构树 + 真实技术栈 + 说明包级 spec 为何缺席
└── guides/                            ← 保留目录，按真实链路重写内容
    ├── index.md                       图层图改为 web → nginx → service → DB；rg 改 grep
    ├── cross-layer-thinking-guide.md  跨层数据流按真实三层重写
    └── pre-implementation-checklist.md 检查项改为本项目（接口走 docs/tech/api/ 5 步等）
```

**4 个文件取代 35 个。** 删除 31 个：

| 目录 | 数量 | 处置 |
|---|---|---|
| `backend/` | 10 | 全删（`orpc-usage.md`、`database.md`(Drizzle)、`authentication.md`(drizzleAdapter) 等） |
| `frontend/` | 12 | 全删（`orpc-usage.md`、`hooks.md`(React Query)、`api-integration.md`(oRPC) 等） |
| `shared/` | 4 | 全删（`dependencies.md` 列 drizzle-orm、`typescript.md` 讲 oRPC 类型推导） |
| `big-question/` | 5 | 全删（Postgres JSON/JSONB、Sentry、Turbopack、WebKit —— 与本项目无关） |

## 2. 为什么保留 `guides/` 而不是全删

全删（35 个）看似更干净，但有两处硬依赖会断：

| 依赖点 | 原文 | 全删后的后果 |
|---|---|---|
| `trellis-before-dev` 步骤 6 | "**Always read shared guides**: `cat .trellis/spec/guides/index.md`"，SKILL.md 末行标注 "This step is **mandatory** before writing any code" | 每次写代码前都报 "Cannot find path"。R000 要写大量代码，正是该步骤调用最频繁的时候 |
| `trellis-update-spec`（Phase 3.3） | 以 `.trellis/spec/` 为写入目标 | 无处可写，Phase 3.3 失去落点 |

保留 `guides/` 的关键理由是**它不含任何关于"代码长什么样"的断言**：它是跨层数据流与动手前检查项的
思考工具，骨架与栈无关，只有示例需要换成本项目链路。所以重写它**不产生虚构** —— 它描述的是
`docs/tech/architecture.md` 已定的三层契约，有事实来源。这与 `web/ui`、`web/data` 的性质完全不同：
后两者要断言"目录怎么放、hook 怎么写"，而 `web/` 目录还不存在。

## 3. 被否方案

| 方案 | 为什么否 |
|---|---|
| **35 个全删，R000 后从零建 spec** | 最彻底，但断掉上面两处硬依赖（before-dev 步骤 6、Phase 3.3），且 R000 期间每次写代码前都撞一次缺失报错。保留 guides 的成本极低（3 个文件），收益是两条流程不中断。 |
| **按原计划全重写（含 `web/ui`、`web/data`）** | 用户已否。`web/` 零代码时写出的规约无法指向真实文件，只能靠断言；即使标注 `[待证]`，本质仍是虚构 —— 而这正是本任务要清除的问题。 |
| **只删 `backend/`，保留 `frontend/`（因为 web 要搬 master）** | `frontend/` 12 个文件同样全是 oRPC / React Query / Radix / Next 15 模板内容，实测 `@tanstack` 与 `@radix-ui` 在真实项目命中 **0** 次。留着会诱导引入不存在的依赖。 |
| **保留 `big-question/` 目录名，只换内容** | `big-question` 在 monorepo 模式下是根级目录，声明 `packages` 后不再被扫描（`packages_context.py:36`），会变成孤儿（文件在、永远读不到）。且实测 5 个真实的坑**全在 service 侧**，放 web guides 是张冠李戴。随 R000 的 `spec/service/` 迁入。 |
| **现在声明 `packages` 并建空的 `spec/web`、`spec/service` 目录** | 空目录会让 `--mode packages` 显示 "Spec layers: (空)"，且空目录不进 git（git 不跟踪空目录），实际等于没建。不如老实显示 "Spec: not configured"。 |
| **把 `docs/tech/` 的契约抄进 guides** | 违反 `docs/README.md` §3"单一事实来源"。guides 只写**编码视角**，契约细节指向 `docs/tech/`。 |
| **顺手改 `.trellis/tasks/00-bootstrap-guidelines/`** | 它的前提（扫描已有代码填充 spec）在零代码时不成立，但那是独立的一件事。混进本任务会让回滚点变模糊。 |

## 4. `packages` 配置的连带影响（已核实）

`.trellis/config.yaml` 增加：

```yaml
packages:
  web:
    path: web
  service:
    path: service
```

**不设 `default_package`**：早期任务多为跨两端（R000 同时动 web 与 service），设默认值会让
`resolve_package()` 把任务误判为单包（`config.py:507-546`）。留空即"未指定"，语义更准。

连带影响（`packages_context.py` 实测行为）：

1. `--mode packages` 输出从 `Single-repo project (no packages configured)` 变为 `## PACKAGES` + 两个包。
2. 两包都没有 spec 目录 → 均显示 `Spec: not configured`。**预期输出**，验收标准已写明。
3. 根级 spec 层（`backend`/`frontend`/`shared`/`big-question`）不再被扫描 —— 必须随本任务删除，否则成孤儿。
4. `task.py create --package web|service` 变得可用；`validate_package()` 开始校验包名（`config.py:495-504`）。
5. `guides/` 不受影响：它在 `packages_context.py:204-208` 单独作为 "Shared Guides (always included)" 输出。

## 5. 两个相似标题的区别（容易踩的坑）

实测字符串计数：

| 字符串 | 命中 | 说明 |
|---|---|---|
| `Pre-Development Checklist` | **0** | `trellis-before-dev:29` 要找的就是这个 |
| `Pre-Implementation Checklist` | 7 | 模板自己的一套命名，**匹配不上** |
| `Quality Check` | 3（全为正文链接文字 "Quality Checklist"） | `trellis-check:31` 要找的标题形式不存在 |
| `Pre-commit Checklist` | 5 | `backend/quality.md` / `frontend/quality.md` 的标题，**匹配不上** |

即现状是"**差一个词**"式的失效：看起来有 checklist，实际两个入口都命中不了。
本任务**不修这个**（那属于 `<package>/<layer>/index.md`，随 R000 的包级 spec 一起做），
但要在 `guides/` 里避免继续使用 `Pre-Implementation Checklist` 这个容易混淆的名字 ——
`cross-layer-thinking-guide.md:20` 的该小节改名为 `## 动手前检查项`，避免与入口标题混淆。

## 6. 验证方式

```powershell
cd D:\workspacePy\Agent\summer-checkin

# 1. 四个目录已删，只剩 4 个文件
Get-ChildItem .trellis\spec -Recurse -File | Select-Object -ExpandProperty FullName

# 2. 错栈清零
grep -ri "orpc\|drizzle\|prisma" .trellis/spec/

# 3. 模板栈不再作为推荐出现
grep -ri "next.js 15\|turborepo\|pnpm\|sentry\|radix\|react-query\|@tanstack" .trellis/spec/

# 4. 包与 guides 被正确识别（预期两包均 not configured）
python ./.trellis/scripts/get_context.py --mode packages

# 5. guides 可读（Phase 2 步骤 6 的硬命令）
Get-Content .trellis\spec\guides\index.md -Encoding utf8 | Select-Object -First 20

# 6. 本机无 rg，guides 里不应再有 rg 命令
grep -rn "rg " .trellis/spec/guides/
```

第 4 步的预期输出：

```
## PACKAGES

### web
Path: web
Spec: not configured

### service
Path: service
Spec: not configured

### Shared Guides (always included)
Path: .trellis/spec/guides/index.md
```

## 7. 回滚

纯文档改动，无代码依赖。回滚 = `git checkout .trellis/spec .trellis/config.yaml`。

**前置**：仓库当前是 unborn HEAD（`git rev-parse --verify HEAD` 失败），**没有 HEAD 可回滚** ——
删掉的 31 个文件若未提交将无法恢复。`implement.md` 的卡点 0 要求先做基线提交。
