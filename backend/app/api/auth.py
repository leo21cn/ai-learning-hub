"""鉴权路由:Admin 登录 / 登出。"""
from __future__ import annotations

import time

from fastapi import APIRouter, Response

from app.core.errors import BusinessError, ErrorCode
from app.middleware.admin_auth import issue_admin_jwt, verify_admin_token
from app.schemas import ok
from app.schemas.auth import AdminLoginRequest


router = APIRouter(prefix="/api/auth", tags=["auth"])

# Cookie 配置
_COOKIE_NAME = "LH_ADMIN_SESSION"
_COOKIE_MAX_AGE = 8 * 3600


@router.post("/admin")
def admin_login(payload: AdminLoginRequest, response: Response):  # type: ignore[no-untyped-def]
    """校验 Admin Token,签发 JWT,写入 HttpOnly Cookie。"""
    if not verify_admin_token(payload.token):
        raise BusinessError(ErrorCode.INVALID_ADMIN_TOKEN, "管理令牌无效")
    token = issue_admin_jwt(sub="single-admin")
    response.set_cookie(
        key=_COOKIE_NAME,
        value=token,
        max_age=_COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        path="/",
    )
    expires_at = time.strftime(
        "%Y-%m-%dT%H:%M:%S+08:00",
        time.localtime(time.time() + _COOKIE_MAX_AGE),
    )
    return ok(data={"adminId": "single-admin", "expiresAt": expires_at})


@router.post("/logout")
def admin_logout(response: Response):  # type: ignore[no-untyped-def]
    response.delete_cookie(_COOKIE_NAME, path="/")
    return ok(data=None)


__all__ = ["router"]
