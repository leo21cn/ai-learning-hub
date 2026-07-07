"""课件(Courseware)业务服务。

业务规则:
- R-01 课件必须挂载到 3 级叶子分类节点
- R-02 标题非空,≤100 字符
- R-03 accessMode=RESTRICTED 时 accessTokens 至少 1 个
- R-12 accessMode 从 RESTRICTED 降级为 OPEN 时自动清空 token 绑定
- 删除:级联清空关联表(courseware_tag/courseware_material/courseware_access_token)
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import BusinessError, ErrorCode
from app.models.category import Category
from app.models.courseware import AccessMode, Courseware
from app.models.material import Material
from app.models.tag import Tag
from app.services import access_token as token_svc
from app.services import audit
from app.services import category as cat_svc


TITLE_MAX_LEN = 100


def _ensure_title(title: str) -> str:
    t = (title or "").strip()
    if not t:
        raise BusinessError(ErrorCode.COURSEWARE_TITLE_REQUIRED, "请填写课件标题")
    if len(t) > TITLE_MAX_LEN:
        raise BusinessError(ErrorCode.COURSEWARE_TITLE_REQUIRED, f"标题长度需 ≤ {TITLE_MAX_LEN}")
    return t


def _normalize_token_ids(token_ids: Optional[List[int]]) -> List[int]:
    if not token_ids:
        return []
    # 去重 + 过滤无效
    return sorted({int(x) for x in token_ids if x is not None})


def get(
    db: Session,
    courseware_id: int,
    *,
    with_relations: bool = True,
) -> Courseware:
    stmt = select(Courseware).where(Courseware.id == courseware_id)
    if with_relations:
        stmt = stmt.options(
            selectinload(Courseware.tags),
            selectinload(Courseware.materials),
            selectinload(Courseware.access_tokens),
        )
    obj = db.execute(stmt).scalars().first()
    if not obj:
        raise BusinessError(ErrorCode.COURSEWARE_NOT_FOUND, "课件不存在")
    return obj


def get_many(db: Session, courseware_ids: List[int]) -> List[Courseware]:
    """按 ID 批量拉取课件（带 access_tokens 关联）。不存在/空集合返回空列表。"""
    if not courseware_ids:
        return []
    rows = db.execute(
        select(Courseware)
        .where(Courseware.id.in_(courseware_ids))
        .options(selectinload(Courseware.access_tokens))
    ).scalars().all()
    return list(rows)


def _resolve_category(db: Session, category_id: int) -> Category:
    if not category_id:
        raise BusinessError(ErrorCode.COURSEWARE_CATEGORY_REQUIRED, "请选择分类")
    cat = db.get(Category, category_id)
    if not cat:
        raise BusinessError(ErrorCode.COURSEWARE_CATEGORY_REQUIRED, "分类不存在")
    # R-01:课件必须挂载到叶子节点(level=3),不允许挂在 1/2 级
    if cat.level != 3:
        raise BusinessError(
            ErrorCode.COURSEWARE_CATEGORY_NOT_LEAF, "课件必须挂载到 3 级分类"
        )
    return cat


def _resolve_tags(db: Session, tag_ids: Optional[List[int]]) -> List[Tag]:
    if not tag_ids:
        return []
    rows = db.execute(select(Tag).where(Tag.id.in_(tag_ids))).scalars().all()
    return list(rows)


def _resolve_materials(db: Session, material_ids: Optional[List[int]]) -> List[Material]:
    if not material_ids:
        return []
    rows = db.execute(select(Material).where(Material.id.in_(material_ids))).scalars().all()
    return list(rows)


def create(
    db: Session,
    *,
    title: str,
    category_id: int,
    author: Optional[str] = None,
    description: Optional[str] = None,
    access_mode: str = AccessMode.OPEN.value,
    tag_ids: Optional[List[int]] = None,
    material_ids: Optional[List[int]] = None,
    token_ids: Optional[List[int]] = None,
) -> Courseware:
    """创建课件。返回带关联的 Courseware。"""
    clean_title = _ensure_title(title)
    cat = _resolve_category(db, category_id)
    try:
        mode = AccessMode(access_mode)
    except ValueError:
        mode = AccessMode.OPEN

    tag_objs = _resolve_tags(db, tag_ids)
    mat_objs = _resolve_materials(db, material_ids)
    tok_objs = token_svc.list_by_ids(db, _normalize_token_ids(token_ids))

    if mode == AccessMode.RESTRICTED:
        if not tok_objs:
            raise BusinessError(
                ErrorCode.COURSEWARE_TOKEN_REQUIRED, "受限课件需至少绑定 1 个令牌"
            )

    obj = Courseware(
        title=clean_title,
        author=(author or "").strip() or None,
        description=description,
        access_mode=mode,
        category_id=cat.id,
    )
    obj.tags = tag_objs
    obj.materials = mat_objs
    obj.access_tokens = tok_objs
    db.add(obj)
    db.commit()
    db.refresh(obj)
    audit.write(
        "courseware.create",
        resource=f"courseware:{obj.id}",
        payload={"title": clean_title, "accessMode": mode.value},
    )
    return obj


def update(
    db: Session,
    courseware_id: int,
    *,
    title: Optional[str] = None,
    category_id: Optional[int] = None,
    author: Optional[str] = None,
    description: Optional[str] = None,
    access_mode: Optional[str] = None,
    tag_ids: Optional[List[int]] = None,
    material_ids: Optional[List[int]] = None,
    token_ids: Optional[List[int]] = None,
) -> Courseware:
    """更新课件;None 表示不修改。token_ids 不为 None 时按传入值重置绑定。

    R-12:从 RESTRICTED → OPEN 时,自动清空 token 绑定。
    """
    obj = get(db, courseware_id)
    if title is not None:
        obj.title = _ensure_title(title)
    if author is not None:
        obj.author = (author or "").strip() or None
    if description is not None:
        obj.description = description
    if category_id is not None:
        _resolve_category(db, category_id)
        obj.category_id = category_id
    if access_mode is not None:
        try:
            new_mode = AccessMode(access_mode)
        except ValueError:
            raise BusinessError(
                ErrorCode.INTERNAL_ERROR, f"不支持的 accessMode: {access_mode}"
            )
        # R-12 降级清空
        if obj.access_mode == AccessMode.RESTRICTED and new_mode == AccessMode.OPEN:
            obj.access_tokens = []
        obj.access_mode = new_mode
    if tag_ids is not None:
        obj.tags = _resolve_tags(db, tag_ids)
    if material_ids is not None:
        obj.materials = _resolve_materials(db, material_ids)
    if token_ids is not None:
        if obj.access_mode == AccessMode.OPEN:
            # OPEN 模式忽略 token 绑定(防止误传)
            obj.access_tokens = []
        else:
            toks = token_svc.list_by_ids(db, _normalize_token_ids(token_ids))
            if not toks:
                raise BusinessError(
                    ErrorCode.COURSEWARE_TOKEN_REQUIRED, "受限课件需至少绑定 1 个令牌"
                )
            obj.access_tokens = toks

    db.commit()
    db.refresh(obj)
    audit.write(
        "courseware.update",
        resource=f"courseware:{obj.id}",
        payload={"accessMode": obj.access_mode.value},
    )
    return obj


def delete(db: Session, courseware_id: int) -> None:
    obj = get(db, courseware_id)
    db.delete(obj)  # 关联表 ON DELETE CASCADE 自动清空
    db.commit()
    audit.write("courseware.delete", resource=f"courseware:{courseware_id}")


# ============ 列表 / 搜索 ============

def _to_item(obj: Courseware, *, downloadable: bool = False) -> Dict[str, Any]:
    item = {
        "id": obj.id,
        "title": obj.title,
        "author": obj.author,
        "categoryId": obj.category_id,
        "categoryName": obj.category.name if obj.category else None,
        "description": obj.description,
        "accessMode": obj.access_mode.value,
        "tagIds": [t.id for t in (obj.tags or [])],
        "tagNames": [t.name for t in (obj.tags or [])],
        "materialIds": [m.id for m in (obj.materials or [])],
        "tokenIds": [t.id for t in (obj.access_tokens or [])],
        "createdAt": obj.created_at.isoformat() if obj.created_at else None,
        "updatedAt": obj.updated_at.isoformat() if obj.updated_at else None,
    }
    if downloadable:
        item["materials"] = [
            {
                "id": m.id,
                "name": m.name,
                "type": m.type,
                "sizeBytes": int(m.size_bytes),
                "duration": m.duration_or_pages,
                "downloadUrl": f"/api/public/materials/{m.id}/file",
                "streamUrl": f"/api/public/materials/{m.id}/stream",
            }
            for m in (obj.materials or [])
        ]
    return item


def list_paged(
    db: Session,
    *,
    keyword: Optional[str],
    category_id: Optional[int],
    access_mode: Optional[str],
    page: int,
    size: int,
) -> dict:
    base = select(Courseware).options(
        selectinload(Courseware.tags),
        selectinload(Courseware.materials),
        selectinload(Courseware.access_tokens),
        selectinload(Courseware.category),
    )
    if keyword:
        like = f"%{keyword}%"
        base = base.where(
            or_(
                Courseware.title.ilike(like),
                Courseware.author.ilike(like),
                Courseware.description.ilike(like),
            )
        )
    if category_id:
        # 子树过滤:选 L1/L2 节点时,后端会拉出该节点及其所有后代分类下的课件;
        # 选 L3 叶子时等价于精确匹配(叶子节点无后代)。
        subtree_ids = cat_svc.collect_subtree_ids(db, category_id)
        if not subtree_ids:
            return {"items": [], "page": page, "size": size, "total": 0}
        base = base.where(Courseware.category_id.in_(subtree_ids))
    if access_mode:
        try:
            base = base.where(Courseware.access_mode == AccessMode(access_mode))
        except ValueError:
            pass
    total = db.execute(select(func.count()).select_from(base.subquery())).scalar_one()
    items = (
        db.execute(
            base.order_by(Courseware.id.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        .scalars()
        .all()
    )
    return {
        "page": page,
        "size": size,
        "total": int(total),
        "items": [_to_item(o) for o in items],
    }


def search_public(
    db: Session,
    *,
    keyword: Optional[str],
    page: int,
    size: int,
) -> List[Dict[str, Any]]:
    """前台搜索(不过滤 RESTRICTED,但标记 mode)。返回列表,无分页元数据。"""
    base = (
        select(Courseware)
        .options(
            selectinload(Courseware.tags),
            selectinload(Courseware.materials),
            selectinload(Courseware.access_tokens),
            selectinload(Courseware.category),
        )
        .order_by(Courseware.id.desc())
    )
    if keyword:
        like = f"%{keyword}%"
        base = base.where(
            or_(
                Courseware.title.ilike(like),
                Courseware.author.ilike(like),
                Courseware.description.ilike(like),
            )
        )
    rows = db.execute(base.offset((page - 1) * size).limit(size)).scalars().all()
    return [_to_item(o) for o in rows]


__all__ = [
    "create",
    "update",
    "delete",
    "get",
    "get_many",
    "list_paged",
    "search_public",
    "_to_item",
]
