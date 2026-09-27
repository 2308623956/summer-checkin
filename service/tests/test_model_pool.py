"""模型池单测：全部走注入的假 client，不需要任何真实 API key。

覆盖四件事（`design.md` D10 的范围）：档位链、失败降级、限流/额度状态、记账旁路。
"""

from __future__ import annotations

import pytest

from app.llm.pool import (
    CHAINS,
    HIGH_CHAIN,
    LOW_CHAIN,
    ModelPool,
    ModelUnavailable,
    QuotaExhausted,
    RateLimited,
    Tier,
    UpstreamFailed,
    Usage,
)

PROMPT = "分析今天的打卡"


class FakeClient:
    """按脚本回应：`responses` 里每个模型对应一个结果（Usage 或要抛的异常）。"""

    def __init__(self, responses: dict[str, object] | None = None) -> None:
        self.responses = responses or {}
        self.calls: list[str] = []

    async def complete(self, *, model: str, prompt: str, tier: str) -> Usage:
        self.calls.append(model)
        result = self.responses.get(model)
        if result is None:
            return Usage(model=model, tier=tier, input_tokens=10, output_tokens=5)
        if isinstance(result, Exception):
            raise result
        assert isinstance(result, Usage)
        return result


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def test_chain_is_a_code_constant_not_config() -> None:
    """链是代码常量（integrations.md §2.1）：模型名进 .env 会带来静默降级故障。"""
    assert CHAINS[Tier.HIGH] is HIGH_CHAIN
    assert CHAINS[Tier.LOW] is LOW_CHAIN
    assert HIGH_CHAIN[0] == "agnes-2.5-flash"
    assert LOW_CHAIN[0] == "agnes-2.5-flash"


def test_model_names_are_full_snapshot_strings() -> None:
    """禁简写：简写会命中平台的最新别名，回归对比失去意义。"""
    for chain in CHAINS.values():
        for model in chain:
            assert model == model.strip()
            assert " " not in model
    assert "qwen3.8-max" in HIGH_CHAIN


async def test_uses_first_model_when_healthy() -> None:
    client = FakeClient()
    pool = ModelPool(client=client)
    usage = await pool.complete(tier=Tier.HIGH, prompt=PROMPT, surface="agent")
    assert usage.model == HIGH_CHAIN[0]
    assert client.calls == [HIGH_CHAIN[0]]


async def test_falls_back_to_next_model_on_failure() -> None:
    """第一个模型网络错误 → 换下一个，而不是把异常抛给用户。"""
    client = FakeClient({HIGH_CHAIN[0]: RuntimeError("connection reset")})
    pool = ModelPool(client=client)
    usage = await pool.complete(tier=Tier.HIGH, prompt=PROMPT, surface="agent")
    assert usage.model == HIGH_CHAIN[1]
    assert client.calls == [HIGH_CHAIN[0], HIGH_CHAIN[1]]


async def test_quota_exhausted_marks_model_permanently() -> None:
    """403 FreeTierOnly：额度不会自己回来，所以永久跳过。"""
    client = FakeClient({HIGH_CHAIN[0]: QuotaExhausted(HIGH_CHAIN[0], "FreeTierOnly")})
    pool = ModelPool(client=client)

    await pool.complete(tier=Tier.HIGH, prompt=PROMPT, surface="agent")
    assert HIGH_CHAIN[0] not in pool.available_models(Tier.HIGH)

    await pool.complete(tier=Tier.HIGH, prompt=PROMPT, surface="agent")
    # 第二次不该再试第一个模型。
    assert client.calls.count(HIGH_CHAIN[0]) == 1


async def test_rate_limited_model_recovers_after_cooldown() -> None:
    """429 是暂时的：冷却结束后必须重新可选，否则额度池会越用越小。"""
    clock = FakeClock()
    client = FakeClient({HIGH_CHAIN[0]: RateLimited(HIGH_CHAIN[0], "429")})
    pool = ModelPool(client=client, clock=clock)

    await pool.complete(tier=Tier.HIGH, prompt=PROMPT, surface="agent")
    assert HIGH_CHAIN[0] not in pool.available_models(Tier.HIGH)

    clock.advance(61)
    assert HIGH_CHAIN[0] in pool.available_models(Tier.HIGH)


async def test_cooldown_is_sixty_seconds_by_default() -> None:
    """默认冷却 60 秒（integrations.md §2.2）。"""
    clock = FakeClock()
    pool = ModelPool(client=FakeClient(), clock=clock)
    pool.mark_rate_limited("some-model")
    assert pool._state_for("some-model").rate_limited_until == pytest.approx(clock.now + 60)


async def test_custom_cooldown_is_honored() -> None:
    clock = FakeClock()
    pool = ModelPool(client=FakeClient(), clock=clock)
    pool.mark_rate_limited("some-model", cooldown_seconds=5)
    assert pool._state_for("some-model").rate_limited_until == pytest.approx(clock.now + 5)


async def test_all_models_failing_raises_upstream_failed() -> None:
    """全挂要抛 UpstreamFailed：调用方据此走规则兜底，而不是 500。"""
    client = FakeClient({model: RuntimeError("down") for model in HIGH_CHAIN})
    pool = ModelPool(client=client)
    with pytest.raises(UpstreamFailed):
        await pool.complete(tier=Tier.HIGH, prompt=PROMPT, surface="agent")
    assert client.calls == list(HIGH_CHAIN)


async def test_unavailable_error_subclass_is_treated_as_model_failure() -> None:
    client = FakeClient({HIGH_CHAIN[0]: ModelUnavailable(HIGH_CHAIN[0], "5xx")})
    pool = ModelPool(client=client)
    usage = await pool.complete(tier=Tier.HIGH, prompt=PROMPT, surface="agent")
    assert usage.model == HIGH_CHAIN[1]


async def test_low_tier_uses_low_chain() -> None:
    client = FakeClient()
    pool = ModelPool(client=client)
    usage = await pool.complete(tier=Tier.LOW, prompt="生成标题", surface="title")
    assert usage.model in LOW_CHAIN
    assert usage.tier == "LOW"


async def test_usage_has_total_tokens() -> None:
    usage = Usage(model="m", tier="HIGH", input_tokens=100, output_tokens=20)
    assert usage.total_tokens == 120


async def test_usage_is_recorded_on_success() -> None:
    recorded: list[tuple[Usage, str]] = []
    client = FakeClient()
    pool = ModelPool(client=client, record_usage=lambda u, s: recorded.append((u, s)))
    usage = await pool.complete(tier=Tier.HIGH, prompt=PROMPT, surface="agent")
    assert recorded == [(usage, "agent")]


async def test_recording_failure_does_not_break_the_call() -> None:
    """记账是旁路：写库失败不能把已经成功的模型调用变成失败。"""

    def boom(usage: Usage, surface: str) -> None:
        raise RuntimeError("tokenusage insert failed")

    pool = ModelPool(client=FakeClient(), record_usage=boom)
    usage = await pool.complete(tier=Tier.HIGH, prompt=PROMPT, surface="agent")
    assert usage.model == HIGH_CHAIN[0]


async def test_zero_token_usage_is_not_recorded() -> None:
    """`total_tokens <= 0` 不记账（integrations.md §2.3）。"""
    recorded: list[Usage] = []
    client = FakeClient(
        {HIGH_CHAIN[0]: Usage(model=HIGH_CHAIN[0], tier="HIGH", input_tokens=0, output_tokens=0)}
    )
    pool = ModelPool(client=client, record_usage=lambda u, s: recorded.append(u))
    await pool.complete(tier=Tier.HIGH, prompt=PROMPT, surface="agent")
    assert recorded == []


async def test_exhausted_everything_raises_upstream_failed() -> None:
    pool = ModelPool(client=FakeClient())
    for model in HIGH_CHAIN:
        pool.mark_exhausted(model)
    with pytest.raises(UpstreamFailed, match="没有可用模型"):
        await pool.complete(tier=Tier.HIGH, prompt=PROMPT, surface="agent")


async def test_only_used_models_are_marked_not_the_whole_chain() -> None:
    """一个模型挂了不该牵连其它模型——额度池是每个模型独立的。"""
    client = FakeClient({HIGH_CHAIN[0]: QuotaExhausted(HIGH_CHAIN[0], "FreeTierOnly")})
    pool = ModelPool(client=client)
    await pool.complete(tier=Tier.HIGH, prompt=PROMPT, surface="agent")
    assert set(pool.available_models(Tier.HIGH)) == set(HIGH_CHAIN[1:])
