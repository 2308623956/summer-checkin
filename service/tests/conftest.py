"""测试夹具。

两条关键约束：

1. **测试库护栏**：碰数据库前断言库名以 `_test` 结尾。
2. **配置用测试值**，不读开发者本机的真实 `.env`——否则测试结果取决于谁的机器。

环境变量在**模块导入时**就设好：`app.main` 在模块级构造 `app`（供 `uvicorn app.main:app`
使用），而它在缺配置时会拒绝启动。生产环境这条 fail-fast 要保留，所以测试侧提前把配置
备好，而不是把校验放宽。

`client` 是**会话级**的：应用无状态，每个测试都建一次的话，启动时的数据库探测会重复执行
（本机 5432 未监听且丢包而非拒绝连接，每次要等满超时）。
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from tests.helpers import TEST_CRON_SECRET, TEST_DB_URL, key_pair

# 导入即生效：见模块 docstring。
os.environ.setdefault("SUMMER_DATABASE_URL", TEST_DB_URL)
os.environ.setdefault("SUMMER_JWT_PUBLIC_KEY", key_pair()[1])
os.environ.setdefault("SUMMER_CRON_SECRET", TEST_CRON_SECRET)
os.environ.setdefault("SUMMER_AUTO_MIGRATE", "false")
os.environ.setdefault("SUMMER_VERSION", "test")


@pytest.fixture(scope="session")
def client() -> Iterator[TestClient]:
    """不带数据库的 TestClient：`/healthz` 如实报 degraded，其余接口正常可用。"""
    from app.main import create_app

    app = create_app()
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def assert_is_test_database(url: str) -> None:
    from app.db.guard import assert_test_database

    assert_test_database(url, "pytest 夹具")


# 需要真实数据库的测试用这个跳过：R000 阶段不连库，它们应当被跳过而不是失败。
# 用法：SUMMER_TEST_DATABASE=1 uv run pytest（并先在 .env 填好 SUMMER_DATABASE_URL）。
requires_database = pytest.mark.skipif(
    os.environ.get("SUMMER_TEST_DATABASE") != "1",
    reason="需要真实测试库：设 SUMMER_TEST_DATABASE=1",
)
