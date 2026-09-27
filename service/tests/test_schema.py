"""Schema 基线测试：R000 的验收锚点 §10-5/6/7。

这里不连数据库：靠 `Base.metadata` 与迁移文件本身证明基线正确。
真库验收（`alembic upgrade head` → `check` → `downgrade base`）需要先填 `SUMMER_DATABASE_URL`。
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from pgvector.sqlalchemy import Vector
from sqlalchemy import UniqueConstraint

import app.models  # noqa: F401  导入即注册
from app.db.base import NAMING_CONVENTION, Base

MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "alembic" / "versions"
INITIAL = MIGRATIONS_DIR / "0001_initial.py"

# 31 张表的权威清单，逐条对应 docs/tech/data-model/（01 账号 5 + 02 学习 6 +
# 03 知识 4 + 04 agent 9 + 05 会话 3 + 06 用量与回归 4）。
EXPECTED_TABLES = {
    # 01
    "user",
    "session",
    "account",
    "verification",
    "avatarchange",
    # 02
    "plan",
    "plantask",
    "todo",
    "checkin",
    "studyrecord",
    "plantemplate",
    # 03
    "document",
    "documentchunk",
    "knowledgedoc",
    "documenttemplate",
    # 04
    "agentrun",
    "agentstep",
    "agentapproval",
    "agenttoolcall",
    "agentdecision",
    "agentschedule",
    "usermemory",
    "aihistory",
    "notification",
    # 05
    "conversation",
    "conversationmessage",
    "chatmessage",
    # 06
    "tokenusage",
    "evalfixture",
    "evalrun",
    "evalresult",
}

HNSW_INDEXES = {"documentchunk_embedding_hnsw", "usermemory_embedding_hnsw"}


def _migration_tree() -> ast.Module:
    return ast.parse(INITIAL.read_text(encoding="utf-8"))


def _op_calls(func_name: str, op_name: str) -> list[ast.Call]:
    """取出 upgrade()/downgrade() 里所有 `op.<op_name>(...)` 调用。"""
    calls: list[ast.Call] = []
    for node in ast.walk(_migration_tree()):
        if not isinstance(node, ast.FunctionDef) or node.name != func_name:
            continue
        for sub in ast.walk(node):
            if (
                isinstance(sub, ast.Call)
                and isinstance(sub.func, ast.Attribute)
                and sub.func.attr == op_name
            ):
                calls.append(sub)
    return calls


def test_table_count_is_31() -> None:
    assert len(Base.metadata.tables) == 31


def test_table_names_match_data_model() -> None:
    assert set(Base.metadata.tables) == EXPECTED_TABLES


def test_every_table_has_single_column_text_pk() -> None:
    """全库统一：text 主键、UUIDv7 由应用层生成（见 data-model/README.md）。"""
    for name, table in Base.metadata.tables.items():
        pk = list(table.primary_key.columns)
        assert len(pk) == 1, f"{name} 的主键不是单列"
        assert str(pk[0].type) == "TEXT", f"{name}.{pk[0].name} 不是 text"


def test_business_tables_have_user_id_index() -> None:
    """业务表按 user_id 过滤是常态，必须有以 user_id 开头的索引。

    例外都在各自的数据模型文档里写明，不是漏建：
    - `user`/`session`/`account`/`verification`：表结构由 Better Auth 自己的 schema 决定
      （`docs/tech/data-model/01-account.md`）；
    - `chatmessage`：不启用的表（ADR-002，没有任何代码读写），索引照参考实现保留
      （`05-conversation.md`）；
    - `plan`：**有意不建**——单用户下计划数是个位数，走 user_id 的全表扫描更省
      （`02-study.md`「索引：无额外索引」）。
    """
    exempt = {
        "user",
        "session",
        "account",
        "verification",
        "chatmessage",
        "plan",
    }
    for name, table in Base.metadata.tables.items():
        if name in exempt or "user_id" not in table.columns:
            continue
        indexed = any(idx.columns[0].name == "user_id" for idx in table.indexes)
        constrained = any(
            [c.name for c in con.columns][:1] == ["user_id"]
            for con in table.constraints
            if isinstance(con, UniqueConstraint)
        )
        assert indexed or constrained, f"{name}.user_id 没有以它开头的索引"


def test_user_foreign_keys_cascade() -> None:
    """用户注销时业务数据必须一起清掉，否则会留下查不到的孤儿行。

    例外：`chatmessage.user_id` 是 SET NULL——聊天室里允许匿名/系统消息
    （`docs/tech/data-model/05-conversation.md`）。
    """
    set_null_allowed = {"chatmessage"}
    for name, table in Base.metadata.tables.items():
        for fk in table.foreign_keys:
            if fk.target_fullname != "user.id" or fk.parent.name != "user_id":
                continue
            expected = "SET NULL" if name in set_null_allowed else "CASCADE"
            assert fk.ondelete == expected, f"{name}.user_id 的 ON DELETE 应为 {expected}"


def test_naming_convention_is_applied() -> None:
    assert Base.metadata.naming_convention == NAMING_CONVENTION
    # 约束都该拿到确定的名字，否则 autogenerate 会反复报漂移。
    for table in Base.metadata.tables.values():
        for constraint in table.constraints:
            assert constraint.name, f"{table.name} 有匿名约束"


def test_hnsw_indexes_declared_on_models() -> None:
    found = {
        idx.name: idx
        for table in Base.metadata.tables.values()
        for idx in table.indexes
        if idx.name in HNSW_INDEXES
    }
    assert set(found) == HNSW_INDEXES
    for idx in found.values():
        pg = idx.dialect_options["postgresql"]
        assert pg["using"] == "hnsw"
        assert pg["ops"]["embedding"] == "vector_cosine_ops"


def test_embedding_columns_are_1024_dimensional() -> None:
    """维度契约：链上任何 embedding 模型必须输出 1024 维，否则整条检索链报废。"""
    chunk = Base.metadata.tables["documentchunk"]
    assert isinstance(chunk.c.embedding.type, Vector)
    assert chunk.c.embedding.type.dim == 1024
    assert not chunk.c.embedding.nullable, "documentchunk.embedding 写入即生成，不应可空"

    memory = Base.metadata.tables["usermemory"]
    assert isinstance(memory.c.embedding.type, Vector)
    assert memory.c.embedding.type.dim == 1024
    assert memory.c.embedding.nullable, "usermemory.embedding 生成失败时留空，必须可空"


def test_migration_creates_exactly_the_documented_tables() -> None:
    created = {
        call.args[0].value
        for call in _op_calls("upgrade", "create_table")
        if call.args and isinstance(call.args[0], ast.Constant)
    }
    assert created == EXPECTED_TABLES


def test_migration_downgrade_is_symmetric() -> None:
    """upgrade 建的每张表都要在 downgrade 里被删掉，否则回退会留残骸。"""
    created = {
        call.args[0].value
        for call in _op_calls("upgrade", "create_table")
        if call.args and isinstance(call.args[0], ast.Constant)
    }
    dropped = {
        call.args[0].value
        for call in _op_calls("downgrade", "drop_table")
        if call.args and isinstance(call.args[0], ast.Constant)
    }
    assert created == dropped


def test_migration_creates_pgvector_extension() -> None:
    source = INITIAL.read_text(encoding="utf-8")
    assert "CREATE EXTENSION IF NOT EXISTS vector" in source


def test_migration_declares_both_hnsw_indexes() -> None:
    source = INITIAL.read_text(encoding="utf-8")
    assert source.count('postgresql_using="hnsw"') == 2
    for name in HNSW_INDEXES:
        assert name in source


def test_migration_chain_has_one_head() -> None:
    revisions: dict[str, str | None] = {}
    for path in sorted(MIGRATIONS_DIR.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        values: dict[str, object] = {}
        for node in tree.body:
            if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
                target = node.targets[0].id
                if target in {"revision", "down_revision"}:
                    values[target] = ast.literal_eval(node.value)
        assert "revision" in values, f"{path.name} 缺少 revision"
        revisions[str(values["revision"])] = values.get("down_revision")  # type: ignore[arg-type]

    referenced = {down for down in revisions.values() if down}
    heads = set(revisions) - referenced
    assert heads == {"0001_initial"}, f"迁移链 head 不唯一：{heads}"


def test_initial_migration_has_no_down_revision() -> None:
    tree = _migration_tree()
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == "down_revision"
        ):
            assert ast.literal_eval(node.value) is None
            return
    pytest.fail("0001_initial.py 没有声明 down_revision")
