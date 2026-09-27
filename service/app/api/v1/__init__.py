"""`/api/v1` 路由聚合。

路径前缀由这里统一加：nginx 按 `/api/v1/*` 分流到 service，
漏掉前缀的接口在线上会被交给 web（表现为 404），本地却因为直连端口而正常。
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import readonly, system

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(system.router, tags=["system"])
api_router.include_router(readonly.router, tags=["readonly"])
