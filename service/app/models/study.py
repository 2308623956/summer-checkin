"""02 · 学习计划与打卡（6 张表）：plan / plantask / todo / checkin / studyrecord / plantemplate。

巡检 agent 的输入（连续天数、时长、待办）全部来自这里。统计一律按 `checkin_date`。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Double,
    ForeignKey,
    Index,
    Integer,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Plan(Base):
    """一个学习计划（可含 Markdown 计划文档）。"""

    __tablename__ = "plan"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(
        Text, ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    goal: Mapped[str | None] = mapped_column(Text)
    document: Mapped[str | None] = mapped_column(Text)
    tasks_source_hash: Mapped[str | None] = mapped_column(Text)
    tasks_splitting_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'active'"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class PlanTask(Base):
    """计划下的任务条目；也是审批通过后补强任务的落地表（只有审批放行才允许 agent 写）。"""

    __tablename__ = "plantask"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    plan_id: Mapped[str] = mapped_column(
        Text, ForeignKey("plan.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        Text, ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    day_number: Mapped[int | None] = mapped_column(Integer)
    week_number: Mapped[int | None] = mapped_column(Integer)
    category: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'study'"))
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'pending'"))
    priority: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'normal'"))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_plantask_plan_id", "plan_id"),
        Index("ix_plantask_user_id_status", "user_id", "status"),
        Index("ix_plantask_user_id_day_number", "user_id", "day_number"),
    )


class Todo(Base):
    """轻量待办（不挂在计划下）。巡检观察"未完成待办数"判断任务量是否过载。"""

    __tablename__ = "todo"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(
        Text, ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    completed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_todo_user_id_completed", "user_id", "completed"),
        Index("ix_todo_user_id_created_at", "user_id", "created_at"),
    )


class Checkin(Base):
    """一次打卡记录：统计与巡检的主要事实表。"""

    __tablename__ = "checkin"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(
        Text, ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    # 删计划不清打卡：不级联。
    plan_id: Mapped[str | None] = mapped_column(Text, ForeignKey("plan.id"))
    source_task_id: Mapped[str | None] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    hours: Mapped[float] = mapped_column(Double, nullable=False, server_default=text("0"))
    # 与题库主题、plantask.category 用同一套字符串。
    subject: Mapped[str | None] = mapped_column(Text)
    mood: Mapped[str | None] = mapped_column(Text)
    screenshot: Mapped[str | None] = mapped_column(Text)
    checkin_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_checkin_user_id_checkin_date", "user_id", "checkin_date"),
        Index("ix_checkin_source_task_id", "source_task_id"),
    )


class StudyRecord(Base):
    """按日聚合的学习时长。"""

    __tablename__ = "studyrecord"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(
        Text, ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    total_minutes: Mapped[float] = mapped_column(Double, nullable=False, server_default=text("0"))
    subject: Mapped[str | None] = mapped_column(Text)
    # 无外键，与参考实现一致。
    checkin_id: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (Index("ix_studyrecord_user_id_date", "user_id", "date"),)


class PlanTemplate(Base):
    """新用户引导用的计划模板。单用户阶段用不到，保留以免删表引发连锁改动。"""

    __tablename__ = "plantemplate"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    goal: Mapped[str | None] = mapped_column(Text)
    document: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
