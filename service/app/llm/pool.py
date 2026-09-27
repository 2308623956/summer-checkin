"""模型池最小切片：档位链、失败降级、限流冷却、记账。

范围严格限制在四件事上（见任务 `design.md` D10）：**档位链 + 降级 + 限流冷却 + 记账**。
不碰 rerank、不碰 embedding、不碰流式——那些等真正用到它们的需求再做。

设计要点：

- **链是代码常量**，不进环境变量（`docs/tech/integrations.md` §2.1）：把模型名放进 `.env`
  只会带来"配错一个名字 → 静默降级到最弱模型"的故障。
- 客户端通过构造注入，所以整个降级逻辑可以用假 client 单测，不需要真实 API key。
- 记账是**旁路**：`total_tokens <= 0` 或写库失败都不阻断主流程。
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol

import structlog

logger = structlog.get_logger()


class Tier(StrEnum):
    HIGH = "HIGH"
    LOW = "LOW"


# 档位链。模型名必须是**完整快照字符串**（如 `qwen3.8-max`），禁止简写：
# 简写会命中平台的最新别名，回归对比直接失去意义（integrations.md §2.1 第 3 条）。
HIGH_CHAIN: tuple[str, ...] = (
    "agnes-2.5-flash",
    "qwen3.8-max",
    "qwen3.8-plus",
    "deepseek-v3.2",
    "kimi-k2.5",
    "glm-5",
)
LOW_CHAIN: tuple[str, ...] = (
    "agnes-2.5-flash",
    "qwen-flash",
    "qwen3.5-flash",
    "qwen-turbo",
)

CHAINS: dict[Tier, tuple[str, ...]] = {Tier.HIGH: HIGH_CHAIN, Tier.LOW: LOW_CHAIN}


class ModelUnavailable(Exception):
    """该模型本次不可用。带上原因，便于日志与统计区分。"""

    def __init__(self, model: str, reason: str) -> None:
        self.model = model
        self.reason = reason
        super().__init__(f"{model}: {reason}")


class QuotaExhausted(ModelUnavailable):
    """免费额度用尽（403 `AllocationQuota.FreeTierOnly`）→ 本轮之后**永久跳过**。"""


class RateLimited(ModelUnavailable):
    """限流（429）→ 冷却期内不选它，冷却结束自动恢复。"""


class UpstreamFailed(Exception):
    """链上全部模型都不可用。调用方据此走规则兜底，而不是把 500 抛给用户。"""


@dataclass
class Usage:
    model: str
    tier: str
    input_tokens: int
    output_tokens: int

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class LLMClient(Protocol):
    """模型池依赖的最小接口。真实实现走 httpx；测试里注入假实现。"""

    async def complete(self, *, model: str, prompt: str, tier: str) -> Usage: ...


@dataclass
class _ModelState:
    exhausted: bool = False
    rate_limited_until: float = 0.0


@dataclass
class ModelPool:
    """按档位链选模型，失败就降级，并记录用量。"""

    client: LLMClient
    # 记账回调：写 tokenusage。传 None 表示不记账（测试或不需要账本的场景）。
    record_usage: Callable[[Usage, str], None] | None = None
    # 时钟可注入：冷却逻辑的测试不该真的 sleep 60 秒。
    clock: Callable[[], float] = time.monotonic
    _state: dict[str, _ModelState] = field(default_factory=dict)

    def _state_for(self, model: str) -> _ModelState:
        return self._state.setdefault(model, _ModelState())

    def available_models(self, tier: Tier) -> list[str]:
        """当前可选的模型，按链顺序。"""
        now = self.clock()
        return [
            model
            for model in CHAINS[tier]
            if not self._state_for(model).exhausted
            and self._state_for(model).rate_limited_until <= now
        ]

    def mark_rate_limited(self, model: str, cooldown_seconds: float = 60.0) -> None:
        """429 之后冷却一段时间（实测语义：限流是暂时的）。"""
        self._state_for(model).rate_limited_until = self.clock() + cooldown_seconds

    def mark_exhausted(self, model: str) -> None:
        """免费额度用尽：**永久跳过**，因为额度不会自己回来。"""
        self._state_for(model).exhausted = True

    async def complete(self, *, tier: Tier, prompt: str, surface: str) -> Usage:
        """按链尝试。全挂抛 `UpstreamFailed`，由调用方决定规则兜底。"""
        candidates = self.available_models(tier)
        if not candidates:
            raise UpstreamFailed(f"{tier} 档位链上当前没有可用模型")

        last_error: Exception | None = None
        for model in candidates:
            try:
                usage = await self.client.complete(model=model, prompt=prompt, tier=tier.value)
            except QuotaExhausted as exc:
                logger.warning("model quota exhausted", model=model, reason=exc.reason)
                self.mark_exhausted(model)
                last_error = exc
            except RateLimited as exc:
                logger.warning("model rate limited", model=model, reason=exc.reason)
                self.mark_rate_limited(model)
                last_error = exc
            except ModelUnavailable as exc:
                logger.warning("model unavailable", model=model, reason=exc.reason)
                last_error = exc
            except Exception as exc:  # 网络类错误：换下一个，不终止整条链
                logger.warning("model call failed", model=model, error=str(exc))
                last_error = exc
            else:
                self._record(usage, surface)
                return usage

        raise UpstreamFailed(f"{tier} 档位链全部不可用：{last_error}") from last_error

    def _record(self, usage: Usage, surface: str) -> None:
        """记账是旁路：写失败只记日志，绝不让主流程失败（integrations.md §2.3）。"""
        if self.record_usage is None:
            return
        if usage.total_tokens <= 0:
            logger.warning("skip usage record: non-positive tokens", model=usage.model)
            return
        try:
            self.record_usage(usage, surface)
        except Exception as exc:
            logger.error("usage record failed", model=usage.model, error=str(exc))
