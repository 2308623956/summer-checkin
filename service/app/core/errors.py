"""错误码与异常家族。

错误码清单是跨进程契约（`docs/tech/architecture.md` §7.1）：前端按 `code` 分支，
中文文案由前端映射。**码值是契约，改名等于破坏前端**。
"""

from __future__ import annotations

from enum import StrEnum


class ErrorCode(StrEnum):
    AUTH_REQUIRED = "AUTH_REQUIRED"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    CONFLICT = "CONFLICT"
    RATE_LIMITED = "RATE_LIMITED"
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
    UPSTREAM_FAILED = "UPSTREAM_FAILED"
    INTERNAL = "INTERNAL"


# 错误码 → HTTP 状态码。集中一处，避免同一个码在不同路由返回不同状态。
STATUS_BY_CODE: dict[ErrorCode, int] = {
    ErrorCode.AUTH_REQUIRED: 401,
    ErrorCode.FORBIDDEN: 403,
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.CONFLICT: 409,
    ErrorCode.VALIDATION_FAILED: 422,
    ErrorCode.RATE_LIMITED: 429,
    ErrorCode.QUOTA_EXCEEDED: 429,
    ErrorCode.UPSTREAM_FAILED: 502,
    ErrorCode.INTERNAL: 500,
}


class AppError(Exception):
    """业务错误基类。路由与服务层只管抛它，响应格式由异常处理器统一负责。"""

    code: ErrorCode = ErrorCode.INTERNAL
    # 默认文案面向用户；调用方可覆盖，但**不要把内部细节写进去**（会原样返回给前端）。
    message: str = "服务内部错误"

    def __init__(self, message: str | None = None) -> None:
        if message is not None:
            self.message = message
        super().__init__(self.message)

    @property
    def status_code(self) -> int:
        return STATUS_BY_CODE[self.code]


class AuthRequiredError(AppError):
    code = ErrorCode.AUTH_REQUIRED
    message = "请先登录"


class ForbiddenError(AppError):
    code = ErrorCode.FORBIDDEN
    message = "没有权限执行该操作"


class NotFoundError(AppError):
    code = ErrorCode.NOT_FOUND
    message = "资源不存在"


class ValidationFailedError(AppError):
    code = ErrorCode.VALIDATION_FAILED
    message = "请求参数不合法"


class ConflictError(AppError):
    code = ErrorCode.CONFLICT
    message = "状态已变化，请刷新后重试"


class RateLimitedError(AppError):
    code = ErrorCode.RATE_LIMITED
    message = "请求过于频繁，请稍后再试"


class QuotaExceededError(AppError):
    code = ErrorCode.QUOTA_EXCEEDED
    message = "今日额度已用完"


class UpstreamFailedError(AppError):
    code = ErrorCode.UPSTREAM_FAILED
    message = "上游服务暂时不可用"


class InternalError(AppError):
    code = ErrorCode.INTERNAL
    message = "服务内部错误"
