"""M:N 关联表(courseware_tag / courseware_material / courseware_access_token)。"""
from __future__ import annotations

from sqlalchemy import Column, ForeignKey, Integer, Table

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
