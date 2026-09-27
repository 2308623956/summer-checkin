"""数据库会话与事务边界。

事务边界规则：**一个请求一个事务**，在依赖的 `finally` 里提交或回滚。
服务层不自己 commit，这样"写多张表"天然在一个事务里（跨层思考指南的要求）。
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings

# 探针超时：连不通时驱动会等操作系统的 connect 超时（实测约 2 秒），数据库"半死"时更久。
PING_TIMEOUT_SECONDS = 3.0

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def init_engine(settings: Settings) -> AsyncEngine:
    """建连接池。进程内单例；测试里用 `dispose_engine()` 重置。"""
    global _engine, _session_factory
    if _engine is None:
        _engine = create_async_engine(
            settings.async_database_url,
            pool_pre_ping=True,  # 连的是长连接，防止拿到已被服务端断开的连接
            pool_size=5,
            max_overflow=5,
            echo=False,
            # 连接阶段也要有超时，否则数据库不可达时请求会一直挂着。
            connect_args={"timeout": PING_TIMEOUT_SECONDS},
        )
        _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


async def dispose_engine() -> None:
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    if _session_factory is None:
        raise RuntimeError("数据库引擎尚未初始化：请先调用 init_engine()")
    return _session_factory


def get_engine() -> AsyncEngine:
    if _engine is None:
        raise RuntimeError("数据库引擎尚未初始化：请先调用 init_engine()")
    return _engine


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI 依赖：给路由/服务层一个会话，并在退出时定事务。"""
    async with get_session_factory()() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        else:
            await session.commit()


async def ping(engine: AsyncEngine, timeout_seconds: float = PING_TIMEOUT_SECONDS) -> bool:
    """`/healthz` 的数据库探针：失败不抛异常，健康检查要能返回 degraded 而不是 500。

    带超时是必要的：连不通时驱动会等操作系统的 connect 超时（实测约 2 秒），
    数据库"半死"时会更久。探针拖住请求，健康检查本身就失去了意义。
    """
    from sqlalchemy import text

    try:
        async with asyncio.timeout(timeout_seconds):
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
    except (Exception, TimeoutError):
        return False
    return True
