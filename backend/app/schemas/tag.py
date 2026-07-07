"""标签(Tag)Pydantic Schema。"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, model_validator


class TagNameRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=30)

    @model_validator(mode="after")
    def _strip(self):  # type: ignore[no-untyped-def]
        if self.name:
            self.name = self.name.strip()
        return self


class TagItem(BaseModel):
    id: int
    name: str
    coursewareCount: int = 0
    createdAt: Optional[str] = None


class TagPaged(BaseModel):
    page: int
    size: int
    total: int
    items: list[TagItem]


__all__ = ["TagNameRequest", "TagItem", "TagPaged"]
