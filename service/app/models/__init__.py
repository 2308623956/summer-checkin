"""模型包：导入即注册全部 31 张表到 `Base.metadata`。

Alembic 与测试都依赖这个副作用，所以这里显式导入每个模块，顺序无关（外键按表名解析）。
"""

from __future__ import annotations

from app.models.account import Account, AvatarChange, Session, User, Verification
from app.models.agent import (
    AgentApproval,
    AgentDecision,
    AgentRun,
    AgentSchedule,
    AgentStep,
    AgentToolCall,
    AIHistory,
    Notification,
    UserMemory,
)
from app.models.conversation import ChatMessage, Conversation, ConversationMessage
from app.models.knowledge import Document, DocumentChunk, DocumentTemplate, KnowledgeDoc
from app.models.study import Checkin, Plan, PlanTask, PlanTemplate, StudyRecord, Todo
from app.models.usage_eval import EvalFixture, EvalResult, EvalRun, TokenUsage

__all__ = [
    "AIHistory",
    "Account",
    "AgentApproval",
    "AgentDecision",
    "AgentRun",
    "AgentSchedule",
    "AgentStep",
    "AgentToolCall",
    "AvatarChange",
    "ChatMessage",
    "Checkin",
    "Conversation",
    "ConversationMessage",
    "Document",
    "DocumentChunk",
    "DocumentTemplate",
    "EvalFixture",
    "EvalResult",
    "EvalRun",
    "KnowledgeDoc",
    "Notification",
    "Plan",
    "PlanTask",
    "PlanTemplate",
    "Session",
    "StudyRecord",
    "Todo",
    "TokenUsage",
    "User",
    "UserMemory",
    "Verification",
]
