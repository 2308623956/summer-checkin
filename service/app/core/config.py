"""配置：全部来自环境变量，前缀 `SUMMER_`。

契约见 `docs/tech/integrations.md` §5.1。缺必需项**拒绝启动**，不允许静默降级——
"缺公钥就无鉴权放行"这类降级比启动失败危险得多。
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

#: 仓库根。`.env` / `.env.local` 放这里，**两个服务读同一份**。
#: `app/core/config.py` → `app/core` → `app` → `service` → 仓库根。
REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SUMMER_",
        # 用绝对路径锚定仓库根：`env_file=".env"` 是相对**当前工作目录**的，
        # 从 service/ 启动只会找到 service/.env，从仓库根启动又换一个文件——
        # 同一份代码在不同目录下读到不同配置，是很难查的故障。
        # 注意顺序：先 .env.local（本地开发），后 .env（Docker/服务器）。
        # 文件不存在时 pydantic 静默忽略，所以两边都不会因为缺文件而报错。
        env_file=(str(REPO_ROOT / ".env.local"), str(REPO_ROOT / ".env")),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- 必需 ---
    # 标准 PostgreSQL URL，代码里自动转成 asyncpg 格式（见 async_database_url 属性）
    database_url: str = Field(description="PostgreSQL 连接串")
    jwt_secret: str = Field(description="JWT 签发与验签的对称密钥（HS256）")
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

    @property
    def async_database_url(self) -> str:
        """转换成 SQLAlchemy asyncpg 驱动格式。
        
        .env 里只维护标准格式 `postgresql://...`（与 web 的 Kysely 共用），
        service 用这个属性拿到 `postgresql+asyncpg://...` 格式。
        """
        if self.database_url.startswith("postgresql+asyncpg://"):
            return self.database_url
        return self.database_url.replace("postgresql://", "postgresql+asyncpg://", 1)


@lru_cache
def get_settings() -> Settings:
    """进程内单例。测试里用 `get_settings.cache_clear()` 重置。"""
    return Settings()  # type: ignore[call-arg]  字段由环境变量提供
