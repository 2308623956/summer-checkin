# 05 · 复盘会话与聊天室

> 3 张表：`conversation`、`conversationmessage`、`chatmessage`。
> **归属**：`conversation` / `conversationmessage` 由 `service/` 读写（复盘编排）；`chatmessage` 不启用（见 `../decisions/ADR-002-no-chatroom.md`）。

## 5.1 `conversation`

一个会话。本项目复用为**复盘会话**：题库复盘一轮一条、简历复盘一轮一条。

| 列 | 类型 | 默认 / 约束 | 说明 |
|---|---|---|---|
| `id` | text | PK | |
| `user_id` | text | NOT NULL → `user.id` CASCADE | |
| `title` | text | NOT NULL, `'新对话'` | 本项目约定格式：`复盘 · 题库 · <主题> · 2026-09-25` / `复盘 · 简历 · <项目名>` |
| `created_at` | timestamptz | NOT NULL, `now()` | |
| `updated_at` | timestamptz | NOT NULL, `now()` | 每轮问答后更新（列表按它排序） |

**索引**：`INDEX(user_id, updated_at)`。
**为什么不再建一张"复盘会话表"**：会话的生命周期、消息结构、列表查询与已有能力完全一致，另建一张只会让"会话"这件事有两套实现。复盘的差异（主题、评分）落在消息内容与 `usermemory` 里。

## 5.2 `conversationmessage`

会话内的每条消息。

| 列 | 类型 | 默认 / 约束 | 说明 |
|---|---|---|---|
| `id` | text | PK | |
| `conversation_id` | text | NOT NULL → `conversation.id` CASCADE | |
| `role` | text | NOT NULL | `user` / `assistant` /（可能还有 `system`，取值以运行时为准） |
| `content` | text | NOT NULL | 正文；评分与反馈用 Markdown 约定段落写在这里 |
| `created_at` | timestamptz | NOT NULL, `now()` | |

**索引**：`INDEX(conversation_id, created_at)`。
**内容约定**（assistant 消息，前端按约定渲染，**不新增列**）：

```markdown
## 追问（L2）
……

## 评分
| 维度 | 分 | 依据 |
|---|---|---|
| 要点覆盖 | 3/5 | 漏了幂等边界 |
| 准确度 | 4/5 | …… |
| 结构 | 3/5 | …… |
| 深度 | 2/5 | 停在"加锁"，没说条件更新 |

## 弱项
- 并发下的幂等边界（已写入弱项档案）
```

**已知取舍**：评分没有独立列/表，统计"平均分趋势"需要解析 Markdown。首版接受（复盘轮次少、解析在 service 内一处完成）；若统计要变复杂，再谈是否加结构化列。

## 5.3 `chatmessage`

聊天室消息（**本项目不启用**）。

| 列 | 类型 | 默认 / 约束 | 说明 |
|---|---|---|---|
| `id` | text | PK | |
| `user_id` | text | NULL → `user.id` **SET NULL** | 允许匿名/系统消息 |
| `role` | text | NOT NULL, `'user'` | |
| `content` | text | NOT NULL | |
| `ai_role` | text | NULL | AI 角色标识（原项目两个拟人角色） |
| `reply_to_id` | text | NULL → `chatmessage.id` **SET NULL** | 引用回复 |
| `created_at` | timestamptz | NOT NULL, `now()` | |

**索引**：`INDEX(created_at)`、`INDEX(reply_to_id)`。
**本项目用法**：表建出来但**没有任何代码读写**（保留是为了不重建迁移基线；ADR-002 记录了不迁移聊天室的决定）。

---

**变更记录**

| 日期 | 变更 |
|---|---|
| 2026-09-25 | 首版（3 张表全字段 + 复盘会话的内容约定） |
