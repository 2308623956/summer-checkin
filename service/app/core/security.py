"""JWT 验签与调用方识别。

三条不可动摇的规则（`docs/tech/architecture.md` §3.1）：

1. **对称密钥 HS256**：web 和 service 共用 `JWT_SECRET`，签发与验签都用同一密钥。
2. **拿不到密钥就拒绝启动**，不是"放行所有请求"。
3. `user_id` 只从验签通过的 token 里取，**绝不从请求体或查询参数取**。
"""

from __future__ import annotations

import hmac
from dataclasses import dataclass
from typing import Annotated

import jwt
from fastapi import Depends, Request

from app.core.config import Settings, get_settings
from app.core.errors import AuthRequiredError, ForbiddenError

ALGORITHM = "HS256"

# 与 web 侧 `src/app/api/service-token/route.ts` 的常量必须一致。
# 这是两个服务之间唯一共享的"名字"，改名要同时改两边。
SERVICE_TOKEN_COOKIE = "summer_service_jwt"

SettingsDep = Annotated[Settings, Depends(get_settings)]


@dataclass(frozen=True)
class CurrentUser:
    """一个通过验签的调用者。业务代码只依赖它，不直接碰 token。"""

    id: str
    email: str | None = None


def decode_token(token: str, secret: str) -> dict[str, object]:
    """验签并解码。任何问题（过期、签名错、算法不符）都抛 AuthRequiredError。"""
    try:
        return jwt.decode(
            token,
            secret,
            # 显式只允许 HS256：不写 algorithms 的话，攻击者可把 alg 改成 none。
            algorithms=[ALGORITHM],
            options={"require": ["exp", "sub"]},
        )
    except jwt.PyJWTError as exc:
        # 不把底层原因（"签名不匹配"/"已过期"）回给客户端：那是给攻击者的提示。
        raise AuthRequiredError("登录状态无效，请重新登录") from exc


def _extract_bearer(request: Request) -> str | None:
    header = request.headers.get("Authorization")
    if not header:
        return None
    scheme, _, credentials = header.partition(" ")
    if scheme.lower() != "bearer" or not credentials.strip():
        return None
    return credentials.strip()


def _extract_user_token(request: Request) -> str | None:
    """浏览器走 httpOnly cookie，CLI/CI 走 Authorization 头（`architecture.md` §3.1）。

    **头优先**：同一个请求同时带两者时以头为准，这样脚本与测试可以显式覆盖浏览器身份，
    而不用先想办法清掉 cookie。
    """
    token = _extract_bearer(request)
    if token is not None:
        return token
    return request.cookies.get(SERVICE_TOKEN_COOKIE)


async def get_current_user(request: Request, settings: SettingsDep) -> CurrentUser:
    """浏览器与 CLI 共用的调用方识别。"""
    token = _extract_user_token(request)
    if token is None:
        raise AuthRequiredError()
    payload = decode_token(token, settings.jwt_secret)
    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject:
        raise AuthRequiredError("登录状态无效，请重新登录")
    email = payload.get("email")
    return CurrentUser(id=subject, email=email if isinstance(email, str) else None)


async def require_cron_secret(request: Request, settings: SettingsDep) -> None:
    """定时任务调用方：`Authorization: Bearer <CRON_SECRET>`。

    用 `compare_digest` 做定时安全比较——普通 `==` 会因提前返回而泄漏前缀。
    """
    token = _extract_bearer(request)
    if token is None or not hmac.compare_digest(token, settings.cron_secret):
        # 这里回 FORBIDDEN 而不是 AUTH_REQUIRED：它不是在说"请登录"，
        # 而是在说"这个凭据不对"（`prd.md` §10 第 12 行的期望）。
        raise ForbiddenError("凭据无效")
