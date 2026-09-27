"""03 · 文档与知识库（4 张表）：document / documentchunk / knowledgedoc / documenttemplate。

题库原文与简历正文都进 `knowledgedoc`，切块后进 `documentchunk`（1024 维向量 + HNSW）。
维度契约：链上任何 embedding 模型必须输出 1024 维（1536 维模型绝不能进链）。
"""

from __future__ import annotations

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Index, Integer, Text, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

EMBEDDING_DIM = 1024


class Document(Base):
    """用户自己写的资料正文（Markdown），给人看。"""

    __tablename__ = "document"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(
        Text, ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (Index("ix_document_user_id_updated_at", "user_id", "updated_at"),)


class DocumentChunk(Base):
    """检索单元：原文切块 + 1024 维向量，RAG 的读路径。"""

    __tablename__ = "documentchunk"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    # 检索必须带 user_id 过滤，绝不跨用户。
    user_id: Mapped[str] = mapped_column(
        Text, ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    source_name: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'text'"))
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # 写入即生成；生成失败整条不入库（宁可少一条，也不留半条）。
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_documentchunk_user_id_source_name", "user_id", "source_name"),
        Index("ix_documentchunk_source_name", "source_name"),
        Index(
            "documentchunk_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


class KnowledgeDoc(Base):
    """入库原文（每份资料一行），同时是"是否已导入"的去重依据。"""

    __tablename__ = "knowledgedoc"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(
        Text, ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    source_name: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("user_id", "source_name"),
        Index("ix_knowledgedoc_user_id", "user_id"),
    )


class DocumentTemplate(Base):
    """资料模板（新建文档时可选）。"""

    __tablename__ = "documenttemplate"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
