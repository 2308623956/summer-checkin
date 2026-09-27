"""主键生成：UUIDv7（时间有序）。

为什么不是自增：id 由应用层生成才能在插入前就知道它（写审计行、拼幂等键都要用）。
为什么不是 UUIDv4：随机值让 btree 插入页分裂，且无法按时间排序。
"""

from __future__ import annotations

import os
import time
import uuid


def uuid7() -> str:
    """返回 36 字符的 UUIDv7 字符串。

    布局（RFC 9562）：48 位毫秒时间戳 | 4 位版本(7) | 12 位随机 | 2 位变体 | 62 位随机。
    """
    timestamp_ms = time.time_ns() // 1_000_000
    rand_a = int.from_bytes(os.urandom(2), "big") & 0x0FFF
    rand_b = int.from_bytes(os.urandom(8), "big") & 0x3FFF_FFFF_FFFF_FFFF

    value = (timestamp_ms & 0xFFFF_FFFF_FFFF) << 80
    value |= 0x7 << 76
    value |= rand_a << 64
    value |= 0b10 << 62
    value |= rand_b
    return str(uuid.UUID(int=value))


def uuid7_timestamp_ms(value: str) -> int:
    """取回时间戳（毫秒）。用于测试与"按 id 排序即按时间排序"的验证。"""
    return uuid.UUID(value).int >> 80
