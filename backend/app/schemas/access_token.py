"""访问令牌(AccessToken)Pydantic Schema。"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class AccessTokenCreateRequest(BaseModel):
    label: str = Field(..., min_length=1, max_length=50)

    @model_validator(mode="after")
    def _strip(self):  # type: ignore[no-untyped-def]
        if self.label:
            self.label = self.label.strip()
        return self


class AccessTokenCreatedResponse(BaseModel):
    """创建/重新生成后一次性返回明文 + 哈希。"""

    id: str
    label: str
    value: str
    valueHash: str
    createdAt: Optional[str] = None
    regeneratedAt: Optional[str] = None


class AccessTokenItem(BaseModel):
    """列表项:仅哈希,不暴露明文。"""

    id: int
    label: str
    valueHash: str
    coursewareCount: int = 0
    createdAt: Optional[str] = None
    regeneratedAt: Optional[str] = None


class AccessTokenPaged(BaseModel):
    page: int
    size: int
    total: int
    items: List[AccessTokenItem]


__all__ = [
    "AccessTokenCreateRequest",
    "AccessTokenCreatedResponse",
    "AccessTokenItem",
    "AccessTokenPaged",
]