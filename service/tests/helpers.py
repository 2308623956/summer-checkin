"""测试辅助：常量、一次性密钥对、签发 token。

独立模块而不是放在 `conftest.py` 里，因为 `tests/` 不是包，测试文件无法相对导入。
`conftest.py` 也从这里取密钥，保证"签发用的私钥"与"验签用的公钥"是同一对。
"""

from __future__ import annotations

import time
from functools import lru_cache

import jwt

TEST_USER_ID = "01930000-0000-7000-8000-000000000001"
TEST_CRON_SECRET = "test-cron-secret-not-a-real-one"
TEST_DB_URL = "postgresql+asyncpg://tester:pw@127.0.0.1:5432/summer_checkin_test"


@lru_cache
def key_pair() -> tuple[str, str]:
    """一次性 RS256 密钥对（私钥, 公钥）。

    每次调用都生成 2048 位密钥很慢，所以缓存；但**只在测试进程内**存在，
    绝不写入文件或日志。
    """
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public = (
        key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    return private, public


def auth_header(user_id: str = TEST_USER_ID) -> dict[str, str]:
    """签一个真实 JWT，走真实验签路径。"""
    token = jwt.encode(
        {"sub": user_id, "email": "tester@example.com", "exp": int(time.time()) + 900},
        key_pair()[0],
        algorithm="RS256",
    )
    return {"Authorization": f"Bearer {token}"}


def expired_token() -> str:
    token = jwt.encode(
        {"sub": TEST_USER_ID, "exp": int(time.time()) - 10},
        key_pair()[0],
        algorithm="RS256",
    )
    return f"Bearer {token}"


def token_signed_by_another_key() -> str:
    """用另一对密钥签的 token：签名必须验不过。"""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    other_pem = other.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    token = jwt.encode(
        {"sub": TEST_USER_ID, "exp": int(time.time()) + 900},
        other_pem,
        algorithm="RS256",
    )
    return f"Bearer {token}"


def hs256_token_using_public_key_as_secret() -> str:
    """用**公钥文本**当 HMAC 密钥手搓一个 HS256 token。

    PyJWT 拒绝这样签名（它知道公钥不该当 HMAC 密钥），但攻击者不受这个限制：
    他可以自己拼。如果服务端验签时不限定算法，公钥这种公开信息就变成了签名密钥。
    所以这个 token 必须被手搓出来，否则测不到真正的攻击面。
    """
    import base64
    import hashlib
    import hmac
    import json

    def b64(raw: bytes) -> str:
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    header = b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = b64(json.dumps({"sub": TEST_USER_ID, "exp": int(time.time()) + 900}).encode())
    signing_input = f"{header}.{payload}".encode()
    signature = hmac.new(key_pair()[1].encode(), signing_input, hashlib.sha256).digest()
    return f"Bearer {header}.{payload}.{b64(signature)}"
