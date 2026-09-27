# 第三方声明（Third-Party Notices）

本仓库包含源自下列第三方项目的部分设计与数据模型。按其许可证要求，此处保留原始版权声明。

---

## summer-checkin（原始项目）

本项目的领域设计、数据模型与页面结构参考并重构自 `ruan-weibo` 的 **summer-checkin** 项目
（原始副本以只读方式保留在仓库外的 `summer-checkin-master/`，不随本仓库分发）。

具体继承关系：

| 项 | 说明 |
|---|---|
| 数据模型 | 31 张表中的 **27 张沿用原项目的表名与字段语义**（如 `agentapproval`、`plantask`、`plantemplate`、`usermemory`），新增 `verification` 与 `evalfixture` / `evalrun` / `evalresult` 四张 |
| 页面结构 | 页面路由沿用原项目（`/checkin`、`/dashboard`、`/plans`、`/docs`、`/agent`、`/profile`、`/statistics`） |
| 功能设计 | 打卡字段语义、agent 的 Observe→Analyze→Plan→Execute 四步与审批分级 |

**实现是重写的，不是复制。** 原项目为 Next.js API Routes + Prisma 单体；本项目拆为
FastAPI 领域服务 + Next.js BFF 双服务，Python 与 TypeScript 代码均为重新编写，
未移植原项目的组件、样式或路由处理器。

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

> **待补**：原始项目的公开仓库地址未能确认（`github.com/ruan-weibo` 返回 404，
> 原始副本内也未声明 `repository` 字段）。作者确认来源后应在此处补上链接。

---

## 依赖项

本仓库的运行时与开发依赖（Next.js、React、FastAPI、SQLAlchemy、Alembic、pgvector 等）
各自遵循其自身许可证，未在此逐一罗列。需要完整清单时按语言查询：

```bash
cd web && npx license-checker --summary     # npm 依赖
cd service && uv tree                        # Python 依赖
```
