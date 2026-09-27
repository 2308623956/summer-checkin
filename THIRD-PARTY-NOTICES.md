# 第三方声明（Third-Party Notices）

本仓库是 **[gdut4140/summer-checkin](https://github.com/gdut4140/summer-checkin)** 的二次开发，
按其 MIT 许可证要求，此处保留原始版权声明。

---

## summer-checkin（原项目）

| 项 | 值 |
|---|---|
| 仓库 | https://github.com/gdut4140/summer-checkin |
| 在线演示 | http://8.163.59.196/ |
| 简介 | 一个 AI 驱动的自习室学习平台，用户 400+ |
| 许可证 | MIT |
| 版权 | Copyright (c) 2026 ruan-weibo |
| 本项目使用的快照 | 原项目 `master` 分支，以只读方式保留在仓库外的 `summer-checkin-master/`（**不随本仓库分发**） |

### 二次开发的范围

**继承的部分**（在原项目设计基础上继续）：

| 项 | 说明 |
|---|---|
| 数据模型 | 31 张表中的 **27 张沿用原项目的表名与字段语义**（如 `agentapproval`、`plantask`、`plantemplate`、`usermemory`、`tokenusage`），新增 `verification` 与 `evalfixture` / `evalrun` / `evalresult` 四张 |
| 页面路由 | 沿用原项目（`/checkin`、`/dashboard`、`/plans`、`/docs`、`/agent`、`/profile`、`/statistics`） |
| 功能设计 | 打卡字段语义、agent 的 Observe→Analyze→Plan→Execute 四步、审批与决策表结构 |

**重写的部分**（未复制原项目代码）：

| 项 | 原项目 | 本项目 |
|---|---|---|
| 后端 | Next.js API Routes（与页面同进程） | FastAPI 独立服务 |
| 数据访问 | Prisma ORM | SQLAlchemy 2.0 + Alembic |
| 认证 | Better Auth 会话直用 | BFF 短期 RS256 JWT |
| 聊天室 | WebSocket sidecar | 不迁移（ADR-002） |

本项目的 Python 与 TypeScript 代码均为重新编写，未移植原项目的组件、样式或路由处理器。

### 原始许可证（MIT，逐字保留）

```
MIT License

Copyright (c) 2026 ruan-weibo

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## 依赖项

本仓库的运行时与开发依赖（Next.js、React、FastAPI、SQLAlchemy、Alembic、pgvector 等）
各自遵循其自身许可证，未在此逐一罗列。需要完整清单时按语言查询：

```bash
cd web && npx license-checker --summary     # npm 依赖
cd service && uv tree                        # Python 依赖
```
