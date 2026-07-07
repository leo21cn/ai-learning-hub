"""管理员鉴权相关 Pydantic Schema。"""
from __future__ import annotations

from pydantic import BaseModel, Field


class AdminLoginRequest(BaseModel):
    token: str = Field(..., min_length=1, max_length=255)


class AdminLoginResponse(BaseModel):
    adminId: str = "single-admin"
    expiresAt: str  # ISO-8601


__all__ = ["AdminLoginRequest", "AdminLoginResponse"]
