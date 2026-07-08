"""统一搜索服务:LLM-to-SQL 召回(qwen-plus)优先 + 关键词 ILIKE 兜底。

业务规则(参见 plan §2.1、doc/spec/10-API设计规范 §5.1.1):

1. **LLM-to-SQL 召回**(默认):
   - 调 dashscope qwen-plus 让 LLM 直写 WHERE 条件
   - 7 道闸白名单校验(_sql_safety.validate_sql)
   - read-only 事务执行,按 LLM 排序取前 size 条
   - `source="llm"`
2. **关键词兜底**(降级):
   - DASHSCOPE_API_KEY 未配置 / dashscope 调用失败 / SQL 校验拒绝 / 执行为空 → `_keyword_hits()`
   - `source="keyword"`(前端徽标显示"AI 智能搜索 · 降级中")
3. 数据契约:`{items, source, total}`,`source` 枚举 = {"llm", "keyword"}。
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.models.courseware import Courseware
from app.services import llm_sql

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    items: List[Dict[str, Any]]
    source: str  # 'llm' | 'keyword'
    total: int


# ============================================================
# 关键词兜底(原 ILIKE 路径)
# ============================================================
def _keyword_hits(db: Session, keyword: str, size: int) -> List[Dict[str, Any]]:
    """关键词 ILIKE 搜索(标题/作者/描述/标签名)。空关键词时返回最新。"""
    q = (keyword or "").strip()
    base = select(Courseware).options(
        selectinload(Courseware.tags),
        selectinload(Courseware.access_tokens),
        selectinload(Courseware.materials),
        selectinload(Courseware.category),
    )

    if q:
        pattern = f"%{q}%"
        from app.models.tag import Tag
        from app.models.association import courseware_tag

        tag_match = (
            select(courseware_tag.c.courseware_id)
            .join(Tag, courseware_tag.c.tag_id == Tag.id)
            .where(Tag.name.ilike(pattern))
        )
        base = base.where(
            or_(
                Courseware.title.ilike(pattern),
                Courseware.author.ilike(pattern),
                Courseware.description.ilike(pattern),
                Courseware.id.in_(tag_match),
            )
        )

    rows = db.scalars(base.order_by(Courseware.updated_at.desc()).limit(size)).all()
    from app.services.courseware import _to_item  # 局部复用,避免循环

    return [_to_item(r, downloadable=False) for r in rows]


# ============================================================
# 拉取完整 Courseware(LLM 路径只需 id,这里补齐)
# ============================================================
def _fetch_coursewares(
    db: Session, ids_in_order: List[int], size: int
) -> List[Dict[str, Any]]:
    """按给定 id 顺序取完整 Courseware(含 tags/materials/category)。"""
    if not ids_in_order:
        return []
    rows = db.scalars(
        select(Courseware)
        .where(Courseware.id.in_(ids_in_order))
        .options(
            selectinload(Courseware.tags),
            selectinload(Courseware.materials),
            selectinload(Courseware.access_tokens),
            selectinload(Courseware.category),
        )
    ).all()
    by_id = {c.id: c for c in rows}
    from app.services.courseware import _to_item  # 局部复用,避免循环

    items: List[Dict[str, Any]] = []
    for cid in ids_in_order[:size]:
        obj = by_id.get(cid)
        if obj is not None:
            items.append(_to_item(obj, downloadable=False))
    return items


# ============================================================
# LLM 同步包装(供 asyncio.to_thread 调用)
# ============================================================
def _llm_sync_search(db: Session, *, keyword: str, size: int) -> List[Dict[str, Any]]:
    """同步包装:generate_sql → validate_sql → execute_search_sql → _fetch_coursewares。

    任一环节失败 → 返回 [](由 search() 降级到 keyword)。
    """
    ids, source = llm_sql.search(db, keyword=keyword, size=size)
    if source != "llm" or not ids:
        return []
    return _fetch_coursewares(db, ids, size)


# ============================================================
# 主流程(异步)
# ============================================================
async def search(
    db: Session,
    *,
    keyword: str,
    size: int = 20,
) -> SearchResult:
    """统一搜索:LLM-to-SQL 召回优先 + 关键词 ILIKE 兜底。

    返回 source:
        "llm":LLM 直写 SQL 命中(>=1)
        "keyword":LLM 未启用/失败/校验拒绝/空候选,降级 ILIKE
    """
    # 1. LLM-to-SQL 召回
    stripped = (keyword or "").strip()
    if stripped and llm_sql.is_enabled():
        try:
            timeout_s = float(get_settings().llm_sql_timeout_seconds or 8.0)
            items = await asyncio.wait_for(
                asyncio.to_thread(_llm_sync_search, db, keyword=stripped, size=size),
                timeout=timeout_s,
            )
        except asyncio.TimeoutError:
            logger.warning("LLM SQL search timeout, fallback to keyword")
            items = []
        except Exception as e:  # noqa: BLE001
            logger.warning("LLM SQL search failed, fallback to keyword: %s", e)
            items = []
        if items:
            return SearchResult(items=items, source="llm", total=len(items))

    # 2. 关键词兜底
    items = await asyncio.to_thread(_keyword_hits, db, keyword, size)
    return SearchResult(items=items, source="keyword", total=len(items))


# 同步包装(供 FastAPI 同步路由调用)
def search_sync(db: Session, *, keyword: str, size: int = 20) -> SearchResult:
    """FastAPI 默认同步接口的便捷包装。"""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # 已在事件循环中(uvicorn 异步时),直接 await
            return asyncio.ensure_future(search(db, keyword=keyword, size=size))  # type: ignore[return-value]
    except RuntimeError:
        pass
    return asyncio.run(search(db, keyword=keyword, size=size))


__all__ = [
    "SearchResult",
    "search",
    "search_sync",
]
