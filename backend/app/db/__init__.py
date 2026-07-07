"""数据库连接与 session 工厂。"""
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


_settings = get_settings()

# 同步引擎(适配 Alembic 与 FastAPI 同步路由)
# SQLite(如测试用)不支持 pool_size/max_overflow，仅 Postgres/MySQL 走连接池。
# SQLite 内存还需要 check_same_thread=False 以允许 TestClient 在多线程下访问。
_engine_kwargs: dict = {"pool_pre_ping": True, "echo": False}
if _settings.database_url.startswith("sqlite"):
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
    _engine_kwargs["poolclass"] = StaticPool
else:
    _engine_kwargs.update(pool_size=10, max_overflow=20)
engine = create_engine(_settings.database_url, **_engine_kwargs)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """所有 ORM 模型的统一基类。"""

    pass


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖注入:每个请求一个 Session。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


__all__ = ["Base", "engine", "SessionLocal", "get_db"]
