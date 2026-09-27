"""系统类接口的请求/响应模型。

字段名与数据模型一致（snake_case 只用于数据库列；对外 JSON 用 camelCase，
与 `docs/tech/api/` 的契约一致）。放这里而不是散在路由文件里，
便于第 2 步"建 Pydantic 模型"有固定落点（`api/README.md` §9）。
"""

from __future__ import annotations

from pydantic import BaseModel


class HealthData(BaseModel):
    status: str
    version: str
    db: str
    uptime_s: int


class MetaFeatures(BaseModel):
    """功能开关。**前端不得硬编码开关**：`features` 里没有的键按 `false` 处理。

    R000 阶段全部为 false——功能还没实现。如实报 false 比报 true 让页面好看重要得多。
    """

    chatroom: bool
    resume_review: bool
    quiz_import: bool
    eval: bool


class MetaLimits(BaseModel):
    checkin_max_hours: int
    quiz_size_max: int
    agent_daily_tokens: int


class MetaQuota(BaseModel):
    """带凭据时才返回；不带凭据为 `null`（契约见 `api/01-system.md` §1.2）。"""

    used_tokens_today: int
    limit_tokens: int
    resets_at: str


class MetaData(BaseModel):
    version: str
    env: str
    api_version: str
    features: MetaFeatures
    limits: MetaLimits
    # R000 没有用量统计接口，带凭据时也暂为 None——不编造"今天用了 0 tokens"。
    quota: MetaQuota | None = None


class ExampleData(BaseModel):
    """`GET /example` 的响应体：按 `api/README.md` §9 的 5 步新增的样例接口。"""

    message: str
    userId: str
