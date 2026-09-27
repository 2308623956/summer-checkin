"""05 · 复盘会话与聊天室（3 张表）：conversation / conversationmessage / chatmessage。

`conversation` / `conversationmessage` 复用为复盘会话；`chatmessage` 建表但不启用
（ADR-002：聊天室不迁移，保留表是为了不动迁移基线）。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Conversation(Base):
    """会话；本项目复用为复盘会话（题库一轮一条、简历一轮一条）。"""

    __tablename__ = "conversation"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(
        Text, ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'新对话'"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (Index("ix_conversation_user_id_updated_at", "user_id", "updated_at"),)


class ConversationMessage(Base):
    """会话内的每条消息。评分与反馈用 Markdown 约定段落写在 content 里（不新增列）。"""

    __tablename__ = "conversationmessage"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        Text, ForeignKey("conversation.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_conversationmessage_conversation_id_created_at", "conversation_id", "created_at"),
    )


class ChatMessage(Base):
    """聊天室消息：本项目建表但没有任何代码读写。"""

    __tablename__ = "chatmessage"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    # SET NULL：允许匿名 / 系统消息。
    user_id: Mapped[str | None] = mapped_column(Text, ForeignKey("user.id", ondelete="SET NULL"))
    role: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'user'"))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    ai_role: Mapped[str | None] = mapped_column(Text)
    reply_to_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("chatmessage.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_chatmessage_created_at", "created_at"),
        Index("ix_chatmessage_reply_to_id", "reply_to_id"),
    )
