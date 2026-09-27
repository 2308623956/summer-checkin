<!-- TRELLIS:START -->
# Trellis Instructions

These instructions are for AI assistants working in this project.

This project is managed by Trellis. The working knowledge you need lives under `.trellis/`:

- `.trellis/workflow.md` — development phases, when to create tasks, skill routing
- `.trellis/spec/` — package- and layer-scoped coding guidelines (read before writing code in a given layer)
- `.trellis/workspace/` — per-developer journals and session traces
- `.trellis/tasks/` — active and archived tasks (PRDs, research, jsonl context)

If a Trellis command is available on your platform (e.g. `/trellis:finish-work`, `/trellis:continue`), prefer it over manual steps. Not every platform exposes every command.

If you're using Codex or another agent-capable tool, additional project-scoped helpers may live in:
- `.agents/skills/` — reusable Trellis skills
- `.codex/agents/` — optional custom subagents

Managed by Trellis. Edits outside this block are preserved; edits inside may be overwritten by a future `trellis update`.

<!-- TRELLIS:END -->

## 文档优先级

`docs/tech/`（现状契约） > 本任务 `.trellis/tasks/*/design.md`（本任务方案） > `docs/PRD.md`（需求摘要）。

三者冲突时以 `docs/tech/` 为准，并当场回改 PRD 的摘要。任务里定下的东西一旦成为跨需求契约，回写 `docs/tech/`。

## 任务入口

`docs/PRD.md` 只写到**需求级**（用户、功能范围、验收、排期）。每个需求开一个 Trellis 任务继续讨论，形成真正的 `prd.md` / `design.md` / `implement.md`：

    python ./.trellis/scripts/task.py create "<需求标题>" --slug <name> --priority P0 --meta req=R00X

- `prd.md` — 本任务的需求、约束、验收标准（不写技术设计）；
- `design.md` — 技术选型、被否方案与理由、数据流、降级与回滚；
- `implement.md` — 有序执行清单、校验命令、评审卡点；
- **不复制 `docs/tech/` 的内容**，只写本任务的增量与指向。

需求范围有变时改 `docs/PRD.md`；任务的分工、命名、归档与 PRD 无关，不要去改 PRD。

## 需求溯源

`task.json` 的 `meta.req` 存需求 ID（如 `R000`）。读 PRD 时按这个 ID 检索，命中三处：

    grep -n "R000" docs/PRD.md

1.6（需求表：描述、初步拆解、优先级）、3.x（功能详述）、3.11（验收标准）。

需求 ID 是唯一的锚点——任务的目录名带创建日期前缀，不含需求编号，不要从目录名反推需求。
工程基建类任务没有对应需求，用 `--meta kind=<tooling|docs>` 代替 `req`。

