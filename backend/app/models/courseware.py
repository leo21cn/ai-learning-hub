"""课件(Courseware)与 AccessMode 枚举。"""
from __future__ import annotations

import enum
from datetime import datetime
from typing import List, Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class AccessMode(str, enum.Enum):
    """课件访问模式。"""

    OPEN = "OPEN"  # 开放
    RESTRICTED = "RESTRICTED"  # 受限:需 AccessToken 解锁


class Courseware(Base):
    """课件主表。"""

    __tablename__ = "courseware"
    __table_args__ = ({"comment": "课件主表"},)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    author: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    category_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("category.id", ondelete="RESTRICT"), nullable=False
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    access_mode: Mapped[AccessMode] = mapped_column(
        Enum(AccessMode, name="access_mode_enum", native_enum=False, length=16),
        nullable=False,
        default=AccessMode.OPEN,
    )
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=True,
    )

    category = relationship("Category", lazy="joined")

    # M:N 关联(实际数据在 association 表中)
    tags: Mapped[List["Tag"]] = relationship(  # noqa: F821
        "Tag", secondary="courseware_tag", backref="coursewares", lazy="selectin"
    )
    materials: Mapped[List["Material"]] = relationship(  # noqa: F821
        "Material",
        secondary="courseware_material",
        backref="coursewares",
        lazy="selectin",
    )
    access_tokens: Mapped[List["AccessToken"]] = relationship(  # noqa: F821
        "AccessToken",
        secondary="courseware_access_token",
        backref="coursewares",
        lazy="selectin",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Courseware id={self.id} title={self.title!r} mode={self.access_mode}>"


__all__ = ["Courseware", "AccessMode"]
