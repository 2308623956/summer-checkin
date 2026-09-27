"""测试库护栏单测。

护栏失效的后果是"把生产库删了"，所以它的测试要覆盖三个关键判断：
非测试库拒绝、测试库放行、逃生开关放行。
"""

from __future__ import annotations

import pytest

from app.db.guard import (
    ALLOW_NON_TEST_DB_ENV,
    NonTestDatabaseError,
    assert_test_database,
    database_name,
)


def test_database_name_strips_query_params() -> None:
    assert database_name("postgresql+asyncpg://u:p@h:5432/summer_checkin_test") == (
        "summer_checkin_test"
    )
    assert database_name("postgresql+asyncpg://u:p@h:5432/db_test?sslmode=require") == "db_test"


def test_accepts_test_database() -> None:
    name = assert_test_database(
        "postgresql+asyncpg://u:p@127.0.0.1:5433/summer_checkin_test", "downgrade base"
    )
    assert name == "summer_checkin_test"


def test_rejects_production_database(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ALLOW_NON_TEST_DB_ENV, raising=False)
    with pytest.raises(NonTestDatabaseError, match="summer_checkin"):
        assert_test_database("postgresql+asyncpg://u:p@h:5432/summer_checkin", "downgrade base")


def test_rejects_database_without_suffix(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ALLOW_NON_TEST_DB_ENV, raising=False)
    with pytest.raises(NonTestDatabaseError):
        assert_test_database("postgresql+asyncpg://u:p@h:5432/mydb", "downgrade base")


def test_escape_hatch_allows_non_test_database(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ALLOW_NON_TEST_DB_ENV, "1")
    assert assert_test_database("postgresql+asyncpg://u:p@h:5432/summer_checkin", "downgrade base")


def test_escape_hatch_only_accepts_exactly_one(monkeypatch: pytest.MonkeyPatch) -> None:
    """`SUMMER_ALLOW_NON_TEST_DB=true` 之类的写法不算放行，必须是 "1"。"""
    monkeypatch.setenv(ALLOW_NON_TEST_DB_ENV, "true")
    with pytest.raises(NonTestDatabaseError):
        assert_test_database("postgresql+asyncpg://u:p@h:5432/summer_checkin", "downgrade base")
