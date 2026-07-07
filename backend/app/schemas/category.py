"""分类(Category)Pydantic Schema。"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class CategoryBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=30)
    parentId: Optional[int] = None


class CategoryCreateRequest(CategoryBase):
    @model_validator(mode="after")
    def _strip(self):  # type: ignore[no-untyped-def]
        if self.name:
            self.name = self.name.strip()
        return self


class CategoryRenameRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=30)

    @model_validator(mode="after")
    def _strip(self):  # type: ignore[no-untyped-def]
        if self.name:
            self.name = self.name.strip()
        return self


class CategoryNode(BaseModel):
    id: int
    name: str
    level: int
    parentId: Optional[int] = None
    children: List["CategoryNode"] = []


CategoryNode.model_rebuild()


__all__ = [
    "CategoryBase",
    "CategoryCreateRequest",
    "CategoryRenameRequest",
    "CategoryNode",
]
