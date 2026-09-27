"""JWT 验签与调用方识别。

三条不可动摇的规则（`docs/tech/architecture.md` §3.1）：

1. **service 只验签，不签发、不持有私钥**。私钥只在 web 侧，service 拿到私钥就等于
   任何人拿到私钥——签发权不扩散。
2. **拿不到公钥就拒绝启动**，不是"放行所有请求"。
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

ALGORITHM = "RS256"

# 与 web 侧 `src/app/api/service-token/route.ts` 的常量必须一致。
# 这是两个服务之间唯一共享的"名字"，改名要同时改两边。
SERVICE_TOKEN_COOKIE = "summer_service_jwt"

SettingsDep = Annotated[Settings, Depends(get_settings)]


@dataclass(frozen=True)
class CurrentUser:
    """一个通过验签的调用者。业务代码只依赖它，不直接碰 token。"""

    id: str
    email: str | None = None


def decode_token(token: str, public_key: str) -> dict[str, object]:
    """验签并解码。任何问题（过期、签名错、算法不符）都抛 AuthRequiredError。"""
    try:
        return jwt.decode(
            token,
            public_key,
            # 显式只允许 RS256：不写 algorithms 的话，攻击者可把 alg 改成 none 或 HS256，
            # 用公钥当 HMAC 密钥来伪造签名。
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
    payload = decode_token(token, settings.jwt_public_key)
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


def verify_public_key(public_key: str) -> None:
    """启动自检：公钥能用就通过，否则立刻失败——不要等第一个用户登录才发现配错了。

    只做"能否解析成 RS256 公钥"这一件事：生成一对临时密钥来跑完整验签会拖慢每次启动
    （2048 位密钥生成约 100ms），而它检验的是同一件事。
    """
    from cryptography.exceptions import UnsupportedAlgorithm
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives.serialization import load_pem_public_key

    try:
        loaded = load_pem_public_key(public_key.encode())
    except (ValueError, UnsupportedAlgorithm) as exc:
        raise RuntimeError(
            f"SUMMER_JWT_PUBLIC_KEY 不是合法的 PEM 公钥：{exc}。"
            "注意环境变量里的换行要写成 \\n，或使用多行值。"
        ) from exc

    if not isinstance(loaded, rsa.RSAPublicKey):
        raise RuntimeError(
            "SUMMER_JWT_PUBLIC_KEY 必须是 RSA 公钥（web 侧用 RS256 签发），"
            f"实际是 {type(loaded).__name__}"
        )
    if loaded.key_size < 2048:
        raise RuntimeError(f"SUMMER_JWT_PUBLIC_KEY 长度不足：{loaded.key_size} 位，至少 2048 位")
