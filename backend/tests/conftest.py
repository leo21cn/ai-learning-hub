"""pytest 全局 fixtures:为后端测试提供内存数据库与 FastAPI 客户端。"""
from __future__ import annotations

import builtins
import os
from collections.abc import Generator

# 修复 Windows 上 slowapi/starlette 默认 open() 使用 GBK 编码读 .env 失败:
# 强制在测试环境用 utf-8 打开文本文件。此修改仅作用于 pytest 进程。
_orig_open = builtins.open
def _patched_open(file, mode="r", *args, **kwargs):  # type: ignore[no-untyped-def]
    if "b" not in mode and "encoding" not in kwargs:
        kwargs["encoding"] = "utf-8"
    return _orig_open(file, mode, *args, **kwargs)
builtins.open = _patched_open

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

# 测试环境:必须在 import app.* 之前覆盖 DATABASE_URL
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-32-chars-min-for-tests-1234")

from app.core.config import get_settings  # noqa: E402
from app.db import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import *  # noqa: E402,F401,F403  # 注册所有模型

# 强制使用 SQLite 内存(覆盖容器里的 postgres URL)
_settings = get_settings()
_settings.database_url = "sqlite:///:memory:"  # type: ignore[attr-defined]

# 测试用 admin token:与现有测试用例保持一致(用 "demo")
# 注意:这里覆盖 settings.admin_token 以让 admin_login 等历史 fixture 走通。
ADMIN_TOKEN_TEST = "demo"
_settings.admin_token = ADMIN_TOKEN_TEST  # type: ignore[attr-defined]

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
    # 重置 access-sessions 限流桶(模块级全局 dict,跨测试累积)
    from app.api.public import access_sessions as _as
    with _as._rate_lock:
        for b in _as._rate_buckets.values():
            b.clear()
    yield
    Base.metadata.drop_all(_test_engine)


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as c:
        yield c


@pytest.fixture
def admin_login(client: TestClient) -> None:
    """对需要鉴权的接口,先登录后台管理员。"""
    r = client.post("/api/auth/admin", json={"token": ADMIN_TOKEN_TEST})
    assert r.status_code == 200, r.text
    # Cookie 由 TestClient 自动保持


@pytest.fixture
def courseware_payload(admin_login):
    """构造课件 POST payload 的工厂。默认 OPEN,允许覆盖。"""
    counter = {"i": 0}

    def _factory(
        title: str | None = None,
        category_id: int = 0,
        access_mode: str = "OPEN",
        token_ids: list[int] | None = None,
        tag_ids: list[int] | None = None,
        material_ids: list[int] | None = None,
    ) -> dict:
        counter["i"] += 1
        return {
            "title": title or f"course-{counter['i']}",
            "categoryId": category_id,
            "accessMode": access_mode,
            "tokenIds": token_ids if token_ids is not None else [],
            "tagIds": tag_ids or [],
            "materialIds": material_ids or [],
            "description": None,
            "author": None,
        }

    return _factory


def login_admin(client: TestClient) -> None:
    r = client.post("/api/auth/admin", json={"token": ADMIN_TOKEN_TEST})
    assert r.status_code == 200, r.text
    # Cookie 由 TestClient 自动保持


__all__ = ["client", "login_admin"]
