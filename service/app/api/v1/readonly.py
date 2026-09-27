"""占位读接口：让 15 个页面能渲染**空态**而不是白屏。

R000 的验收标准就是"页面显示空态"（`docs/PRD.md` §3.0.1），所以这几个接口返回合法信封 +
空数组即可。它们**不查数据库**——一旦开始查，就要连同过滤与分页一起做对，
那属于后续需求。到那时把实现换成真查询，契约（路径、信封形状）不变。
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.pagination import Page, page_params
from app.core.response import list_ok
from app.core.security import CurrentUser, get_current_user

router = APIRouter()


def _page(
    limit: Annotated[int | None, Query(ge=1, le=100)] = None,
    cursor: Annotated[str | None, Query()] = None,
) -> Page:
    return page_params(limit=limit, cursor=cursor)


@router.get("/checkins")
async def list_checkins(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    page: Annotated[Page, Depends(_page)],
) -> dict[str, object]:
    """打卡记录列表（R000：空实现）。"""
    return list_ok([], next_cursor=None)


@router.get("/plans")
async def list_plans(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    page: Annotated[Page, Depends(_page)],
) -> dict[str, object]:
    """学习计划列表（R000：空实现）。"""
    return list_ok([], next_cursor=None)


@router.get("/runs")
async def list_runs(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    page: Annotated[Page, Depends(_page)],
) -> dict[str, object]:
    """巡检运行列表（R000：空实现）。"""
    return list_ok([], next_cursor=None)


@router.get("/notifications")
async def list_notifications(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    page: Annotated[Page, Depends(_page)],
) -> dict[str, object]:
    """站内通知列表（R000：空实现）。"""
    return list_ok([], next_cursor=None)


@router.get("/stats/overview")
async def stats_overview(
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> dict[str, object]:
    """首页概览统计（R000：空实现）。

    空数据要给出**零值字段**而不是空对象：前端据此画"还没有数据"的引导，
    而不是在模板里对 `undefined` 做判断。
    """
    return {
        "data": {
            "streakDays": 0,
            "checkinCount": 0,
            "totalMinutes": 0,
            "completedTasks": 0,
            "pendingTasks": 0,
            "unreadNotifications": 0,
        }
    }
