"""标签(Tag)表:扁平,全局唯一名称。"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Tag(Base):
    """课件标签:name 全局唯一。"""

    __tablename__ = "tag"
    __table_args__ = ({"comment": "标签表,name 全局唯一"},)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Tag id={self.id} name={self.name!r}>"


__all__ = ["Tag"]
