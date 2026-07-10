"""M:N 关联表(courseware_tag / courseware_material / courseware_access_token)。"""
from __future__ import annotations

from sqlalchemy import Column, ForeignKey, Index, Integer, Table

from app.db import Base


courseware_tag = Table(
    "courseware_tag",
    Base.metadata,
    Column("courseware_id", Integer, ForeignKey("courseware.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tag.id", ondelete="CASCADE"), primary_key=True),
)

courseware_material = Table(
    "courseware_material",
    Base.metadata,
    Column("courseware_id", Integer, ForeignKey("courseware.id", ondelete="CASCADE"), primary_key=True),
    Column("material_id", Integer, ForeignKey("material.id", ondelete="CASCADE"), primary_key=True),
    # 课件内的素材展示顺序（学习路径），由管理员拖拽写入。
    # 同一课件内 0..N-1 连续递增；ORM 默认 0 由业务层维护。
    Column("sort_order", Integer, nullable=False, default=0),
    # 加速按课件取有序素材的查询。
    Index("ix_courseware_material_courseware_order", "courseware_id", "sort_order"),
)

courseware_access_token = Table(
    "courseware_access_token",
    Base.metadata,
    Column("courseware_id", Integer, ForeignKey("courseware.id", ondelete="CASCADE"), primary_key=True),
    Column("access_token_id", Integer, ForeignKey("access_token.id", ondelete="CASCADE"), primary_key=True),
)


__all__ = [
    "courseware_tag",
    "courseware_material",
    "courseware_access_token",
]
