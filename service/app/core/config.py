"""配置：全部来自环境变量，前缀 `SUMMER_`。

契约见 `docs/tech/integrations.md` §5.1。缺必需项**拒绝启动**，不允许静默降级——
"缺公钥就无鉴权放行"这类降级比启动失败危险得多。
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SUMMER_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- 必需 ---
    database_url: str = Field(description="PostgreSQL 连接串（asyncpg）")
    jwt_public_key: str = Field(description="校验 web 签发 JWT 的 RS256 公钥（PEM）")
    cron_secret: str = Field(description="POST /cron/daily 的 Bearer")

    # --- 可选（默认值即契约默认值）---
    # 环境名，/meta 会返回它，便于确认"这个实例连的是哪个环境"。
    env: str = "development"
    log_level: str = "info"
    tz: str = "Asia/Shanghai"
    schedule_cron: str = "0 21 * * *"
    ai_token_limit: int = 100_000
    agent_daily_tokens: int = 20_000
    daily_budget_usd: float = 3.0
    # 开发期自动迁移。生产固定 false：迁移失败会让服务起不来，且多实例会并发跑迁移。
    auto_migrate: bool = False
    prompt_version: str = "baseline@0.0.0"
    # 部署版本，/meta 会返回它，方便确认"线上跑的是哪个 sha"。
    version: str = "0.1.0"
    # 本地开发 rewrite 用；线上同域经 nginx，不需要。
    service_url: str = "http://127.0.0.1:8000"

    @field_validator("jwt_public_key")
    @classmethod
    def _normalize_public_key(cls, value: str) -> str:
        """环境变量里换行常被写成字面量 `\\n`，这里还原成真换行。

        PEM 少了换行会导致验签全部失败，而报错信息通常看不出是这个原因。
        """
        key = value.strip()
        if "\\n" in key:
            key = key.replace("\\n", "\n")
        return key

    @field_validator("database_url")
    @classmethod
    def _require_async_driver(cls, value: str) -> str:
        """必须是 asyncpg 驱动：同步驱动会在 async 代码里把事件循环堵死。"""
        if not value.startswith("postgresql+asyncpg://"):
            raise ValueError("SUMMER_DATABASE_URL 必须以 postgresql+asyncpg:// 开头")
        return value


@lru_cache
def get_settings() -> Settings:
    """进程内单例。测试里用 `get_settings.cache_clear()` 重置。"""
    return Settings()  # type: ignore[call-arg]  字段由环境变量提供
