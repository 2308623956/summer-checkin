"""异常处理器与请求校验错误映射。

全部出口都走统一信封（`app/core/response.py`）。这里集中兜底，路由里不要写 try/except。
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.errors import AppError, ErrorCode
from app.core.logging import get_request_id
from app.core.response import error_body

logger = structlog.get_logger()

# 框架自带的 HTTPException 用状态码表达，这里映射回我们的错误码，避免出现两种风格。
CODE_BY_STATUS: dict[int, ErrorCode] = {
    400: ErrorCode.VALIDATION_FAILED,
    401: ErrorCode.AUTH_REQUIRED,
    403: ErrorCode.FORBIDDEN,
    404: ErrorCode.NOT_FOUND,
    405: ErrorCode.VALIDATION_FAILED,
    409: ErrorCode.CONFLICT,
    429: ErrorCode.RATE_LIMITED,
}


def _json(status: int, code: str, message: str, request_id: str) -> JSONResponse:
    return JSONResponse(status_code=status, content=error_body(code, message, request_id))


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> JSONResponse:
        request_id = get_request_id(request)
        # 5xx 才记 error 级：业务错误（401/404 等）是正常流量，刷日志会淹没真问题。
        log = logger.error if exc.status_code >= 500 else logger.info
        log("request failed", code=exc.code.value, message=exc.message, status=exc.status_code)
        return _json(exc.status_code, exc.code.value, exc.message, request_id)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return _json(
            422,
            ErrorCode.VALIDATION_FAILED.value,
            _readable_validation_message(exc),
            get_request_id(request),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = CODE_BY_STATUS.get(exc.status_code, ErrorCode.INTERNAL)
        detail = exc.detail if isinstance(exc.detail, str) else code.value
        return _json(exc.status_code, code.value, detail, get_request_id(request))

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        request_id = get_request_id(request)
        # 未预期异常记完整堆栈，但只把 requestId 回给客户端：
        # 堆栈里的表名、路径、SQL 片段不该出现在响应体里。
        logger.exception("unhandled error", error=str(exc))
        return _json(500, ErrorCode.INTERNAL.value, "服务内部错误", request_id)


def _readable_validation_message(exc: RequestValidationError) -> str:
    """把 pydantic 的错误压成一句人话：前端只用它做兜底展示，按字段提示由前端自己校验。"""
    errors: list[dict[str, Any]] = exc.errors()
    if not errors:
        return "请求参数不合法"
    first = errors[0]
    location = ".".join(str(part) for part in first.get("loc", ()) if part != "body")
    message = first.get("msg", "不合法")
    return f"{location}: {message}" if location else str(message)
