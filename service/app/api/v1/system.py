"""系统类接口：`/healthz`、`/meta`、`/example`、`/cron/daily`。

`/healthz` 与 `/meta` 是**真实现**：前者含数据库探测，后者是前端启动时拿限额与
feature flags 的地方。`/example` 是按 `api/README.md` §9 的 5 步新增的样例接口。
`/cron/daily` 是占位——R000 只到"找到期用户 → 排一条 queued run"，不跑分析（R005 才做）。
"""

from __future__ import annotations

import time
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy import func, select

from app.core.config import Settings, get_settings
from app.core.ids import uuid7
from app.core.response import ok
from app.core.security import CurrentUser, get_current_user, require_cron_secret
from app.db.session import get_engine, get_session_factory, ping
from app.models.agent import AgentRun, AgentSchedule
from app.schemas.system import ExampleData, HealthData, MetaData, MetaFeatures, MetaLimits

logger = structlog.get_logger()
router = APIRouter()

# 进程启动时刻。`time.monotonic` 不受系统时钟调整影响，算存活时长更稳。
_STARTED_AT = time.monotonic()


@router.get("/healthz")
async def healthz(settings: Annotated[Settings, Depends(get_settings)]) -> dict[str, object]:
    """就绪探针。数据库连不上时返回 `degraded` 而**不是** 500——
    编排系统据此重启容器，而 500 会让它误以为进程本身坏了。"""
    try:
        db_ok = await ping(get_engine())
    except RuntimeError:
        # 引擎还没建起来（启动自检已经把缺配置挡在前面了），如实报 degraded。
        db_ok = False

    return ok(
        HealthData(
            status="ok" if db_ok else "degraded",
            version=settings.version,
            db="ok" if db_ok else "down",
            uptime_s=int(time.monotonic() - _STARTED_AT),
        ).model_dump()
    )


@router.get("/example")
async def example(user: Annotated[CurrentUser, Depends(get_current_user)]) -> dict[str, object]:
    """按 `docs/tech/api/README.md` §9 的 5 步新增的样例接口。

    它存在的意义是**证明那份文档可照着执行**，所以刻意保持最小：
    鉴权 → 组装 → 包装信封，没有业务逻辑，也没有数据库访问。
    """
    return ok(ExampleData(message="样例接口", userId=user.id).model_dump())


@router.get("/meta")
async def meta(settings: Annotated[Settings, Depends(get_settings)]) -> dict[str, object]:
    """版本与功能开关。前端顶栏显示版本，功能开关决定入口显隐。

    `quota` 需要查 `tokenusage`，属于用量统计需求；R000 返回 `null` 而不是编造 0。
    """
    data = MetaData(
        version=settings.version,
        env=settings.env,
        api_version="v1",
        features=MetaFeatures(
            chatroom=False,  # 聊天室不迁移（ADR-002）
            resume_review=False,
            quiz_import=False,
            eval=False,
        ),
        limits=MetaLimits(
            checkin_max_hours=24,
            quiz_size_max=20,
            agent_daily_tokens=settings.agent_daily_tokens,
        ),
        quota=None,
    )
    return ok(data.model_dump())


@router.post("/cron/daily", dependencies=[Depends(require_cron_secret)])
async def cron_daily(
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, object]:
    """占位：给到期的巡检计划各排一条 `queued` run；不执行分析。

    定时任务由外部 cron / 平台调度每天打这个接口（而不是在进程里养一个调度器），
    这样单 worker 与将来的多实例行为一致。
    """
    async with get_session_factory()() as session:
        due_user_ids = (
            (
                await session.execute(
                    select(AgentSchedule.user_id).where(
                        AgentSchedule.enabled.is_(True),
                        AgentSchedule.next_run_at.is_not(None),
                        AgentSchedule.next_run_at <= func.now(),
                    )
                )
            )
            .scalars()
            .all()
        )

        for user_id in due_user_ids:
            session.add(
                AgentRun(
                    id=uuid7(),
                    user_id=user_id,
                    goal="每日巡检",
                    status="queued",
                    model=None,
                    prompt_version=settings.prompt_version,
                )
            )
        await session.commit()
        queued = len(due_user_ids)

    logger.info("cron daily placeholder executed", queued=queued)
    # 明确告诉调用方"只是排了队，没有真跑"，避免被误当成巡检已完成。
    return ok({"queued": queued, "executed": False, "note": "R000 占位：只排队，不执行分析"})
