"""Pydantic Schema:访问会话与按素材聚合。"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class AccessSessionItem(BaseModel):
    """单条访问台账行。"""

    id: int
    startedAt: str
    endedAt: Optional[str] = None
    durationSeconds: Optional[int] = None
    clientLeave: bool
    coursewareId: int
    coursewareTitle: str
    materialId: int
    materialName: str
    materialType: str
    ip: Optional[str] = None
    ua: Optional[str] = None


class AccessSessionSummary(BaseModel):
    """同一查询区间内的聚合概览。"""

    totalDurationSeconds: int
    sessionCount: int
    coursewareCount: int
    materialCount: int


class AccessSessionPaged(BaseModel):
    page: int
    size: int
    total: int
    summary: AccessSessionSummary
    items: List[AccessSessionItem]


class MaterialUsageItem(BaseModel):
    """按素材聚合:本期重点接口。"""

    materialId: int
    materialName: str
    materialType: str
    coursewareId: int
    coursewareTitle: str
    totalDurationSeconds: int
    viewCount: int
    lastViewedAt: Optional[str] = None


class MaterialUsagePaged(BaseModel):
    start: str
    end: str
    items: List[MaterialUsageItem]


class AccessSessionStartRequest(BaseModel):
    materialId: int = Field(..., ge=1)


class AccessSessionStartResponse(BaseModel):
    sessionId: Optional[int] = None
    startedAt: Optional[str] = None
    recorded: bool = False


class AccessSessionLeaveRequest(BaseModel):
    durationSeconds: Optional[int] = Field(default=None, ge=0)


class AccessSessionLeaveResponse(BaseModel):
    ok: bool = True


__all__ = [
    "AccessSessionItem",
    "AccessSessionSummary",
    "AccessSessionPaged",
    "MaterialUsageItem",
    "MaterialUsagePaged",
    "AccessSessionStartRequest",
    "AccessSessionStartResponse",
    "AccessSessionLeaveRequest",
    "AccessSessionLeaveResponse",
]
