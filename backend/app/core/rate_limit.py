"""限流模块:SlowAPI 适配 FastAPI,支持 IP / Token 双键。"""
from __future__ import annotations

import logging
from typing import Callable, Optional

from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from slowapi.wrappers import Limit

from app.core.config import get_settings

logger = logging.getLogger(__name__)
_settings = get_settings()


def _key_func(identifier: str) -> Callable:
    """构造 SlowAPI key 函数。"""

    def _resolve(request) -> str:  # type: ignore[no-untyped-def]
        ip = get_remote_address(request) or "unknown"
        # Optionally enrich with header-based identifiers
        if identifier == "ip":
            return f"ip:{ip}"
        if identifier == "session":
            # session-based: 从 JWT 解析 sub;失败 fallback 到 ip
            auth = request.headers.get("Authorization", "")
            if auth.lower().startswith("bearer "):
                token = auth.split(" ", 1)[1]
                # 取 JWT payload.sub 作为会话 key(简化:仅做最末段截取)
                sess = token.rsplit(".", 1)[0][-12:]
                return f"sess:{sess}"
            return f"sess:{ip}"
        return identifier

    return _resolve


def get_limiter() -> Limiter:
    """构建全局 limiter,优先使用 Redis;否则内存模式。"""
    storage_uri = _settings.storage_redis_url or "memory://"
    return Limiter(key_func=get_remote_address, storage_uri=storage_uri, default_limits=[])


limiter = get_limiter()


def rate_limit(spec: str, key: str = "ip") -> Limit:  # type: ignore[name-defined]
    """路由装饰器限流。spec 形如 '30/minute'。"""
    return limiter.limit(spec, key_func=_key_func(key), per_method=False)


__all__ = ["limiter", "rate_limit", "RateLimitExceeded"]
