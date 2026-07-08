"""主流程搜索的 LLM-to-SQL + 关键词兜底测试。

mock llm_sql 的内部函数,验证:
  - LLM 命中 → source="llm"
  - LLM 校验拒绝 / 超时 / 无 key → source="keyword"
  - 空关键词 → 返回最新(降级 keyword)
  - 关键词路径仍可用(短关键词)
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.services import llm_sql, search
from app.services.search import SearchResult
from tests.conftest import login_admin


# ============================================================
# 单元层:llm_sql.search() 同步入口
# ============================================================

def test_llm_sql_disabled_when_no_api_key(monkeypatch):
    """DASHSCOPE_API_KEY 留空 → is_enabled()=False,search() 立即降级。"""
    monkeypatch.setattr(llm_sql, "is_enabled", lambda: False)
    db = _fake_db()
    ids, source = llm_sql.search(db, keyword="帮我找一下管理课程", size=10)  # type: ignore[arg-type]
    assert ids == []
    assert source == "keyword"


def test_llm_sql_generate_returns_none_falls_back(monkeypatch):
    """generate_sql 返回 None → search() 返回 ([], 'keyword')。"""
    monkeypatch.setattr(llm_sql, "is_enabled", lambda: True)
    monkeypatch.setattr(llm_sql, "generate_sql", lambda q, **kw: None)
    db = _fake_db()
    ids, source = llm_sql.search(db, keyword="任何关键词", size=10)  # type: ignore[arg-type]
    assert ids == []
    assert source == "keyword"


def test_llm_sql_validate_rejects_invalid_sql_falls_back(monkeypatch):
    """LLM 输出含黑名单(DROP)→ validate_sql 返回 None → 降级。"""
    monkeypatch.setattr(llm_sql, "is_enabled", lambda: True)
    monkeypatch.setattr(
        llm_sql,
        "generate_sql",
        lambda q, **kw: "SELECT id FROM courseware; DROP TABLE courseware",
    )
    db = _fake_db()
    ids, source = llm_sql.search(db, keyword="任何关键词", size=10)  # type: ignore[arg-type]
    assert ids == []
    assert source == "keyword"


def test_llm_sql_empty_keyword_returns_keyword():
    """空关键词直接走 keyword(不调 LLM)。"""
    db = _fake_db()
    ids, source = llm_sql.search(db, keyword="", size=10)  # type: ignore[arg-type]
    assert ids == []
    assert source == "keyword"


# ============================================================
# 集成层:search.search() 异步主入口
# ============================================================

def test_search_llm_matches_natural_language(monkeypatch):
    """LLM 生成合法 SQL → 主流程返回 source='llm' + 命中 id 列表对应的 CoursewareItem。"""
    # 准备一个真实课件(走 ILIKE 也可命中的"管理"课程,确保 LLM 路径取到后 _fetch_coursewares 能补齐)
    # 这里 patch 掉 _fetch_coursewares 走 stub
    monkeypatch.setattr(llm_sql, "is_enabled", lambda: True)
    monkeypatch.setattr(
        llm_sql,
        "generate_sql",
        lambda q, **kw: "SELECT id, title FROM courseware WHERE title ILIKE '%管理%' LIMIT 10",
    )
    monkeypatch.setattr(
        llm_sql, "validate_sql", lambda raw, **kw: "SELECT id FROM courseware WHERE title ILIKE '%管理%' LIMIT 10"
    )
    monkeypatch.setattr(
        llm_sql, "execute_search_sql", lambda db, sql, *, size: [101, 102]
    )

    fake_items = [
        {"id": 101, "title": "项目管理入门", "accessMode": "OPEN"},
        {"id": 102, "title": "管理学基础", "accessMode": "OPEN"},
    ]
    monkeypatch.setattr(search, "_fetch_coursewares", lambda db, ids, size: fake_items[:size])

    db = _fake_db()
    result = asyncio.run(search.search(db, keyword="帮我找一下管理课程", size=10))
    assert result.source == "llm"
    assert result.total == 2
    assert [i["id"] for i in result.items] == [101, 102]


def test_search_llm_invalid_sql_falls_back_to_keyword(monkeypatch):
    """LLM 输出校验拒绝 → 主流程走 _keyword_hits,source='keyword'。"""
    monkeypatch.setattr(llm_sql, "is_enabled", lambda: True)
    monkeypatch.setattr(
        llm_sql, "generate_sql", lambda q, **kw: "DROP TABLE courseware"
    )
    monkeypatch.setattr(llm_sql, "validate_sql", lambda raw, **kw: None)
    monkeypatch.setattr(
        search, "_keyword_hits", lambda db, kw, size: _kw_stub_result()
    )

    db = _fake_db()
    result = asyncio.run(search.search(db, keyword="任何关键词", size=10))
    assert result.source == "keyword"
    assert result.items == _kw_stub_result()


def test_search_llm_timeout_falls_back_to_keyword(monkeypatch):
    """LLM 阻塞超过 llm_sql_timeout_seconds → asyncio.TimeoutError → 降级。"""
    import time as _t

    monkeypatch.setattr(llm_sql, "is_enabled", lambda: True)

    def _slow_sync(db, *, keyword, size):
        # 模拟 LLM 调用阻塞;主流程的 wait_for 会超时
        _t.sleep(0.5)
        return []

    monkeypatch.setattr(search, "_llm_sync_search", _slow_sync)
    # 强制超时极短,触发 TimeoutError
    from app.core import config

    class _S:
        llm_sql_timeout_seconds = 0.05

    monkeypatch.setattr(config, "get_settings", lambda: _S())

    # 关键词兜底 stub
    monkeypatch.setattr(
        search, "_keyword_hits", lambda db, kw, size: _kw_stub_result()
    )

    db = _fake_db()
    result = asyncio.run(search.search(db, keyword="任何关键词", size=10))
    assert result.source == "keyword"


def test_search_llm_no_api_key_falls_back(monkeypatch):
    """DASHSCOPE_API_KEY 未配置 → is_enabled()=False → 关键词兜底。"""
    monkeypatch.setattr(llm_sql, "is_enabled", lambda: False)
    monkeypatch.setattr(
        search, "_keyword_hits", lambda db, kw, size: _kw_stub_result()
    )

    db = _fake_db()
    result = asyncio.run(search.search(db, keyword="任何关键词", size=10))
    assert result.source == "keyword"


def test_search_empty_keyword_returns_latest_via_keyword(monkeypatch):
    """空关键词 → 不调 LLM → 走 _keyword_hits 返回最新课件。"""
    monkeypatch.setattr(llm_sql, "is_enabled", lambda: True)
    monkeypatch.setattr(
        llm_sql, "generate_sql", lambda q, **kw: pytest.fail("LLM must not be called for empty keyword")
    )
    monkeypatch.setattr(
        search, "_keyword_hits", lambda db, kw, size: _kw_stub_result()
    )

    db = _fake_db()
    result = asyncio.run(search.search(db, keyword="", size=10))
    assert result.source == "keyword"
    assert result.items == _kw_stub_result()


# ============================================================
# E2E 层:HTTP /api/public/coursewares/search
# ============================================================

def test_api_search_no_api_key_returns_keyword_source(monkeypatch, client: TestClient):
    """HTTP 接口:无 DASHSCOPE_API_KEY → 响应 source='keyword'。"""
    monkeypatch.setattr(llm_sql, "is_enabled", lambda: False)
    r = client.get("/api/public/coursewares/search", params={"q": "管理"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["code"] == "ok"
    assert body["data"]["source"] == "keyword"
    assert "items" in body["data"]
    assert "page" in body["data"]
    assert "size" in body["data"]


# ============================================================
# helpers
# ============================================================

class _FakeDB:
    """最小 db 占位;测试用 mock 替换真实 DB 路径。"""


def _fake_db():
    return _FakeDB()


def _kw_stub_result() -> List[Dict[str, Any]]:
    return [
        {
            "id": 1,
            "title": "项目管理入门",
            "author": "张三",
            "categoryId": 1,
            "categoryName": "项目管理",
            "description": None,
            "accessMode": "OPEN",
            "tagIds": [],
            "tagNames": [],
            "materialIds": [],
            "tokenIds": [],
            "createdAt": None,
            "updatedAt": None,
        }
    ]
