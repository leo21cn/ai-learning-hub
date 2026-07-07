"""课件(Courseware)Pydantic Schema。"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class CoursewareMaterialBrief(BaseModel):
    id: int
    name: str
    type: str
    sizeBytes: int
    duration: Optional[str] = None
    downloadUrl: str
    streamUrl: str = ""


class CoursewareBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)
    author: Optional[str] = Field(default=None, max_length=50)
    categoryId: int
    description: Optional[str] = None
    accessMode: str = Field(default="OPEN")
    tagIds: List[int] = []
    materialIds: List[int] = []
    tokenIds: List[int] = []

    @model_validator(mode="after")
    def _strip(self):  # type: ignore[no-untyped-def]
        if self.title:
            self.title = self.title.strip()
        if self.author:
            self.author = self.author.strip()
        return self


class CoursewareCreateRequest(CoursewareBase):
    pass


class CoursewareUpdateRequest(BaseModel):
    """所有字段都可选;非空表示修改。"""

    title: Optional[str] = Field(default=None, min_length=1, max_length=100)
    author: Optional[str] = Field(default=None, max_length=50)
    categoryId: Optional[int] = None
    description: Optional[str] = None
    accessMode: Optional[str] = None
    tagIds: Optional[List[int]] = None
    materialIds: Optional[List[int]] = None
    tokenIds: Optional[List[int]] = None

    @model_validator(mode="after")
    def _strip(self):  # type: ignore[no-untyped-def]
        if self.title:
            self.title = self.title.strip()
        if self.author:
            self.author = self.author.strip()
        return self


class CoursewareItem(BaseModel):
    id: int
    title: str
    author: Optional[str] = None
    categoryId: int
    categoryName: Optional[str] = None
    description: Optional[str] = None
    accessMode: str
    tagIds: List[int] = []
    tagNames: List[str] = []
    materialIds: List[int] = []
    tokenIds: List[int] = []
    createdAt: Optional[str] = None
    updatedAt: Optional[str] = None
    # 仅详情/详情公共返回时填充
    materials: List[CoursewareMaterialBrief] = []


class CoursewarePaged(BaseModel):
    page: int
    size: int
    total: int
    items: List[CoursewareItem]


class UnlockRequest(BaseModel):
    token: str = Field(..., min_length=1, max_length=64)


class UnlockResponse(BaseModel):
    tokenHash: str
    coursewareIds: List[int]


__all__ = [
    "CoursewareBase",
    "CoursewareCreateRequest",
    "CoursewareUpdateRequest",
    "CoursewareItem",
    "CoursewarePaged",
    "CoursewareMaterialBrief",
    "UnlockRequest",
    "UnlockResponse",
]