"""结构化日志与请求上下文。

`X-Request-Id` 契约（`docs/tech/architecture.md` §7.4）：请求带则透传，无则生成；
响应头与日志、错误体三处都带同一个值，这样用户报错时贴一个 id 就能定位整条链路。
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Awaitable, Callable

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

REQUEST_ID_HEADER = "X-Request-Id"

logger = structlog.get_logger()


def configure_logging(level: str = "info") -> None:
    """JSON 输出：便于在同一处检索两个服务的日志。"""
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper(), logging.INFO),
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(ensure_ascii=False),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        cache_logger_on_first_use=True,
    )


def get_request_id(request: Request) -> str:
    """取当前请求的 id；中间件没跑到时返回空串（不该发生，但不值得抛异常）。"""
    return getattr(request.state, "request_id", "")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """给每个请求分配 request id，绑进日志上下文并写回响应头。"""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or _new_request_id()
        request.state.request_id = request_id

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )
        try:
            response = await call_next(request)
        finally:
            structlog.contextvars.clear_contextvars()

        response.headers[REQUEST_ID_HEADER] = request_id
        return response


def _new_request_id() -> str:
    from app.core.ids import uuid7

    return uuid7()
