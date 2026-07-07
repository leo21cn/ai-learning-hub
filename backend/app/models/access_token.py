"""课件访问令牌(AccessToken):只存 value_hash(SHA-256),原值仅创建/重新生成时明文返回。"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class AccessToken(Base):
    """管理员维护的访问令牌:label 全局唯一;value_hash 存 SHA-256 摘要。"""

    __tablename__ = "access_token"
    __table_args__ = ({"comment": "访问令牌;value_hash = sha256(明文)"},)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    label: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    value_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
    regenerated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AccessToken id={self.id} label={self.label!r}>"


__all__ = ["AccessToken"]
