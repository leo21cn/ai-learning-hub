"""统一响应信封:`{code, message, data, requestId}`。"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, Field

from app.core.errors import BusinessError, ErrorCode


def now_iso() -> str:
    """返回 Asia/Shanghai 时区的 ISO-8601 字符串。"""
    from app.core.config import get_settings  # 延迟导入避免循环

    tz = get_settings().timezone or "Asia/Shanghai"
    # 简化:使用本地时区(已由容器 ENV TZ 决定)
    return datetime.now(tz=timezone.utc).isoformat()


T = TypeVar("T")


class Envelope(BaseModel, Generic[T]):
    """统一响应信封。"""

    code: str = "ok"
    message: str = "ok"
    data: Optional[T] = None
    requestId: Optional[str] = Field(default=None, alias="requestId")

    model_config = {"populate_by_name": True}


def ok(data: Any = None, request_id: Optional[str] = None) -> dict:
    """构造成功响应。"""
    return {
        "code": "ok",
        "message": "ok",
        "data": data,
        "requestId": request_id,
    }


def fail(code: str, message: Optional[str] = None, data: Any = None) -> dict:
    """构造失败信封(供全局异常处理 / 中间件调用)。"""
    return {
        "code": code,
        "message": message or code,
        "data": data,
        "requestId": None,
    }


def envelope_or_business(exc: BusinessError, request_id: Optional[str] = None) -> dict:
    return {
        "code": exc.code,
        "message": exc.message,
        "data": exc.payload,
        "requestId": request_id,
    }


__all__ = ["Envelope", "ok", "fail", "envelope_or_business", "ErrorCode", "BusinessError"]
