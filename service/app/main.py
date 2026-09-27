"""FastAPI 应用装配。

启动自检的顺序很重要：**先校验配置与公钥，再连数据库**。缺公钥就拒绝启动，
绝不允许"配置不全 → 无鉴权放行"这种降级（`docs/tech/backend.md` §5.4）。
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from app.api.v1 import api_router
from app.core.config import Settings, get_settings
from app.core.handlers import register_exception_handlers
from app.core.logging import RequestContextMiddleware, configure_logging
from app.core.security import verify_public_key
from app.db.session import dispose_engine, get_engine, init_engine, ping

logger = structlog.get_logger()


def _run_migrations(settings: Settings) -> None:
    """开发期自动追平迁移。生产固定关闭（`SUMMER_AUTO_MIGRATE=false`）。"""
    from pathlib import Path

    service_root = Path(__file__).resolve().parents[1]
    logger.info("auto_migrate: upgrading to head")
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=service_root,
        check=True,
    )
    # 追平之后再比对一次：有漂移说明有人改了模型却没写迁移，此时应当拒绝启动，
    # 否则服务会带着"代码以为存在的列"跑起来，报错出现在业务查询里而不是启动日志里。
    logger.info("auto_migrate: checking for drift")
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "check"],
        cwd=service_root,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "模型与数据库存在漂移：请生成迁移后再启动。\n"
            f"alembic check 输出：\n{result.stdout}\n{result.stderr}"
        )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)

    # 1. 公钥可解析性：格式错了要在这里炸，而不是等第一个用户登录。
    verify_public_key(settings.jwt_public_key)
    logger.info("startup: jwt public key ok")

    # 2. 迁移（仅开发期）。
    if settings.auto_migrate:
        _run_migrations(settings)

    # 3. 数据库可达性：连不上就如实报出来并继续启动。
    #    不在这里退出——否则数据库抖一下容器就起不来，而且 /healthz 也没机会说明原因。
    init_engine(settings)
    db_ok = await ping(get_engine())
    logger.info("startup: database probe", db="ok" if db_ok else "down")
    if not db_ok:
        logger.warning("startup: 数据库不可达，服务以 degraded 状态启动，/healthz 会如实报告")

    yield

    await dispose_engine()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Summer Checkin Service",
        version=settings.version,
        # 生产文档关闭：接口清单是内部信息，且 docs 页面会暴露全部路径。
        docs_url=None if not settings.auto_migrate else "/docs",
        redoc_url=None,
        openapi_url=None if not settings.auto_migrate else "/openapi.json",
        lifespan=lifespan,
    )
    # 中间件顺序：RequestContextMiddleware 在最外层，保证异常处理器也能拿到 request id。
    app.add_middleware(RequestContextMiddleware)
    register_exception_handlers(app)
    app.include_router(api_router)
    return app


app = create_app()
