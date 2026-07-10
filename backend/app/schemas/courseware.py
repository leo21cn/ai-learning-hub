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
    # 该素材在课件内的展示顺序，由管理员拖拽写入；
    # 同课件内 0..N-1 连续递增，前台详情页与 P-VIEWER 按此顺序渲染。
    sortOrder: int = 0


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


class CoursewareMaterialsReorderRequest(BaseModel):
    """专用排序接口请求体：materialIds 按目标顺序传入。

    服务端按数组下标重写 courseware_material.sort_order（0..N-1），
    并校验：①课件存在 ②全部 ID 属于该课件 ③数量一致 ④无重复。
    """

    materialIds: List[int] = Field(..., min_length=1)


__all__ = [
    "CoursewareBase",
    "CoursewareCreateRequest",
    "CoursewareUpdateRequest",
    "CoursewareItem",
    "CoursewarePaged",
    "CoursewareMaterialBrief",
    "UnlockRequest",
    "UnlockResponse",
    "CoursewareMaterialsReorderRequest",
]