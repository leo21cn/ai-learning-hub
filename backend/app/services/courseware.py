"""课件(Courseware)业务服务。

业务规则:
- R-01 课件可挂载到分类树任意层级节点(1 级 / 2 级 / 3 级叶子)
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
    # R-01:课件可挂接到分类树的任意层级节点(1 级 / 2 级 / 3 级叶子),
    # 不再限制必须为 3 级叶子。
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
    # 保留请求方的传入顺序，便于新课件创建时能拿到客户端拖拽后的顺序
    by_id = {m.id: m for m in rows}
    return [by_id[mid] for mid in material_ids if mid in by_id]


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
    db.flush()  # 先让 courseware id 生成,后续 UPDATE 才能定位
    # 显式写入 sort_order,避免依赖 ORM 二次同步导致全部为 0。
    if mat_objs:
        from app.models.association import courseware_material  # noqa: PLC0415

        for idx, m in enumerate(mat_objs):
            db.execute(
                courseware_material.update()
                .where(
                    (courseware_material.c.courseware_id == obj.id)
                    & (courseware_material.c.material_id == m.id)
                )
                .values(sort_order=idx)
            )
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
        # R-20: 集合替换语义——保留原 sortOrder,新素材追加到末尾。
        # 直接用 SQL 操作 courseware_material 表,避免 ORM 二次同步
        # secondary table 时按 new_materials 顺序覆写 sort_order 的副作用。
        from app.models.association import courseware_material  # noqa: PLC0415
    
        old_materials = list(obj.materials or [])
        old_index = {m.id: i for i, m in enumerate(old_materials)}
        max_old = max(old_index.values()) if old_index else -1
        target_set = set(int(mid) for mid in material_ids)
        to_remove = [m.id for m in old_materials if m.id not in target_set]
        to_add = sorted(target_set - set(old_index.keys()))
        # DELETE 被移除的关联行
        if to_remove:
            db.execute(
                courseware_material.delete().where(
                    (courseware_material.c.courseware_id == obj.id)
                    & (courseware_material.c.material_id.in_(to_remove))
                )
            )
        # INSERT 新增的关联行(预留 sort_order=max_old+1..)
        next_ord = max_old + 1
        for mid in to_add:
            db.execute(
                courseware_material.insert().values(
                    courseware_id=obj.id,
                    material_id=mid,
                    sort_order=next_ord,
                )
            )
            next_ord += 1
        db.flush()
        # 过期 ORM 缓存,下次访问 obj.materials 时从 DB 重读
        db.expire(obj, ["materials"])
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

def _to_item(db: Session, obj: Courseware, *, downloadable: bool = False) -> Dict[str, Any]:
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
        # 从关联表读取实际 sort_order,避免用 obj.materials 的下标代替
        # (obj.materials 加载顺序仅在二次同步后才是 sortOrder 语义,
        #  中间过程可能下标错位)。返回字典给 _to_item 使用。
        from app.models.association import courseware_material  # noqa: PLC0415

        so_rows = db.execute(
            select(
                courseware_material.c.material_id,
                courseware_material.c.sort_order,
            ).where(courseware_material.c.courseware_id == obj.id)
        ).all()
        sort_map = {row[0]: int(row[1]) for row in so_rows}
        item["materials"] = [
            {
                "id": m.id,
                "name": m.name,
                "type": m.type,
                "sizeBytes": int(m.size_bytes),
                "duration": m.duration_or_pages,
                "downloadUrl": f"/api/public/materials/{m.id}/file",
                "streamUrl": f"/api/public/materials/{m.id}/stream",
                "sortOrder": sort_map.get(m.id, 0),
            }
            for m in (obj.materials or [])
        ]
    return item


def reorder_materials(
    db: Session,
    courseware_id: int,
    material_ids: List[int],
) -> Courseware:
    """专用排序入口：按数组下标重写 courseware_material.sort_order（0..N-1）。

    校验：
    ① 课件存在（复用 get）；
    ② 数量与当前一致；
    ③ 全部 ID 属于该课件；
    ④ 无重复。

    任意校验失败抛 COURSEWARE_MATERIALS_INVALID。
    """
    obj = get(db, courseware_id)
    current = list(obj.materials or [])
    current_ids = [m.id for m in current]
    current_set = set(current_ids)

    # 重复
    if len(set(material_ids)) != len(material_ids):
        raise BusinessError(
            ErrorCode.COURSEWARE_MATERIALS_INVALID,
            "materialIds 包含重复 ID",
        )
    # 数量一致
    if len(material_ids) != len(current_ids):
        raise BusinessError(
            ErrorCode.COURSEWARE_MATERIALS_INVALID,
            "materialIds 数量与当前课件素材数不一致",
        )
    # 全部属于该课件
    if set(material_ids) != current_set:
        raise BusinessError(
            ErrorCode.COURSEWARE_MATERIALS_INVALID,
            "materialIds 包含未绑定到该课件的 ID",
        )

    # 重写 sort_order（按传入数组下标）
    from app.models.association import courseware_material  # noqa: PLC0415

    for idx, mid in enumerate(material_ids):
        db.execute(
            courseware_material.update()
            .where(
                (courseware_material.c.courseware_id == courseware_id)
                & (courseware_material.c.material_id == mid)
            )
            .values(sort_order=idx)
        )
    db.commit()
    db.refresh(obj)
    audit.write(
        "courseware.reorder_materials",
        resource=f"courseware:{courseware_id}",
        payload={"order": material_ids},
    )
    return obj


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
        "items": [_to_item(db, o) for o in items],
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
    return [_to_item(db, o) for o in rows]


__all__ = [
    "create",
    "update",
    "delete",
    "get",
    "get_many",
    "list_paged",
    "reorder_materials",
    "search_public",
    "_to_item",
]
