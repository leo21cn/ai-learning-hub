"""分类(Category)表:支持 3 级树形结构。"""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy import ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Category(Base):
    """课件分类。level ∈ {1, 2, 3};parent_id=NULL 为根。"""

    __tablename__ = "category"
    __table_args__ = (
        # 同一父节点下名称唯一
        UniqueConstraint("parent_id", "name", name="uq_category_parent_name"),
        Index("ix_category_parent_id", "parent_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(30), nullable=False)
    parent_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("category.id", ondelete="RESTRICT"), nullable=True
    )
    level: Mapped[int] = mapped_column(Integer, nullable=False)  # 1 / 2 / 3

    # 自引用:一个分类可有多个子节点
    children: Mapped[List["Category"]] = relationship(
        "Category",
        back_populates="parent",
        cascade="save-update",
    )
    parent: Mapped[Optional["Category"]] = relationship(
        "Category",
        back_populates="children",
        remote_side="Category.id",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Category id={self.id} level={self.level} name={self.name!r}>"


__all__ = ["Category"]
