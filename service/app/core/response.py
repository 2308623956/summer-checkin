"""统一响应信封。

成功 `{"data": …}`；列表 `{"data": [...], "meta": {"nextCursor": …}}`；
失败 `{"error": {"code", "message", "requestId"}}`（`docs/tech/architecture.md` §7.1）。

路由**不手工拼字典**，一律经过这里——否则总有一两个接口漏掉 `meta` 或写错字段名。
"""

from __future__ import annotations

from typing import Any


def ok(data: Any) -> dict[str, Any]:
    """单对象/字典信封。"""
    return {"data": data}


def list_ok(items: list[Any], next_cursor: str | None = None) -> dict[str, Any]:
    """列表信封。空列表也要带 `meta`，前端据此区分"没有数据"与"字段缺失"。"""
    return {"data": items, "meta": {"nextCursor": next_cursor}}


def error_body(code: str, message: str, request_id: str) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "requestId": request_id}}
