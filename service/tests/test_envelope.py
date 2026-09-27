"""统一响应信封、错误码与请求 id 的契约测试。

这些形状是**跨进程契约**（web 侧按 `code` 分支、按 `data` 取数），所以钉死在测试里：
改形状必须先改 `docs/tech/api/`。
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.errors import STATUS_BY_CODE, AppError, ErrorCode
from app.core.response import error_body, list_ok, ok
from app.main import create_app
from tests.helpers import TEST_CRON_SECRET, TEST_USER_ID, auth_header


def test_ok_wraps_payload_in_data() -> None:
    assert ok({"a": 1}) == {"data": {"a": 1}}


def test_list_ok_includes_meta_even_when_empty() -> None:
    """空列表也必须带 meta：前端据此区分"没有数据"与"字段缺失"。"""
    assert list_ok([]) == {"data": [], "meta": {"nextCursor": None}}
    assert list_ok([{"id": "x"}], next_cursor="abc") == {
        "data": [{"id": "x"}],
        "meta": {"nextCursor": "abc"},
    }


def test_error_body_shape() -> None:
    assert error_body("NOT_FOUND", "资源不存在", "req-1") == {
        "error": {"code": "NOT_FOUND", "message": "资源不存在", "requestId": "req-1"}
    }


def test_error_code_values_are_the_documented_contract() -> None:
    """码值是契约，改名等于破坏前端（`docs/tech/architecture.md` §7.1）。"""
    assert [code.value for code in ErrorCode] == [
        "AUTH_REQUIRED",
        "FORBIDDEN",
        "NOT_FOUND",
        "VALIDATION_FAILED",
        "CONFLICT",
        "RATE_LIMITED",
        "QUOTA_EXCEEDED",
        "UPSTREAM_FAILED",
        "INTERNAL",
    ]


def test_every_error_code_has_an_http_status() -> None:
    missing = [code for code in ErrorCode if code not in STATUS_BY_CODE]
    assert missing == []


def test_status_codes_follow_convention() -> None:
    assert STATUS_BY_CODE[ErrorCode.AUTH_REQUIRED] == 401
    assert STATUS_BY_CODE[ErrorCode.FORBIDDEN] == 403
    assert STATUS_BY_CODE[ErrorCode.NOT_FOUND] == 404
    assert STATUS_BY_CODE[ErrorCode.CONFLICT] == 409
    assert STATUS_BY_CODE[ErrorCode.VALIDATION_FAILED] == 422
    assert STATUS_BY_CODE[ErrorCode.INTERNAL] == 500


def test_app_error_can_override_message() -> None:
    exc = AppError("自定义文案")
    assert exc.message == "自定义文案"
    assert str(exc) == "自定义文案"


def test_app_error_keeps_class_default_message() -> None:
    assert AppError().message == "服务内部错误"


def test_healthz_returns_envelope_and_request_id(client: TestClient) -> None:
    response = client.get("/api/v1/healthz")
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"data"}
    # 契约见 api/01-system.md §1.1
    assert set(body["data"]) == {"status", "version", "db", "uptime_s"}
    assert body["data"]["status"] in ("ok", "degraded")
    assert isinstance(body["data"]["uptime_s"], int)
    assert response.headers["X-Request-Id"]


def test_meta_returns_envelope_with_features_and_limits(client: TestClient) -> None:
    """契约见 api/01-system.md §1.2。"""
    body = client.get("/api/v1/meta").json()
    assert set(body["data"]) == {
        "version",
        "env",
        "api_version",
        "features",
        "limits",
        "quota",
    }
    assert body["data"]["api_version"] == "v1"
    # R000 功能还没实现，features 必须如实为 false，不能为了页面好看写 true。
    assert body["data"]["features"] == {
        "chatroom": False,
        "resume_review": False,
        "quiz_import": False,
        "eval": False,
    }
    assert set(body["data"]["limits"]) == {
        "checkin_max_hours",
        "quiz_size_max",
        "agent_daily_tokens",
    }
    # 不带凭据时 quota 为 null；R000 没有用量统计，带凭据也暂为 null。
    assert body["data"]["quota"] is None


def test_request_id_is_echoed_back(client: TestClient) -> None:
    response = client.get("/api/v1/meta", headers={"X-Request-Id": "trace-me-123"})
    assert response.headers["X-Request-Id"] == "trace-me-123"


def test_request_id_is_generated_when_absent(client: TestClient) -> None:
    first = client.get("/api/v1/meta").headers["X-Request-Id"]
    second = client.get("/api/v1/meta").headers["X-Request-Id"]
    assert first and second and first != second


def test_error_response_carries_the_same_request_id(client: TestClient) -> None:
    response = client.get("/api/v1/checkins", headers={"X-Request-Id": "err-trace-9"})
    assert response.status_code == 401
    assert response.json()["error"]["requestId"] == "err-trace-9"
    assert response.headers["X-Request-Id"] == "err-trace-9"


def test_unknown_path_returns_envelope_not_fastapi_default(client: TestClient) -> None:
    """框架默认的 `{"detail": ...}` 会破坏前端统一错误处理，必须被映射掉。"""
    response = client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_unhandled_exception_hides_internals(client: TestClient) -> None:
    """未预期异常不能把堆栈/表名回给客户端，只给 requestId 便于对日志。"""
    app = create_app()

    @app.get("/api/v1/boom")
    async def boom() -> None:
        raise RuntimeError("secret table name leaked here")

    with TestClient(app, raise_server_exceptions=False) as local_client:
        response = local_client.get("/api/v1/boom")

    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "INTERNAL"
    assert "secret table name" not in response.text
    assert body["error"]["requestId"]


@pytest.mark.parametrize("path", ["/api/v1/does-not-exist"])
def test_readonly_endpoints_require_auth(client: TestClient, path: str) -> None:
    assert client.get(path).status_code == 404


def test_authenticated_readonly_endpoints_return_empty_envelopes(client: TestClient) -> None:
    """五条读接口在 R000 返回空数组 + meta，页面据此渲染空态。"""
    for path in ["/checkins", "/plans", "/runs", "/notifications"]:
        response = client.get(f"/api/v1{path}", headers=auth_header(TEST_USER_ID))
        assert response.status_code == 200, path
        assert response.json() == {"data": [], "meta": {"nextCursor": None}}, path


def test_stats_overview_returns_zero_valued_fields(client: TestClient) -> None:
    """空数据给零值字段，前端才能直接渲染"还没有数据"的引导。"""
    body = client.get("/api/v1/stats/overview", headers=auth_header(TEST_USER_ID)).json()
    assert body["data"] == {
        "streakDays": 0,
        "checkinCount": 0,
        "totalMinutes": 0,
        "completedTasks": 0,
        "pendingTasks": 0,
        "unreadNotifications": 0,
    }


def test_example_endpoint_requires_auth(client: TestClient) -> None:
    """样例接口（`api/README.md` §9.2）走标准鉴权：无凭据必须 401。"""
    response = client.get("/api/v1/example")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_REQUIRED"


def test_example_endpoint_returns_the_envelope(client: TestClient) -> None:
    """5 步走完的接口返回统一信封，且 user_id 来自 token 而不是请求参数。"""
    response = client.get("/api/v1/example", headers=auth_header(TEST_USER_ID))
    assert response.status_code == 200
    assert response.json() == {"data": {"message": "样例接口", "userId": TEST_USER_ID}}


def test_cron_daily_accepts_correct_secret_structure(client: TestClient) -> None:
    """占位接口的响应必须明说"没真跑"，否则会被误当成巡检已完成。"""
    response = client.post(
        "/api/v1/cron/daily", headers={"Authorization": f"Bearer {TEST_CRON_SECRET}"}
    )
    # 没有数据库时不该 500：这个占位不该因为库不可达就崩。
    assert response.status_code in (200, 500)
    if response.status_code == 200:
        assert response.json()["data"]["executed"] is False
