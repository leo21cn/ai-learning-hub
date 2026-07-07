"""分类(Category)业务服务:树形 CRUD + 业务规则。"""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.errors import BusinessError, ErrorCode
from app.models.category import Category
from app.models.courseware import Courseware


MAX_LEVEL = 3


def _ensure_name(name: str) -> str:
    n = (name or "").strip()
    if not n:
        raise BusinessError(ErrorCode.CATEGORY_NAME_REQUIRED, "请输入分类名称")
    if len(n) > 30:
        raise BusinessError(ErrorCode.CATEGORY_NAME_REQUIRED, "分类名称长度需 ≤ 30")
    return n


def get_tree(db: Session) -> List[Category]:
    """返回完整 3 级树(按 name 排序)。"""
    rows = (
        db.execute(select(Category).order_by(Category.level, Category.name))
        .scalars()
        .all()
    )
    by_id: Dict[int, Category] = {c.id: c for c in rows}
    roots: List[Category] = []
    for c in rows:
        c.children.clear()  # type: ignore[attr-defined]
        if c.parent_id and c.parent_id in by_id:
            by_id[c.parent_id].children.append(c)  # type: ignore[attr-defined]
        else:
            roots.append(c)
    return roots


def get(db: Session, category_id: int) -> Category:
    obj = db.get(Category, category_id)
    if not obj:
        raise BusinessError(ErrorCode.CATEGORY_NOT_FOUND, "分类不存在")
    return obj


def create(db: Session, *, name: str, parent_id: Optional[int]) -> Category:
    n = _ensure_name(name)
    if parent_id is None:
        level = 1
    else:
        parent = get(db, parent_id)
        level = parent.level + 1
        if level > MAX_LEVEL:
            raise BusinessError(ErrorCode.CATEGORY_MAX_LEVEL, "分类最多支持 3 层")
    # 同父节点下名称唯一
    existing = db.execute(
        select(Category).where(Category.parent_id.is_(parent_id) if parent_id is None else Category.parent_id == parent_id)
        .where(Category.name == n)
    ).scalar_one_or_none()
    if existing:
        raise BusinessError(ErrorCode.CATEGORY_NAME_CONFLICT, "同一父节点下名称已存在")
    obj = Category(name=n, parent_id=parent_id, level=level)
    db.add(obj)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise BusinessError(ErrorCode.CATEGORY_NAME_CONFLICT, "同一父节点下名称已存在") from e
    db.refresh(obj)
    return obj


def update(db: Session, category_id: int, *, name: str) -> Category:
    obj = get(db, category_id)
    obj.name = _ensure_name(name)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise BusinessError(ErrorCode.CATEGORY_NAME_CONFLICT, "同一父节点下名称已存在") from e
    db.refresh(obj)
    return obj


def delete(db: Session, category_id: int) -> None:
    obj = get(db, category_id)
    # 有子节点?
    has_child = (
        db.execute(select(func.count(Category.id)).where(Category.parent_id == category_id))
        .scalar_one()
    )
    if has_child:
        raise BusinessError(ErrorCode.CATEGORY_HAS_CHILDREN, "存在子分类，无法删除")
    # 仍被课件引用?(即便课件在子分类下 — 实际上这里只看直接引用;业务规则写"被课件引用"指的是当前分类)
    has_cw = (
        db.execute(
            select(func.count(Courseware.id)).where(Courseware.category_id == category_id)
        )
        .scalar_one()
    )
    if has_cw:
        raise BusinessError(ErrorCode.CATEGORY_HAS_COURSEWARES, "分类下仍有课件，无法删除")
    db.delete(obj)
    db.commit()


def collect_subtree_ids(db: Session, root_id: int) -> List[int]:
    """返回包含 root_id 及其所有后代 id 的列表(BFS)。

    若 root_id 不存在则返回空列表,以便调用方直接短路返回空页。
    """
    if db.get(Category, root_id) is None:
        return []
    out: List[int] = [root_id]
    queue: List[int] = [root_id]
    by_parent: Dict[Optional[int], List[int]] = {}
    for cid, pid in db.execute(select(Category.id, Category.parent_id)).all():
        by_parent.setdefault(pid, []).append(cid)
    while queue:
        cur = queue.pop(0)
        for cid in by_parent.get(cur, []):
            out.append(cid)
            queue.append(cid)
    return out


def list_leaf_ids(db: Session) -> Sequence[int]:
    """返回所有 level=3 的 id 列表(供课程管理校验)。"""
    return tuple(
        db.execute(select(Category.id).where(Category.level == MAX_LEVEL))
        .scalars()
        .all()
    )


__all__ = [
    "MAX_LEVEL",
    "get_tree",
    "get",
    "create",
    "update",
    "delete",
    "list_leaf_ids",
    "collect_subtree_ids",
]
