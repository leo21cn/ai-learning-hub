"""素材(Material)Pydantic Schema。"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class MaterialItem(BaseModel):
    id: int
    name: str
    type: str
    sizeBytes: int
    duration: Optional[str] = None
    uploadedAt: Optional[str] = None
    referenced: bool = False
    downloadUrl: str


class MaterialPaged(BaseModel):
    page: int
    size: int
    total: int
    items: list[MaterialItem]


__all__ = ["MaterialItem", "MaterialPaged"]
