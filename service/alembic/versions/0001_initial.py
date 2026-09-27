"""0001 初始基线：31 张表 + pgvector 扩展 + HNSW 索引。

本文件由模型定义机械生成后**冻结**（见任务 implement.md S2a）：不引用 app 代码，
因此模型日后演进不会悄悄改写这条基线。后续迁移一律 `alembic revision --autogenerate`。

手写部分：`CREATE EXTENSION vector`（pgvector 不是 trusted extension，需超级用户）、
`vector(1024)` 列与 `USING hnsw` 索引——这三处 autogenerate 认不出来。
"""

from __future__ import annotations

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # pgvector 不是 trusted extension：这条需要超级用户权限（见 integrations.md §6.1）。
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "avatarchange",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("image", sa.Text()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_avatarchange"),
    )

    op.create_table(
        "documenttemplate",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_documenttemplate"),
    )

    op.create_table(
        "plantemplate",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("goal", sa.Text()),
        sa.Column("document", sa.Text()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_plantemplate"),
    )

    op.create_table(
        "user",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("image", sa.Text()),
        sa.Column("bio", sa.Text()),
        sa.Column("theme", sa.Text(), nullable=False, server_default=sa.text("'system'")),
        sa.Column("vip", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_user"),
        sa.UniqueConstraint("email", name="uq_user_email"),
    )

    op.create_table(
        "verification",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("identifier", sa.Text(), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_verification"),
    )

    op.create_table(
        "account",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("provider_id", sa.Text(), nullable=False),
        sa.Column("account_id", sa.Text(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False, server_default=sa.text("'credential'")),
        sa.Column("password", sa.Text()),
        sa.Column("access_token", sa.Text()),
        sa.Column("refresh_token", sa.Text()),
        sa.Column("access_token_expires_at", sa.DateTime(timezone=True)),
        sa.Column("refresh_token_expires_at", sa.DateTime(timezone=True)),
        sa.Column("scope", sa.Text()),
        sa.Column("id_token", sa.Text()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["user.id"], name="fk_account_user_id_user", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_account"),
        sa.UniqueConstraint("provider_id", "account_id", name="uq_account_provider_id_account_id"),
    )

    op.create_table(
        "agentrun",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("mode", sa.Text(), nullable=False, server_default=sa.text("'planner'")),
        sa.Column("goal", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'queued'")),
        sa.Column("current_step", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("max_steps", sa.Integer(), nullable=False, server_default=sa.text("12")),
        sa.Column("summary", sa.Text()),
        sa.Column("error", sa.Text()),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("model", sa.Text()),
        sa.Column("prompt_version", sa.Text()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["user.id"], name="fk_agentrun_user_id_user", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_agentrun"),
    )

    op.create_table(
        "agentschedule",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False, server_default=sa.text("'daily_review'")),
        sa.Column("cron", sa.Text(), nullable=False, server_default=sa.text("'0 21 * * *'")),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_run_at", sa.DateTime(timezone=True)),
        sa.Column("next_run_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["user.id"], name="fk_agentschedule_user_id_user", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_agentschedule"),
        sa.UniqueConstraint("user_id", "type", name="uq_agentschedule_user_id_type"),
    )

    op.create_table(
        "aihistory",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("response", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["user.id"], name="fk_aihistory_user_id_user", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_aihistory"),
    )

    op.create_table(
        "chatmessage",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Text()),
        sa.Column("role", sa.Text(), nullable=False, server_default=sa.text("'user'")),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("ai_role", sa.Text()),
        sa.Column("reply_to_id", sa.Text()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["user.id"], name="fk_chatmessage_user_id_user", ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["reply_to_id"],
            ["chatmessage.id"],
            name="fk_chatmessage_reply_to_id_chatmessage",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_chatmessage"),
    )

    op.create_table(
        "conversation",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False, server_default=sa.text("'新对话'")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["user.id"], name="fk_conversation_user_id_user", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_conversation"),
    )

    op.create_table(
        "document",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["user.id"], name="fk_document_user_id_user", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_document"),
    )

    op.create_table(
        "documentchunk",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("source_name", sa.Text(), nullable=False),
        sa.Column("source_type", sa.Text(), nullable=False, server_default=sa.text("'text'")),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(1024), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["user.id"], name="fk_documentchunk_user_id_user", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_documentchunk"),
    )

    op.create_table(
        "evalrun",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Text()),
        sa.Column("suite", sa.Text(), nullable=False),
        sa.Column("prompt_version", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("baseline_run_id", sa.Text()),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'running'")),
        sa.Column("total", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("passed", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("failed", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("pass_rate", sa.Double()),
        sa.Column("cost_usd", sa.Numeric(12, 6)),
        sa.Column("p95_latency_ms", sa.Integer()),
        sa.Column("git_sha", sa.Text()),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["baseline_run_id"],
            ["evalrun.id"],
            name="fk_evalrun_baseline_run_id_evalrun",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["user.id"], name="fk_evalrun_user_id_user", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_evalrun"),
    )

    op.create_table(
        "knowledgedoc",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("source_name", sa.Text(), nullable=False),
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["user.id"], name="fk_knowledgedoc_user_id_user", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_knowledgedoc"),
        sa.UniqueConstraint("user_id", "source_name", name="uq_knowledgedoc_user_id_source_name"),
    )

    op.create_table(
        "notification",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False, server_default=sa.text("'reminder'")),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("read", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("action_url", sa.Text()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["user.id"], name="fk_notification_user_id_user", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_notification"),
    )

    op.create_table(
        "plan",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("goal", sa.Text()),
        sa.Column("document", sa.Text()),
        sa.Column("tasks_source_hash", sa.Text()),
        sa.Column("tasks_splitting_at", sa.DateTime(timezone=True)),
        sa.Column("start_date", sa.DateTime(timezone=True)),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'active'")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["user.id"], name="fk_plan_user_id_user", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_plan"),
    )

    op.create_table(
        "session",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("token", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ip_address", sa.Text()),
        sa.Column("user_agent", sa.Text()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["user.id"], name="fk_session_user_id_user", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_session"),
        sa.UniqueConstraint("token", name="uq_session_token"),
    )

    op.create_table(
        "studyrecord",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total_minutes", sa.Double(), nullable=False, server_default=sa.text("0")),
        sa.Column("subject", sa.Text()),
        sa.Column("checkin_id", sa.Text()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["user.id"], name="fk_studyrecord_user_id_user", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_studyrecord"),
    )

    op.create_table(
        "todo",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("completed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["user.id"], name="fk_todo_user_id_user", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_todo"),
    )

    op.create_table(
        "usermemory",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False, server_default=sa.text("'fact'")),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(1024)),
        sa.Column("importance", sa.Double(), nullable=False, server_default=sa.text("0.5")),
        sa.Column("confidence", sa.Double(), nullable=False, server_default=sa.text("0.5")),
        sa.Column("last_used", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["user.id"], name="fk_usermemory_user_id_user", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_usermemory"),
    )

    op.create_table(
        "agentdecision",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("run_id", sa.Text()),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("action", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'executed'")),
        sa.Column("feedback", sa.Text()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["agentrun.id"],
            name="fk_agentdecision_run_id_agentrun",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["user.id"], name="fk_agentdecision_user_id_user", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_agentdecision"),
    )

    op.create_table(
        "agentstep",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("step_number", sa.Integer(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("detail", sa.Text()),
        sa.Column("input", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("output", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("error", sa.Text()),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["run_id"], ["agentrun.id"], name="fk_agentstep_run_id_agentrun", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_agentstep"),
        sa.UniqueConstraint("run_id", "step_number", name="uq_agentstep_run_id_step_number"),
    )

    op.create_table(
        "checkin",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("plan_id", sa.Text()),
        sa.Column("source_task_id", sa.Text()),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("hours", sa.Double(), nullable=False, server_default=sa.text("0")),
        sa.Column("subject", sa.Text()),
        sa.Column("mood", sa.Text()),
        sa.Column("screenshot", sa.Text()),
        sa.Column(
            "checkin_date",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["plan_id"], ["plan.id"], name="fk_checkin_plan_id_plan"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["user.id"], name="fk_checkin_user_id_user", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_checkin"),
    )

    op.create_table(
        "conversationmessage",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("conversation_id", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversation.id"],
            name="fk_conversationmessage_conversation_id_conversation",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_conversationmessage"),
    )

    op.create_table(
        "evalfixture",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Text()),
        sa.Column("suite", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("source_run_id", sa.Text()),
        sa.Column(
            "fixture_schema_version", sa.Integer(), nullable=False, server_default=sa.text("1")
        ),
        sa.Column("input", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("expected", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column(
            "tags", postgresql.ARRAY(sa.Text()), nullable=False, server_default=sa.text("'{}'")
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["user.id"], name="fk_evalfixture_user_id_user", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["source_run_id"],
            ["agentrun.id"],
            name="fk_evalfixture_source_run_id_agentrun",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_evalfixture"),
        sa.UniqueConstraint("user_id", "suite", "name", name="uq_evalfixture_user_id_suite_name"),
    )

    op.create_table(
        "plantask",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("plan_id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("day_number", sa.Integer()),
        sa.Column("week_number", sa.Integer()),
        sa.Column("category", sa.Text(), nullable=False, server_default=sa.text("'study'")),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("priority", sa.Text(), nullable=False, server_default=sa.text("'normal'")),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"], ["plan.id"], name="fk_plantask_plan_id_plan", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["user.id"], name="fk_plantask_user_id_user", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_plantask"),
    )

    op.create_table(
        "tokenusage",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("surface", sa.Text(), nullable=False),
        sa.Column("tier", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("run_id", sa.Text()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["run_id"], ["agentrun.id"], name="fk_tokenusage_run_id_agentrun", ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["user.id"], name="fk_tokenusage_user_id_user", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_tokenusage"),
    )

    op.create_table(
        "agentapproval",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("step_id", sa.Text()),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("decision_reason", sa.Text()),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["step_id"], ["agentstep.id"], name="fk_agentapproval_step_id_agentstep"
        ),
        sa.ForeignKeyConstraint(
            ["run_id"], ["agentrun.id"], name="fk_agentapproval_run_id_agentrun", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_agentapproval"),
    )

    op.create_table(
        "agenttoolcall",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("step_id", sa.Text()),
        sa.Column("tool_name", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("idempotency_key", sa.Text()),
        sa.Column("input", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("output", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("error", sa.Text()),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["step_id"], ["agentstep.id"], name="fk_agenttoolcall_step_id_agentstep"
        ),
        sa.ForeignKeyConstraint(
            ["run_id"], ["agentrun.id"], name="fk_agenttoolcall_run_id_agentrun", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_agenttoolcall"),
        sa.UniqueConstraint("idempotency_key", name="uq_agenttoolcall_idempotency_key"),
    )

    op.create_table(
        "evalresult",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("eval_run_id", sa.Text(), nullable=False),
        sa.Column("fixture_id", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("actual", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("expected", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("diff", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("score", sa.Double()),
        sa.Column("latency_ms", sa.Integer()),
        sa.Column("cost_usd", sa.Numeric(12, 6)),
        sa.Column("tokens_in", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("tokens_out", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["eval_run_id"],
            ["evalrun.id"],
            name="fk_evalresult_eval_run_id_evalrun",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["fixture_id"],
            ["evalfixture.id"],
            name="fk_evalresult_fixture_id_evalfixture",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_evalresult"),
        sa.UniqueConstraint(
            "eval_run_id", "fixture_id", name="uq_evalresult_eval_run_id_fixture_id"
        ),
    )

    op.create_index("ix_avatarchange_user_id_created_at", "avatarchange", ["user_id", "created_at"])
    op.create_index("ix_agentrun_user_id_prompt_version", "agentrun", ["user_id", "prompt_version"])
    op.create_index("ix_agentrun_user_id_status", "agentrun", ["user_id", "status"])
    op.create_index("ix_agentrun_user_id_updated_at", "agentrun", ["user_id", "updated_at"])
    op.create_index(
        "ix_agentschedule_enabled_next_run_at", "agentschedule", ["enabled", "next_run_at"]
    )
    op.create_index("ix_aihistory_user_id_created_at", "aihistory", ["user_id", "created_at"])
    op.create_index("ix_chatmessage_created_at", "chatmessage", ["created_at"])
    op.create_index("ix_chatmessage_reply_to_id", "chatmessage", ["reply_to_id"])
    op.create_index("ix_conversation_user_id_updated_at", "conversation", ["user_id", "updated_at"])
    op.create_index("ix_document_user_id_updated_at", "document", ["user_id", "updated_at"])
    op.create_index(
        "documentchunk_embedding_hnsw",
        "documentchunk",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.create_index("ix_documentchunk_source_name", "documentchunk", ["source_name"])
    op.create_index(
        "ix_documentchunk_user_id_source_name", "documentchunk", ["user_id", "source_name"]
    )
    op.create_index("ix_evalrun_prompt_version", "evalrun", ["prompt_version"])
    op.create_index("ix_evalrun_suite_status", "evalrun", ["suite", "status"])
    op.create_index("ix_evalrun_user_id_created_at", "evalrun", ["user_id", "created_at"])
    op.create_index("ix_knowledgedoc_user_id", "knowledgedoc", ["user_id"])
    op.create_index(
        "ix_notification_user_id_read_created_at", "notification", ["user_id", "read", "created_at"]
    )
    op.create_index("ix_notification_user_id_type", "notification", ["user_id", "type"])
    op.create_index("ix_session_user_id", "session", ["user_id"])
    op.create_index("ix_studyrecord_user_id_date", "studyrecord", ["user_id", "date"])
    op.create_index("ix_todo_user_id_completed", "todo", ["user_id", "completed"])
    op.create_index("ix_todo_user_id_created_at", "todo", ["user_id", "created_at"])
    op.create_index("ix_usermemory_user_id_importance", "usermemory", ["user_id", "importance"])
    op.create_index("ix_usermemory_user_id_last_used", "usermemory", ["user_id", "last_used"])
    op.create_index("ix_usermemory_user_id_type", "usermemory", ["user_id", "type"])
    op.create_index(
        "usermemory_embedding_hnsw",
        "usermemory",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.create_index("ix_agentdecision_run_id", "agentdecision", ["run_id"])
    op.create_index(
        "ix_agentdecision_user_id_created_at", "agentdecision", ["user_id", "created_at"]
    )
    op.create_index("ix_agentdecision_user_id_type", "agentdecision", ["user_id", "type"])
    op.create_index("ix_agentstep_run_id_status", "agentstep", ["run_id", "status"])
    op.create_index("ix_checkin_source_task_id", "checkin", ["source_task_id"])
    op.create_index("ix_checkin_user_id_checkin_date", "checkin", ["user_id", "checkin_date"])
    op.create_index(
        "ix_conversationmessage_conversation_id_created_at",
        "conversationmessage",
        ["conversation_id", "created_at"],
    )
    op.create_index("ix_evalfixture_suite_enabled", "evalfixture", ["suite", "enabled"])
    op.create_index("ix_plantask_plan_id", "plantask", ["plan_id"])
    op.create_index("ix_plantask_user_id_day_number", "plantask", ["user_id", "day_number"])
    op.create_index("ix_plantask_user_id_status", "plantask", ["user_id", "status"])
    op.create_index("ix_tokenusage_run_id", "tokenusage", ["run_id"])
    op.create_index("ix_tokenusage_user_id_created_at", "tokenusage", ["user_id", "created_at"])
    op.create_index("ix_agentapproval_run_id_status", "agentapproval", ["run_id", "status"])
    op.create_index("ix_agenttoolcall_run_id_status", "agenttoolcall", ["run_id", "status"])
    op.create_index("ix_agenttoolcall_run_id_tool_name", "agenttoolcall", ["run_id", "tool_name"])
    op.create_index("ix_evalresult_fixture_id_status", "evalresult", ["fixture_id", "status"])


def downgrade() -> None:
    # 索引随表一起删除，无需单独 drop_index。
    op.drop_table("evalresult")
    op.drop_table("agenttoolcall")
    op.drop_table("agentapproval")
    op.drop_table("tokenusage")
    op.drop_table("plantask")
    op.drop_table("evalfixture")
    op.drop_table("conversationmessage")
    op.drop_table("checkin")
    op.drop_table("agentstep")
    op.drop_table("agentdecision")
    op.drop_table("usermemory")
    op.drop_table("todo")
    op.drop_table("studyrecord")
    op.drop_table("session")
    op.drop_table("plan")
    op.drop_table("notification")
    op.drop_table("knowledgedoc")
    op.drop_table("evalrun")
    op.drop_table("documentchunk")
    op.drop_table("document")
    op.drop_table("conversation")
    op.drop_table("chatmessage")
    op.drop_table("aihistory")
    op.drop_table("agentschedule")
    op.drop_table("agentrun")
    op.drop_table("account")
    op.drop_table("verification")
    op.drop_table("user")
    op.drop_table("plantemplate")
    op.drop_table("documenttemplate")
    op.drop_table("avatarchange")
