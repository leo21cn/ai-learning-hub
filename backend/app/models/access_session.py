"""访问会话(AccessSession):记录某个 token 持有者在 P-VIEWER 中
对某条受限课件素材的一次完整浏览(起 → 止 + 停留秒数)。

业务规则:
- B-1  仅在素材被至少一个 RESTRICTED 课件引用时才允许落库
- B-2  客户端上报 duration_seconds 与 ended_at-started_at 偏差 > 60s 时
       按服务端时间校正
- B-3  token 重新生成后,旧 token_id 上的历史 session 仍归属该 id
- B-4  delete token 时通过 FK CASCADE 一并清理其 session
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    TypeDecorator,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class _INETOrString(TypeDecorator):
    """PostgreSQL INET;SQLite/其他方言降级为 VARCHAR(45)。

    测试环境用 SQLite,INET 无法编译;线上 PostgreSQL 使用原生 INET。
    选用 IPV4/IPV6 文本最长 45 字符(IETF RFC 4291)兼容。
    """

    impl = String
    cache_ok = True

    def load_dialect_impl(self, dialect):  # type: ignore[no-untyped-def]
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import INET

            return dialect.type_descriptor(INET())
        return dialect.type_descriptor(String(45))


# SQLite 的 INTEGER PRIMARY KEY 自增是 ROWID,要求类型为 INTEGER;
# PostgreSQL 用 BIGINT。BigInteger().with_variant 适配两端。
_BigIntPK = BigInteger().with_variant(Integer, "sqlite")


class AccessSession(Base):
    """P-VIEWER 访问会话;FK CASCADE 保证 token/courseware/material
    删除时自动清理历史记录。"""

    __tablename__ = "access_session"
    __table_args__ = (
        CheckConstraint(
            "duration_seconds IS NULL OR duration_seconds >= 0",
            name="ck_access_session_duration_nonneg",
        ),
        Index("ix_access_session_token_started", "token_id", "started_at"),
        Index(
            "ix_access_session_token_material",
            "token_id",
            "material_id",
            "started_at",
        ),
        Index(
            "ix_access_session_token_courseware",
            "token_id",
            "courseware_id",
            "started_at",
        ),
        {"comment": "访问会话;记录 token + 课件 + 素材 + 起止时间 + 停留秒数"},
    )

    id: Mapped[int] = mapped_column(
        _BigIntPK, primary_key=True, autoincrement=True
    )
    token_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("access_token.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    courseware_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("courseware.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    material_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("material.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_seconds: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )
    client_leave: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    ip: Mapped[Optional[str]] = mapped_column(_INETOrString(45), nullable=True)
    ua: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<AccessSession id={self.id} token={self.token_id} "
            f"material={self.material_id} dur={self.duration_seconds}>"
        )


__all__ = ["AccessSession"]
