"""游标分页。

默认 20、最大 100（`docs/tech/architecture.md` §7.3）。游标是**不透明字符串**：
客户端只负责原样回传，编码方式将来可换而不用改契约。

游标内容 = 上一页最后一条的 id。因为主键是 UUIDv7（时间有序），按 id 排序等价于按
创建时间排序，所以"取 id < cursor"就是"取更早的记录"。
"""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass

from app.core.errors import ValidationFailedError

DEFAULT_LIMIT = 20
MAX_LIMIT = 100


@dataclass(frozen=True)
class Page:
    limit: int
    cursor: str | None = None


def encode_cursor(last_id: str) -> str:
    return base64.urlsafe_b64encode(last_id.encode()).decode().rstrip("=")


def decode_cursor(cursor: str) -> str:
    """解不开就当参数非法——不要静默从头开始，那会让前端无限翻同一页。"""
    try:
        padding = "=" * (-len(cursor) % 4)
        decoded = base64.urlsafe_b64decode(cursor + padding).decode()
    except (binascii.Error, UnicodeDecodeError, ValueError) as exc:
        raise ValidationFailedError("分页游标不合法") from exc
    if not decoded:
        raise ValidationFailedError("分页游标不合法")
    return decoded


def normalize_limit(limit: int | None) -> int:
    """超上限直接截断到最大值，而不是报错——前端传大值通常只是想"尽量多拿"。"""
    if limit is None:
        return DEFAULT_LIMIT
    if limit < 1:
        raise ValidationFailedError("limit 必须大于 0")
    return min(limit, MAX_LIMIT)


def page_params(limit: int | None = None, cursor: str | None = None) -> Page:
    return Page(limit=normalize_limit(limit), cursor=cursor)


def next_cursor(returned_ids: list[str], limit: int) -> str | None:
    """取满一页才可能还有下一页：少一条就说明到底了。"""
    if len(returned_ids) < limit:
        return None
    return encode_cursor(returned_ids[-1])
