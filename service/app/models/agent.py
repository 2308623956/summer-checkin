"""04 · Agent 运行、审批、记忆与通知（9 张表）。

agentrun / agentstep / agentapproval / agenttoolcall / agentdecision / agentschedule /
usermemory / aihistory / notification。
审批边界（`agentapproval`）是这一组表的核心：写库类动作未批准不得执行。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    DateTime,
    Double,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.knowledge import EMBEDDING_DIM


class AgentRun(Base):
    """一次 agent 运行（本项目：一次每日巡检）。"""

    __tablename__ = "agentrun"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(
        Text, ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    mode: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'planner'"))
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'queued'"))
    current_step: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    max_steps: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("12"))
    summary: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # 回归对比的可比性前提：没有版本就无法回答"换了模型/prompt 之后变好了吗"。
    model: Mapped[str | None] = mapped_column(Text)
    prompt_version: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_agentrun_user_id_updated_at", "user_id", "updated_at"),
        Index("ix_agentrun_user_id_status", "user_id", "status"),
        Index("ix_agentrun_user_id_prompt_version", "user_id", "prompt_version"),
    )


class AgentStep(Base):
    """运行中的一步。`input` 里的 Observe 快照是冻结 fixture 的素材来源。"""

    __tablename__ = "agentstep"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    run_id: Mapped[str] = mapped_column(
        Text, ForeignKey("agentrun.id", ondelete="CASCADE"), nullable=False
    )
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'pending'"))
    title: Mapped[str] = mapped_column(Text, nullable=False)
    detail: Mapped[str | None] = mapped_column(Text)
    input: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    output: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("run_id", "step_number"),
        Index("ix_agentstep_run_id_status", "run_id", "status"),
    )


class AgentApproval(Base):
    """审批边界所在：写库类动作在这里等人工点头。"""

    __tablename__ = "agentapproval"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    run_id: Mapped[str] = mapped_column(
        Text, ForeignKey("agentrun.id", ondelete="CASCADE"), nullable=False
    )
    step_id: Mapped[str | None] = mapped_column(Text, ForeignKey("agentstep.id"))
    action: Mapped[str] = mapped_column(Text, nullable=False)
    # pending / approved / rejected / expired（expired 为本项目新增取值）。
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'pending'"))
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    decision_reason: Mapped[str | None] = mapped_column(Text)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (Index("ix_agentapproval_run_id_status", "run_id", "status"),)


class AgentToolCall(Base):
    """一次工具调用（含幂等键）。"""

    __tablename__ = "agenttoolcall"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    run_id: Mapped[str] = mapped_column(
        Text, ForeignKey("agentrun.id", ondelete="CASCADE"), nullable=False
    )
    step_id: Mapped[str | None] = mapped_column(Text, ForeignKey("agentstep.id"))
    tool_name: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'pending'"))
    # 幂等键：{run_id}:{action}:{主键}；同一键只落一行。
    idempotency_key: Mapped[str | None] = mapped_column(Text)
    input: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    output: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("idempotency_key"),
        Index("ix_agenttoolcall_run_id_status", "run_id", "status"),
        Index("ix_agenttoolcall_run_id_tool_name", "run_id", "tool_name"),
    )


class AgentDecision(Base):
    """决策台账：每条建议一行，带理由。`run_id` 为 SET NULL，run 清理后决策仍留存。"""

    __tablename__ = "agentdecision"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(
        Text, ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    run_id: Mapped[str | None] = mapped_column(Text, ForeignKey("agentrun.id", ondelete="SET NULL"))
    type: Mapped[str] = mapped_column(Text, nullable=False)
    # 必填：为什么给这条建议——抽查与采纳率都看它。
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    # pending（写库类等审批）/ executed / rejected / failed
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'executed'"))
    feedback: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_agentdecision_user_id_created_at", "user_id", "created_at"),
        Index("ix_agentdecision_user_id_type", "user_id", "type"),
        Index("ix_agentdecision_run_id", "run_id"),
    )


class AgentSchedule(Base):
    """巡检计划：本项目每日 21:00（只改默认值，列沿用参考实现）。"""

    __tablename__ = "agentschedule"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(
        Text, ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'daily_review'"))
    cron: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'0 21 * * *'"))
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("user_id", "type"),
        Index("ix_agentschedule_enabled_next_run_at", "enabled", "next_run_at"),
    )


class UserMemory(Base):
    """长期记忆，本项目同时是弱项档案。embedding 可空：生成失败留空，不丢整条记忆。"""

    __tablename__ = "usermemory"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(
        Text, ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    # 本项目约定新增取值：weakness（弱项）/ correction（已纠正）。
    type: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'fact'"))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))
    importance: Mapped[float] = mapped_column(Double, nullable=False, server_default=text("0.5"))
    confidence: Mapped[float] = mapped_column(Double, nullable=False, server_default=text("0.5"))
    last_used: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_usermemory_user_id_type", "user_id", "type"),
        Index("ix_usermemory_user_id_importance", "user_id", "importance"),
        Index("ix_usermemory_user_id_last_used", "user_id", "last_used"),
        Index(
            "usermemory_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


class AIHistory(Base):
    """ "快速问一句"的落点（不构成会话）。复盘与巡检不写它。"""

    __tablename__ = "aihistory"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(
        Text, ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    response: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (Index("ix_aihistory_user_id_created_at", "user_id", "created_at"),)


class Notification(Base):
    """站内通知。通知类建议不需要审批，直接写这里。"""

    __tablename__ = "notification"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(
        Text, ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'reminder'"))
    title: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    read: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    action_url: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_notification_user_id_read_created_at", "user_id", "read", "created_at"),
        Index("ix_notification_user_id_type", "user_id", "type"),
    )
