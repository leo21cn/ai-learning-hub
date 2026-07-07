"""Admin 鉴权依赖:校验 JWT,提取管理员身份。"""
from __future__ import annotations

from typing import Optional

import jwt
from fastapi import Depends, Request

from app.core.config import get_settings
from app.core.errors import BusinessError, ErrorCode


_settings = get_settings()


def _extract_token(request: Request) -> Optional[str]:
    # 优先 Authorization: Bearer
    auth = request.headers.get("Authorization")
    if auth and auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()
    # 其次 Cookie LH_ADMIN_SESSION
    cookie_token = request.cookies.get("LH_ADMIN_SESSION")
    return cookie_token or None


def get_admin_principal(request: Request) -> dict:
    """FastAPI Depends:必须 Admin 已登录,否则抛 401。"""
    token = _extract_token(request)
    if not token:
        raise BusinessError(ErrorCode.UNAUTHENTICATED, "未登录或会话已失效")
    try:
        payload = jwt.decode(
            token,
            _settings.jwt_secret,
            algorithms=[_settings.jwt_algorithm],
            options={"require": ["exp", "sub"]},
        )
    except jwt.ExpiredSignatureError:
        raise BusinessError(ErrorCode.UNAUTHENTICATED, "会话已过期,请重新登录")
    except jwt.InvalidTokenError:
        raise BusinessError(ErrorCode.UNAUTHENTICATED, "会话无效,请重新登录")
    return {"sub": payload.get("sub"), "iat": payload.get("iat"), "exp": payload.get("exp")}


def issue_admin_jwt(sub: str = "single-admin") -> str:
    """签发 Admin JWT(8h TTL,默认 sub=single-admin)。"""
    import time

    now = int(time.time())
    payload = {
        "sub": sub,
        "iat": now,
        "exp": now + _settings.jwt_ttl_hours * 3600,
    }
    return jwt.encode(payload, _settings.jwt_secret, algorithm=_settings.jwt_algorithm)


def verify_admin_token(token: str) -> bool:
    """登录接口使用的明文 Admin Token 验证(常量时间比较)。"""
    import hmac

    return hmac.compare_digest(token or "", _settings.admin_token or "")


__all__ = ["get_admin_principal", "issue_admin_jwt", "verify_admin_token"]
