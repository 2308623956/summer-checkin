"""06 · 成本账本与回归门禁（4 张表）：tokenusage + evalfixture / evalrun / evalresult。

`tokenusage.run_id` 为 SET NULL：清理 run 时账本不失真。三张 eval 表在 R000 就建出来，
避免 R010 再改迁移基线（空地新建一次做干净）。
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Double,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TokenUsage(Base):
    """成本账本：模型池每次调用记一行。只记 tokens，成本在聚合时按单价表估算。"""

    __tablename__ = "tokenusage"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(
        Text, ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    # agent / studio / chatroom / title / memory / split / agent-bg / review（新增取值，无需迁移）
    surface: Mapped[str] = mapped_column(Text, nullable=False)
    tier: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    # SET NULL：清理 run 时账本不丢。
    run_id: Mapped[str | None] = mapped_column(Text, ForeignKey("agentrun.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_tokenusage_user_id_created_at", "user_id", "created_at"),
        Index("ix_tokenusage_run_id", "run_id"),
    )


class EvalFixture(Base):
    """冻结的回归样本：把真实跑过的巡检/复盘固化成可重放的输入。"""

    __tablename__ = "evalfixture"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    # NULL = 系统样本（不含个人数据）。
    user_id: Mapped[str | None] = mapped_column(Text, ForeignKey("user.id", ondelete="CASCADE"))
    suite: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    # 被引用的 run 不参与清理。
    source_run_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("agentrun.id", ondelete="SET NULL")
    )
    fixture_schema_version: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("1")
    )
    input: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    expected: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    tags: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'")
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("user_id", "suite", "name"),
        Index("ix_evalfixture_suite_enabled", "suite", "enabled"),
    )


class EvalRun(Base):
    """一次重放：同一套 fixture 在某个 prompt/模型组合下跑一遍。"""

    __tablename__ = "evalrun"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str | None] = mapped_column(Text, ForeignKey("user.id", ondelete="CASCADE"))
    suite: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_version: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    baseline_run_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("evalrun.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'running'"))
    total: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    passed: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    failed: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    pass_rate: Mapped[float | None] = mapped_column(Double)
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    p95_latency_ms: Mapped[int | None] = mapped_column(Integer)
    git_sha: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_evalrun_user_id_created_at", "user_id", "created_at"),
        Index("ix_evalrun_suite_status", "suite", "status"),
        Index("ix_evalrun_prompt_version", "prompt_version"),
    )


class EvalResult(Base):
    """单样本结果：一次重放里每条 fixture 一行。"""

    __tablename__ = "evalresult"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    eval_run_id: Mapped[str] = mapped_column(
        Text, ForeignKey("evalrun.id", ondelete="CASCADE"), nullable=False
    )
    fixture_id: Mapped[str] = mapped_column(
        Text, ForeignKey("evalfixture.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    actual: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    expected: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    diff: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    score: Mapped[float | None] = mapped_column(Double)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    tokens_in: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    tokens_out: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("eval_run_id", "fixture_id"),
        Index("ix_evalresult_fixture_id_status", "fixture_id", "status"),
    )
