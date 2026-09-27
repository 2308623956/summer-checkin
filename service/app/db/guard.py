"""测试库护栏。

破坏性数据库操作（`downgrade base`、清库重建）只允许打在库名以 `_test` 结尾的库上。
本地开发连的是数据库服务器上的库，跑错库等于删库——这条不接受"我知道我在做什么"式的绕过。

用在两处（见任务 `design.md` D7）：Alembic 的 `downgrade` 前置，以及 pytest 夹具。
"""

from __future__ import annotations

import os

TEST_DB_SUFFIX = "_test"
# 逃生开关：CI 里库名不一定带 _test 时显式设置，属于有意的例外，不是绕过。
ALLOW_NON_TEST_DB_ENV = "SUMMER_ALLOW_NON_TEST_DB"


class NonTestDatabaseError(RuntimeError):
    """目标库不是测试库，拒绝执行破坏性操作。"""


def database_name(url: str) -> str:
    """从连接串取出库名（去掉查询参数）。"""
    return url.rsplit("/", 1)[-1].split("?", 1)[0]


def assert_test_database(url: str, action: str) -> str:
    """通过则返回库名，否则抛 `NonTestDatabaseError`。"""
    name = database_name(url)
    if name.endswith(TEST_DB_SUFFIX):
        return name
    if os.environ.get(ALLOW_NON_TEST_DB_ENV) == "1":
        return name
    raise NonTestDatabaseError(
        f"拒绝在库 {name!r} 上执行 {action}：库名不以 {TEST_DB_SUFFIX!r} 结尾。"
        f"确认它确实是测试库后，可设 {ALLOW_NON_TEST_DB_ENV}=1 放行。"
    )
