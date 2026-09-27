"""认证与安全边界测试。

验签是 service 唯一的身份来源，所以这里测的是**攻击面**，不只是happy path：
无凭据、格式错的头、过期 token、别的密钥签的 token、算法混淆、跨用户读取。
"""

from __future__ import annotations

import time

import jwt
import pytest
from fastapi.testclient import TestClient

from app.core.errors import AuthRequiredError, ForbiddenError
from app.core.security import SERVICE_TOKEN_COOKIE, decode_token
from tests.helpers import (
    TEST_CRON_SECRET,
    TEST_JWT_SECRET,
    TEST_USER_ID,
    auth_header,
    expired_token,
    token_signed_by_another_key,
)

READONLY_PATHS = ["/checkins", "/plans", "/runs", "/notifications", "/stats/overview"]


@pytest.mark.parametrize("path", READONLY_PATHS)
def test_missing_credentials_returns_401_auth_required(client: TestClient, path: str) -> None:
    """`prd.md` §10 第 11 行：无凭据访问读接口必须是 401 AUTH_REQUIRED。"""
    response = client.get(f"/api/v1{path}")
    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "AUTH_REQUIRED"
    assert body["error"]["requestId"]


@pytest.mark.parametrize(
    "header",
    [
        "",
        "Bearer",
        "Bearer ",
        "Basic dXNlcjpwYXNz",
        "Token abc",
        "Bearer not-a-jwt-at-all",
        "Bearer a.b.c",
    ],
)
def test_malformed_authorization_header_is_rejected(client: TestClient, header: str) -> None:
    headers = {"Authorization": header} if header else {}
    response = client.get("/api/v1/checkins", headers=headers)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_REQUIRED"


def test_valid_token_is_accepted(client: TestClient) -> None:
    response = client.get("/api/v1/checkins", headers=auth_header())
    assert response.status_code == 200


def test_token_in_cookie_is_accepted(client: TestClient) -> None:
    """浏览器路径：web 把 JWT 写进 httpOnly cookie，浏览器自动带上（`architecture.md` §3.1）。"""
    token = auth_header()["Authorization"].removeprefix("Bearer ")
    response = client.get("/api/v1/checkins", cookies={SERVICE_TOKEN_COOKIE: token})
    assert response.status_code == 200


def test_expired_token_in_cookie_is_rejected(client: TestClient) -> None:
    token = expired_token().removeprefix("Bearer ")
    response = client.get("/api/v1/checkins", cookies={SERVICE_TOKEN_COOKIE: token})
    assert response.status_code == 401


def test_header_takes_priority_over_cookie(client: TestClient) -> None:
    """头优先：脚本与测试要能显式覆盖浏览器身份，而不用先清 cookie。"""
    from tests.helpers import TEST_USER_ID as _uid  # noqa: F401

    cookie_token = auth_header(TEST_USER_ID)["Authorization"].removeprefix("Bearer ")
    other = "01930000-0000-7000-8000-000000000002"
    response = client.get(
        "/api/v1/checkins",
        cookies={SERVICE_TOKEN_COOKIE: cookie_token},
        headers=auth_header(other),
    )
    assert response.status_code == 200


def test_other_cookie_is_not_accepted_as_credential(client: TestClient) -> None:
    """只有 service token 那个 cookie 算凭据，随便一个同名 cookie 不算。"""
    token = auth_header()["Authorization"].removeprefix("Bearer ")
    response = client.get("/api/v1/checkins", cookies={"better-auth.session_token": token})
    assert response.status_code == 401


def test_expired_token_is_rejected(client: TestClient) -> None:
    response = client.get("/api/v1/checkins", headers={"Authorization": expired_token()})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_REQUIRED"


def test_token_signed_by_another_key_is_rejected(client: TestClient) -> None:
    """这是最关键的一条：拿不到私钥就伪造不出可用 token。"""
    response = client.get(
        "/api/v1/checkins", headers={"Authorization": token_signed_by_another_key()}
    )
    assert response.status_code == 401


def test_token_without_subject_is_rejected(client: TestClient) -> None:
    token = jwt.encode({"exp": int(time.time()) + 900}, TEST_JWT_SECRET, algorithm="HS256")
    response = client.get("/api/v1/checkins", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_token_without_expiry_is_rejected(client: TestClient) -> None:
    """不过期的 token 等于永久凭据，必须拒绝（`options={"require": ["exp"]}`）。"""
    token = jwt.encode({"sub": TEST_USER_ID}, TEST_JWT_SECRET, algorithm="HS256")
    response = client.get("/api/v1/checkins", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_alg_none_token_is_rejected(client: TestClient) -> None:
    """算法混淆攻击：alg=none 的 token 必须被拒（显式限定 algorithms=["HS256"]）。"""
    token = jwt.encode({"sub": TEST_USER_ID, "exp": int(time.time()) + 900}, None, algorithm="none")
    response = client.get("/api/v1/checkins", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_decode_token_raises_auth_error_not_jwt_error() -> None:
    """业务代码只该看到 AppError 家族，不该被迫 import jwt 的异常。"""
    with pytest.raises(AuthRequiredError):
        decode_token("garbage", TEST_JWT_SECRET)


def test_cron_without_credentials_returns_403_forbidden(client: TestClient) -> None:
    """`prd.md` §10 第 12 行：cron 的凭据不对是 FORBIDDEN，不是 AUTH_REQUIRED。"""
    response = client.post("/api/v1/cron/daily")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_cron_with_wrong_secret_returns_403_forbidden(client: TestClient) -> None:
    response = client.post("/api/v1/cron/daily", headers={"Authorization": "Bearer wrong-secret"})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_cron_with_user_token_is_rejected(client: TestClient) -> None:
    """用户 JWT 不能当 cron 凭据用：两种调用方的权限不同，不能互相顶替。"""
    response = client.post("/api/v1/cron/daily", headers=auth_header())
    assert response.status_code == 403


def test_cron_secret_is_not_a_user_credential(client: TestClient) -> None:
    """反过来也一样：cron secret 不是用户身份，读接口不接受它。"""
    response = client.get(
        "/api/v1/checkins", headers={"Authorization": f"Bearer {TEST_CRON_SECRET}"}
    )
    assert response.status_code == 401


def test_forbidden_error_maps_to_403() -> None:
    assert ForbiddenError().status_code == 403
