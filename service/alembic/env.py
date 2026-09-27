"""Alembic 运行环境。

三条纪律（见任务 `design.md` D4/D9）：

1. URL 只从 `SUMMER_DATABASE_URL` 取，不落版本库、不写进 `alembic.ini`。
2. **这里不做自动前置升级**——那会把 `downgrade`、`revision --autogenerate`、`current`
   全都变成"先升级再说"。自动迁移由应用启动钩子负责（`app/main.py`）。
3. `target_metadata` 指向模型、`compare_type` 打开，供 `alembic check` 抓漂移。

另有一条护栏：`downgrade` 只允许打在测试库上（`app/db/guard.py`）。
"""

from __future__ import annotations

import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

import app.models  # noqa: F401  导入即注册全部 31 张表
from alembic import context
from app.db.base import Base
from app.db.guard import assert_test_database

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def database_url() -> str:
    """连接串来自环境变量；离线渲染（`--sql`）也走这里。"""
    url = os.environ.get("SUMMER_DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError(
            "SUMMER_DATABASE_URL 未设置。请在 service/.env 或环境变量里提供连接串。"
            "只渲染 DDL 不连库时可用 `alembic upgrade head --sql`，同样需要该变量来定方言。"
        )
    return url


def _guard_destructive_command(url: str) -> None:
    cmd_opts = getattr(config, "cmd_opts", None)
    cmd = getattr(cmd_opts, "cmd", None)
    if cmd and cmd[0].__name__ == "downgrade":
        assert_test_database(url, "downgrade")


def run_migrations_offline() -> None:
    """离线渲染：把 SQL 打到 stdout，不连库（`alembic upgrade head --sql`）。"""
    context.configure(
        url=database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    url = database_url()
    _guard_destructive_command(url)

    section = dict(config.get_section(config.config_ini_section) or {})
    section["sqlalchemy.url"] = url
    connectable = engine_from_config(section, prefix="sqlalchemy.", poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
