"""统一搜索服务:LLM 语义排序 + 关键词回退。

业务规则(参见 plan §5):
  1. OPENAI_API_KEY / ANTHROPIC_API_KEY 不存在 → 直接走关键词
  2. 调用 LLM,5 秒超时或失败 → 自动降级到关键词
  3. LLM 不可用时,前端徽标显示 '降级中'
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.courseware import Courseware

logger = logging.getLogger(__name__)

LLM_TIMEOUT_SECS = 5.0


@dataclass
class SearchResult:
    items: List[Dict[str, Any]]
    source: str  # 'llm' | 'keyword'
    total: int


def _keyword_hits(db: Session, keyword: str, size: int) -> List[Dict[str, Any]]:
    """关键词 ILIKE 搜索(标题/作者/描述/标签)。空关键词时返回最新。"""
    q = (keyword or "").strip()
    stmt = (
        select(Courseware)
        .options(
            selectinload(Courseware.tags),
            selectinload(Courseware.access_tokens),
            selectinload(Courseware.materials),
        )
        .order_by(Courseware.updated_at.desc())
        .limit(size)
    )
    if q:
        pattern = f"%{q}%"
        # 关联搜索标签名
        from app.models.tag import Tag
        from app.models.association import courseware_tag

        tag_match = (
            select(courseware_tag.c.courseware_id)
            .join(Tag, courseware_tag.c.tag_id == Tag.id)
            .where(Tag.name.ilike(pattern))
        )
        stmt = (
            select(Courseware)
            .options(
                selectinload(Courseware.tags),
                selectinload(Courseware.access_tokens),
                selectinload(Courseware.materials),
            )
            .where(
                or_(
                    Courseware.title.ilike(pattern),
                    Courseware.author.ilike(pattern),
                    Courseware.description.ilike(pattern),
                    Courseware.id.in_(tag_match),
                )
            )
            .order_by(Courseware.updated_at.desc())
            .limit(size)
        )
    rows = db.scalars(stmt).all()
    from app.services.courseware import _to_item  # 局部复用,避免循环

    return [_to_item(r, downloadable=False) for r in rows]


def _tokenize(q: str) -> List[str]:
    """将查询切成关键词,大小写不敏感。"""
    q = (q or "").lower().strip()
    if not q:
        return []
    # 保留中英文 + 数字
    return [w for w in re.split(r"[\s,;，。；、]+", q) if w]


async def _llm_rerank(
    query: str,
    candidates: List[Dict[str, Any]],
    *,
    base_url: str,
    api_key: str,
    model: str,
) -> Optional[List[int]]:
    """调用 LLM 重排;返回按相关性排序后的 candidate id 列表。失败返回 None。"""
    if not candidates:
        return None
    items_text = "\n".join(
        f"[{c['id']}] {c.get('title','')} / {c.get('author','')} / "
        f"{c.get('description','')} / tags={','.join(c.get('tagNames') or [])}"
        for c in candidates[:30]
    )
    sys_prompt = (
        "你是 Learning Hub 的搜索排序助手。"
        "根据用户查询对 candidate 按相关性降序排序,只输出候选 id,逗号分隔。"
    )
    user_prompt = (
        f"查询: {query}\n候选:\n{items_text}\n"
        "输出最相关的前 N 个 id(逗号分隔):"
    )

    payload: Dict[str, Any] = {
        "model": model,
        "temperature": 0.0,
        "messages": [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    url = base_url.rstrip("/") + "/v1/chat/completions"
    try:
        async with httpx.AsyncClient(timeout=LLM_TIMEOUT_SECS) as client:
            r = await client.post(url, json=payload, headers=headers)
            r.raise_for_status()
            data = r.json()
            text = data["choices"][0]["message"]["content"].strip()
            ids = [int(x) for x in re.findall(r"\d+", text) if x.isdigit()]
            return [int(i) for i in ids if i > 0]
    except Exception as e:
        logger.warning("LLM rerank failed: %s", e)
        return None


def _llm_config() -> Optional[Dict[str, str]]:
    """读取 LLM 配置。返回 None 表示不可用。"""
    if os.getenv("LH_LLM_DISABLED") == "1":
        return None
    key = os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
    if not key:
        return None
    base = os.getenv("OPENAI_BASE_URL") or "https://api.openai.com"
    model = os.getenv("OPENAI_MODEL") or "gpt-4o-mini"
    return {"base_url": base, "api_key": key, "model": model}


async def search(
    db: Session,
    *,
    keyword: str,
    size: int = 20,
) -> SearchResult:
    """统一搜索:LLM 优先 + 关键词回退。

    返回的 source 字段指示实际用的是哪种实现,前端用于显示降级徽标。
    """
    cfg = _llm_config()
    if cfg is None:
        items = _keyword_hits(db, keyword, size)
        return SearchResult(items=items, source="keyword", total=len(items))

    # 拿到候选(关键词命中)
    candidates = _keyword_hits(db, keyword, size=min(30, max(size, 5)))
    if not candidates:
        return SearchResult(items=[], source="llm", total=0)
    try:
        ranked_ids = await asyncio.wait_for(
            _llm_rerank(keyword, candidates, **cfg),
            timeout=LLM_TIMEOUT_SECS,
        )
    except asyncio.TimeoutError:
        logger.info("LLM rerank timeout, fallback to keyword")
        return SearchResult(
            items=candidates[:size],
            source="keyword",
            total=len(candidates),
        )
    if not ranked_ids:
        return SearchResult(
            items=candidates[:size],
            source="keyword",
            total=len(candidates),
        )
    by_id = {c["id"]: c for c in candidates}
    seen: List[Dict[str, Any]] = []
    for cid in ranked_ids:
        if cid in by_id and by_id[cid] not in seen:
            seen.append(by_id[cid])
    # 补齐 LLM 未返回的
    for c in candidates:
        if len(seen) >= size:
            break
        if c not in seen:
            seen.append(c)
    return SearchResult(items=seen[:size], source="llm", total=len(seen))


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
