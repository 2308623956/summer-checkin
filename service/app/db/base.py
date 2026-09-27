"""SQLAlchemy 声明基类与全局命名约定。

命名约定在这里集中定义：约束有确定的名字，Alembic autogenerate 才能可靠地比对
（匿名约束在反射时拿不到稳定标识，会被反复报成"新增/删除"）。
"""

from __future__ import annotations

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# 表名沿用参考实现：全小写、无下划线、单数（ADR-003）。
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """全部模型的基类。metadata 携带命名约定。"""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
