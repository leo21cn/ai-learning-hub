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
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.models.courseware import Courseware
from app.services import llm_sql

logger = logging.getLogger(__name__)


# ============================================================
# 中文查询“清洗”
# ============================================================
# 背景:keyword 兑底路径在 LLM 不可用时,只能对原始查询字符串做 ILIKE。
# 用户输入常带“帮我找一下与项目管理相关的课件”这种“废话”,直接用原句
# 做 ILIKE 命中率很低(标题里没有“帮我找一下”)。下面的正则将常见问题句式
# 进行规范化、提取潜在核心名词,允许多个候选输入 ILIKE 依次尝试。
_CN_QUERY_TRIM_PATTERNS: List[Tuple[re.Pattern[str], str]] = [
    # 表礼貌/求助语气: “请帮我找一找、麻烦帮我查一下” → 去掉头部
    (re.compile(r"^(请|麻烦|劳驾)?(帮|为|替|给)(我|我们|咱)?(找一?找|寻|搜一?下|搜|查一?下|查|看一下|看下|了解|学习|查询|检索|扒|怼|给)"), ""),
    # 表 “一下”软化语气, 可去
    (re.compile(r"一下(吧|吗|呀|呗)?$"), ""),
    # 表 “与/跟/和 XX 相关(的)…” → 保留中心词 "XX"
    # 例: "与项目管理相关的课件" -> "项目管理", "跟 BJC 有关系的视频" -> "BJC"
    (re.compile(r"(与|跟|和|关于)([^,。?!\s]+?)(相关|有关|相关 的|有关 的)的?"), r"\2"),
    # 表 "XX有哪些/给我XX的资料/帮我XX的" → 保留 XX
    (re.compile(r"(有|来给|给我|我要|帮我|向我们|推荐)([^,。?!\s]{2,})"), r"\2"),
    # 广泛型平台术语: “课件/课程/资料/文档/视频/PPT/PDF” 这些不算独立检索词, 删除后留出纯关键词
    (re.compile(r"(课件|课程|资料|文档|视频|PPT|PPTX|PDF)(的|方面|集合|合集|列表)?"), ""),
]

# 额外过滤一些高频准停用词(单个字)以免误检索
_CN_STOPWORDS: frozenset = frozenset({
    "我", "你", "他", "她", "它", "们", "的", "了", "是", "在", "有", "和", "与", "跟",
    "以及", "和", "及", "请", "帮我", "麻烦", "劳驾", "一下", "若干", "哪个", "哪些",
    "什么", "怎么", "如何", "为啥", "为什么",
})


def _cn_tokenize(q: str) -> List[str]:
    """从原始问题中抽取若干“可以拿去 ILIKE”的候选关键字符串。

    算法:
    1. 原始输入;只 strip 后作为第一候选
    2. 依次应用 _CN_QUERY_TRIM_PATTERNS 上的正则, 生成“净化后”的变体(取group或空)
    3. 过滤空字符串、去过抖、CJK字符<2 的项

    返回: 按优先级排序的不重复候选列表(原始串在前面)。
    """
    if not q:
        return []
    original = q.strip()
    if not original:
        return []
    candidates: List[str] = []

    def _add(s: str) -> None:
        s = s.strip()
        if not s or len(s) < 2:
            return
        if all(ch in _CN_STOPWORDS for ch in s):
            return
        if s not in candidates:
            candidates.append(s)

    _add(original)

    # 逐次应用裁剪正则, 最多 4 轮防正循环
    cur = original
    for _ in range(4):
        prev = cur
        for pat, repl in _CN_QUERY_TRIM_PATTERNS:
            nxt = pat.sub(repl, cur).strip()
            if nxt and nxt != cur:
                _add(nxt)
                cur = nxt
        if cur == prev:
            break

    return candidates


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
    base = (
        select(Courseware)
        .options(
            selectinload(Courseware.tags),
            selectinload(Courseware.access_tokens),
            selectinload(Courseware.materials),
            selectinload(Courseware.category),
        )
        .order_by(Courseware.updated_at.desc())
        .limit(size)
    )

    if keyword:
        from app.models.tag import Tag
        from app.models.association import courseware_tag

        candidates = _cn_tokenize(keyword)

        # OR 多个候选 ILIKE, 默认取最大集合;避免句子里骠说明话后漏检
        or_clauses = []
        seen_ids: set = set()
        for cand in candidates:
            pattern = f"%{cand}%"
            or_clauses.append(
                or_(
                    Courseware.title.ilike(pattern),
                    Courseware.author.ilike(pattern),
                    Courseware.description.ilike(pattern),
                )
            )
        # 用 EXISTS 联合 tag.name 匹配, 避免大表 JOIN 成本
        from sqlalchemy import exists
        tag_match_expr = exists().where(
            (Tag.id == courseware_tag.c.tag_id)
            & (courseware_tag.c.courseware_id == Courseware.id)
            & or_(*[Tag.name.ilike(f"%{c}%") for c in candidates])
        )
        if or_clauses:
            base = base.where(or_(*or_clauses) | tag_match_expr)

    rows = db.scalars(base).all()
    from app.services.courseware import _to_item  # 局部复用,避免循环

    return [_to_item(db, r, downloadable=False) for r in rows]  # type: ignore[arg-type]  # noqa: E501


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
            items.append(_to_item(db, obj, downloadable=False))
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
