# 技术文档索引

> 技术文档回答"怎么做"。五个不可缺少的部分：**数据模型、API 设计、架构/流程图、第三方集成、技术决策**。
> 完整性检验标准：**PRD 里每个业务实体都能在数据模型里找到对应，每个功能点都能在 API 里找到对应接口**（见下方追溯表）。

## 1. 阅读顺序

```
tech/README.md（本文，先看追溯表知道自己要动的部分牵涉哪些文档）
  → architecture.md   服务边界、认证、数据所有权、目录、硬规则   ← 任何代码之前必读
  → data-model/       我要改的数据长什么样（schema 归 service）
  → api/              我要写/调的接口长什么样（全部由 service 提供）
  → backend.md        后端（service）逻辑该写在哪个模块
  → frontend.md       前端（web）页面与组件该怎么组织
  → integrations.md   外部依赖、环境变量、限额、部署
  → decisions/        为什么是这样，改它要付什么代价
```

**先记住两条**：① 业务数据与业务接口都归 `service/`（FastAPI），`web/` 只做页面与登录；② 数据库 schema 由 Alembic 唯一拥有，Prisma 已退场。

## 2. 各文档边界（避免内容重叠）

| 文档 | 写什么 | 不写什么 |
|---|---|---|
| `architecture.md` | 服务边界与判据、认证链路、数据所有权、目录、硬规则、关键流程、部署拓扑、跨领域约定 | 具体表字段、具体接口出入参 |
| `data-model/` | **31 张表**按域分 6 册的全部字段、类型、索引、关系、向量、Alembic 迁移与保留策略；命名与主键规范 | 接口行为、页面表现 |
| `api/` | 接口总则（鉴权/响应与错误码/幂等/分页/流式/限流）与 39 个端点的出入参；P0 全 schema、P1 只写职责 | 表结构细节、页面布局 |
| `backend.md` | service 的模块划分、函数签名、事务与幂等、agent 运行时、错误与日志 | 接口清单（在 `api/`）、页面 |
| `frontend.md` | web 的路由表、页面职责与交互状态、组件复用、登录与令牌、文案规范 | 后端实现、表结构 |
| `integrations.md` | 模型池（档位链/配额/成本口径）、embedding 与 pgvector 链路、OSS 预签名、环境变量与密钥、Compose 与 CI/CD、灰度与回滚 | 业务逻辑 |
| `decisions/` | 每条决策的背景/选择/被否方案/代价，一经记录不改写 | 实现细节 |

## 3. PRD ↔ 技术文档追溯表

> 检验用：PRD 的每个需求，必须在这里找齐"数据 → 接口 → 页面 → 验收"四列，缺一列说明技术方案没想全。
> **归属**：接口列全部由 `service/`（FastAPI）提供；页面列全部在 `web/`（Next.js）。

| 需求 | 数据模型 | 接口（service） | 页面（web） | 验收 / 测试 |
|---|---|---|---|---|
| R000 工程骨架 | Alembic 从零建 31 张表 | `GET /healthz`、`GET /meta` | 15 个页面与登录跑通，一条真实链路调通 | 两端 `check` 全绿；`docker compose up` 起全栈；`/api/v1/meta` 返回统一结构 |
| R001 审批边界 | `agentapproval`、`agentdecision`、`plantask` | `POST /runs/{id}/approvals/{aid}/decide` | 智能体页审批卡 | 未审批时 `plantask` 无新增行 |
| R002 幂等 | `agentapproval.status`、`agenttoolcall.idempotency_key` | 同上 + `Idempotency-Key` 头 | — | 并发两次审批只执行一次 |
| R003 每日建议 | `agentrun`（+`model`/`prompt_version`）、`agentstep` | `POST /cron/daily`（或 APScheduler） | 通知铃 + 智能体页时间线 | 抽样 20 条建议 100% 含 `reason` |
| R004 题库复盘 | `knowledgedoc`、`documentchunk`、`conversation`、`conversationmessage`、`usermemory` | `GET /quiz/topics`、`POST /quiz/sessions`、`POST /quiz/sessions/{id}/answers` | 复盘页 · 题库标签 | 一次 5 题复盘全链路 |
| R005 题库导入清洗 | 同上 | `POST /knowledge/documents` | 阅读页 · 题库 | 清洗 5 步 + 去重生效 |
| R006 简历复盘 | `knowledgedoc`、`conversation*`、`usermemory`、`agentrun` | `POST /resume`、`GET /resume/projects`、`POST /resume/sessions*` | 复盘页 · 简历标签 | 4 维评分均带证据 |
| R007 弱项档案 | `usermemory` | `GET /memories`、`POST /memories/{id}/resolve` | 统计页 · 弱项 | 标记已纠正后曲线同步变化 |
| R008 统计面板 | 聚合查询（无新表） | `GET /stats/review`、`GET /stats/agent-quality` | 主页统计 | 三视图各有数据态与空态 |
| R009 成本账本 | `tokenusage`（+`run_id`）、`agentstep` | `GET /usage` | 智能体页 · 成本与延迟 | 页面数值与 `tokenusage` 求和对齐 |
| R010 回归面板 | **新增** `evalfixture`、`evalrun`、`evalresult` | `GET/POST /eval/fixtures`、`POST /eval/runs` | `/agent/eval` | 引入退化时 CI 失败 |
| R011 部署上线 | — | — | — | 公网 HTTPS 可访问；nginx 路径分流正确 |
| R012 演示材料 | — | — | — | 60 秒演示脚本可跑完 |

## 4. 已定事项（原未决问题）

| # | 事项 | 决定 | 依据 |
|---|---|---|---|
| 1 | 数据库来源 | **空地新建**：不接管任何已有库（旧 ECS 环境已不可用），Alembic 初始迁移从零建 31 张表；本地与服务端都用容器里的 PostgreSQL 16 + pgvector | 没有历史数据要保，基线可以一次做干净 |
| 2 | OSS 预签名归属 | **搬到 service**：密钥只留在后端服务；题库/资料这类小文件直接 POST 给 service 解析入库，不绕 OSS | 与"web 只做页面与认证"一致 |
| 3 | 回归面板 `eval` 跑在哪 | **service 内的 CLI + CI 调用**：本地可复现，CI 用它做门禁 | 回归的价值在于"随时能重跑" |
| 4 | 本地开发与部署形态 | **Docker 从 R000 起就要能跑**：`docker-compose.yml` 四容器（web / service / db / nginx）用于部署，`docker-compose.dev.yml` 只起 db、两端本地热重载 | 部署形态必须和开发形态一致 |
| 5 | 成本口径 | `tokenusage` 只记 tokens；成本在**聚合时**按单价表估算（改价不追溯历史）；当前主要跑在各模型独立的免费额度上，超限自动降级到规则建议 | 估算不等于账单，对外表述必须区分 |
| 6 | 调度位置 | APScheduler 跑在 service 进程内，因此 `uvicorn --workers 1`；要扩并发时再把调度拆成独立容器并用 advisory lock 防重 | 多 worker 会重复触发巡检 |
| 7 | 发布与回滚纪律 | 迁移**单独**执行不隐式跑；镜像按 sha 保留（不用 `latest` 回滚）；默认不 downgrade，写正向修复迁移 | 单机 compose，回滚要能一分钟内做掉 |

## 5. 与 PRD 的同步点

- PRD 里已有的技术性内容（2.4 分层与数据结构、3.7 数据模型、3.8 接口清单、3.9 默认值）保留为摘要，详细定义以本目录为准；发现不一致时以本目录为准并回改 PRD 摘要。
- 产品层面变化记在 PRD 的"更新记录"；技术层面变化记在各文档末尾的"变更记录"。
