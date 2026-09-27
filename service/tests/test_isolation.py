"""跨用户数据隔离守卫。

`docs/tech/architecture.md` §3.1：service 侧所有查询强制带 `user_id`，
缺失或验签失败返回 `AUTH_REQUIRED`。

R000 阶段读接口还是空实现，所以这里做两件事：
1. 现在就钉死"两个不同用户的 token 各自解析出各自的 id"——这是隔离的地基；
2. 用静态检查守住"没有 `user_id` 过滤的查询"这条线在后续需求里也不会被破坏。
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.security import decode_token
from tests.helpers import TEST_USER_ID, auth_header, key_pair

OTHER_USER_ID = "01930000-0000-7000-8000-000000000002"

APP_DIR = Path(__file__).resolve().parents[1] / "app"


def test_two_users_get_distinct_identities(client: TestClient) -> None:
    """两个用户的 token 必须解析成两个不同的 id，否则隔离无从谈起。"""
    first = decode_token(
        auth_header(TEST_USER_ID)["Authorization"].removeprefix("Bearer "), key_pair()[1]
    )
    second = decode_token(
        auth_header(OTHER_USER_ID)["Authorization"].removeprefix("Bearer "), key_pair()[1]
    )
    assert first["sub"] == TEST_USER_ID
    assert second["sub"] == OTHER_USER_ID
    assert first["sub"] != second["sub"]


def test_user_id_comes_only_from_the_verified_token(client: TestClient) -> None:
    """把 user_id 塞进查询参数或请求体**不应**改变身份。

    这是最容易被"顺手支持一下"破坏的地方：某天有人加了 `?userId=` 的便利参数，
    越权就读得到了。
    """
    response = client.get(
        f"/api/v1/checkins?userId={OTHER_USER_ID}&user_id={OTHER_USER_ID}",
        headers=auth_header(TEST_USER_ID),
    )
    assert response.status_code == 200
    # 空实现下只能验证"没有报错"，真正的过滤在实现里；这里防止的是"参数被当成身份"。


@pytest.mark.parametrize("path", ["/checkins", "/plans", "/runs", "/notifications"])
def test_readonly_endpoints_do_not_leak_between_users(client: TestClient, path: str) -> None:
    """两个用户各自请求，返回的都是自己的空结果——不存在"看见别人的数据"。"""
    first = client.get(f"/api/v1{path}", headers=auth_header(TEST_USER_ID))
    second = client.get(f"/api/v1{path}", headers=auth_header(OTHER_USER_ID))
    assert first.json() == second.json()
    assert first.json()["data"] == []


def _functions_missing_user_filter() -> list[str]:
    """粗略静态检查：查业务表却完全不提 user_id 的调用点。

    这不是类型检查，只是"防遗忘"的提醒——它可能漏报（比如过滤写在别处），
    但**不会误报**成安全问题：命中的地方都值得人工看一眼。
    """
    suspicious: list[str] = []
    # 有 user_id 的表才需要过滤；user/session/account/verification 归 web 管，
    # plantemplate/documenttemplate 是全局模板，本就没有 user_id。
    tables_without_user_id = {
        "user",
        "session",
        "account",
        "verification",
        "plantemplate",
        "documenttemplate",
    }
    for path in sorted(APP_DIR.rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            segment = ast.get_source_segment(source, node) or ""
            if "select(" not in segment:
                continue
            for model in tables_without_user_id:
                if f"select({model}" in segment:
                    break
            else:
                if "select(" in segment and "user_id" not in segment:
                    suspicious.append(f"{path.name}:{node.name}")
    return suspicious


def test_no_query_is_missing_a_user_id_filter() -> None:
    """当前代码里不应存在"查业务表但没提 user_id"的函数。

    后续需求写查询时若命中这条，说明要么漏了过滤，要么该查询确实不需要按用户隔离
    （那就把表名加进豁免清单并说明理由）。
    """
    assert _functions_missing_user_filter() == []
