"""标签(Tag)业务服务:扁平 CRUD + 业务规则。"""
from __future__ import annotations

from typing import Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import BusinessError, ErrorCode
from app.models.tag import Tag


def _ensure_name(name: str) -> str:
    n = (name or "").strip()
    if not n:
        raise BusinessError(ErrorCode.TAG_NAME_REQUIRED, "请输入标签名")
    if len(n) > 30:
        raise BusinessError(ErrorCode.TAG_NAME_REQUIRED, "标签名长度需 ≤ 30")
    return n


def list_paged(db: Session, *, keyword: Optional[str], page: int, size: int) -> dict:
    base = select(Tag)
    if keyword:
        base = base.where(Tag.name.ilike(f"%{keyword}%"))
    total = db.execute(
        select(func.count()).select_from(base.subquery())
    ).scalar_one()
    items = (
        db.execute(base.order_by(Tag.id.desc()).offset((page - 1) * size).limit(size))
        .scalars()
        .all()
    )
    # 引用计数(避免 N+1,这里示例用子查询)
    from app.models.association import courseware_tag

    count_subq = (
        select(courseware_tag.c.tag_id, func.count(courseware_tag.c.courseware_id).label("c"))
        .group_by(courseware_tag.c.tag_id)
        .subquery()
    )
    counts = dict(
        db.execute(select(count_subq.c.tag_id, count_subq.c.c)).all()
    )
    return {
        "page": page,
        "size": size,
        "total": int(total),
        "items": [
            {
                "id": t.id,
                "name": t.name,
                "coursewareCount": int(counts.get(t.id, 0)),
                "createdAt": t.created_at.isoformat() if t.created_at else None,
            }
            for t in items
        ],
    }


def get(db: Session, tag_id: int) -> Tag:
    obj = db.get(Tag, tag_id)
    if not obj:
        raise BusinessError(ErrorCode.TAG_NOT_FOUND, "标签不存在")
    return obj


def create(db: Session, *, name: str) -> Tag:
    n = _ensure_name(name)
    obj = Tag(name=n)
    db.add(obj)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise BusinessError(ErrorCode.TAG_NAME_CONFLICT, "标签名已存在") from e
    db.refresh(obj)
    return obj


def update(db: Session, tag_id: int, *, name: str) -> Tag:
    obj = get(db, tag_id)
    obj.name = _ensure_name(name)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise BusinessError(ErrorCode.TAG_NAME_CONFLICT, "标签名已存在") from e
    db.refresh(obj)
    return obj


def delete(db: Session, tag_id: int) -> None:
    obj = get(db, tag_id)
    db.delete(obj)
    db.commit()


__all__ = ["list_paged", "get", "create", "update", "delete"]
