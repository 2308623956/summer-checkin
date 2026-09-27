"""测试辅助：常量、测试密钥、签发 token。

独立模块而不是放在 `conftest.py` 里，因为 `tests/` 不是包，测试文件无法相对导入。
`conftest.py` 也从这里取密钥，保证"签发用的密钥"与"验签用的密钥"是同一个。
"""

from __future__ import annotations

import time

import jwt

TEST_USER_ID = "01930000-0000-7000-8000-000000000001"
TEST_CRON_SECRET = "test-cron-secret-not-a-real-one"
TEST_DB_URL = "postgresql+asyncpg://tester:pw@127.0.0.1:5432/summer_checkin_test"
TEST_JWT_SECRET = "test-jwt-secret-for-hs256-at-least-32-chars-long"


def auth_header(user_id: str = TEST_USER_ID) -> dict[str, str]:
    """签一个真实 JWT，走真实验签路径。"""
    token = jwt.encode(
        {"sub": user_id, "email": "tester@example.com", "exp": int(time.time()) + 900},
        TEST_JWT_SECRET,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def expired_token() -> str:
    token = jwt.encode(
        {"sub": TEST_USER_ID, "exp": int(time.time()) - 10},
        TEST_JWT_SECRET,
        algorithm="HS256",
    )
    return f"Bearer {token}"


def token_signed_by_another_key() -> str:
    """用另一个密钥签的 token：签名必须验不过。"""
    other_secret = "another-secret-key-different-from-test"
    token = jwt.encode(
        {"sub": TEST_USER_ID, "exp": int(time.time()) + 900},
        other_secret,
        algorithm="HS256",
    )
    return f"Bearer {token}"
