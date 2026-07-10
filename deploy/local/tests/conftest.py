"""pytest 全局 fixtures:为后端测试提供内存数据库与 FastAPI 客户端。"""
from __future__ import annotations

import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# 测试环境:必须在 import app.* 之前覆盖 DATABASE_URL
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("ADMIN_TOKEN", "shleeyuan")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-32-chars-min-for-tests-1234")

from app.core.config import get_settings  # noqa: E402
from app.db import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import *  # noqa: E402,F401,F403  # 注册所有模型

# 强制使用 SQLite 内存(覆盖容器里的 postgres URL)
_settings = get_settings()
_settings.database_url = "sqlite:///:memory:"  # type: ignore[attr-defined]

_test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_TestingSession = sessionmaker(bind=_test_engine, autoflush=False, autocommit=False)


def _override_db():  # type: ignore[no-untyped-def]
    db = _TestingSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_db


@pytest.fixture(autouse=True)
def _init_schema() -> Generator[None, None, None]:
    Base.metadata.create_all(_test_engine)
    yield
    Base.metadata.drop_all(_test_engine)


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as c:
        yield c


def login_admin(client: TestClient) -> None:
    r = client.post("/api/auth/admin", json={"token": "demo"})
    assert r.status_code == 200, r.text
    # Cookie 由 TestClient 自动保持


__all__ = ["client", "login_admin"]
