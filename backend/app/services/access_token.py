"""访问令牌(AccessToken)业务服务。

业务规则:
- R-04b  label 全局唯一;非空;≤50 字符
- R-09   RESTRICTED 课件创建/更新时需 ≥1 token
- R-10   删除被引用的 token → token_referenced
- R-11   至少保留 1 个 active token → last_token_required
- R-12   课件从 RESTRICTED 降级为 OPEN 时,自动解绑 token
- 安全   数据库只存 sha256(明文);明文仅创建/重新生成时一次性返回
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import BusinessError, ErrorCode
from app.models.access_token import AccessToken
from app.models.association import courseware_access_token
from app.services import audit


LABEL_MAX_LEN = 50
PLAIN_BYTES = 24  # 生成 24 字符 base36 随机值


def _hash_token(plain: str) -> str:
    return hashlib.sha256(plain.encode("utf-8")).hexdigest()


def _ensure_label(label: str) -> str:
    s = (label or "").strip()
    if not s:
        raise BusinessError(ErrorCode.TOKEN_LABEL_REQUIRED, "请填写令牌标签")
    if len(s) > LABEL_MAX_LEN:
        raise BusinessError(ErrorCode.TOKEN_LABEL_TOO_LONG, f"标签长度需 ≤ {LABEL_MAX_LEN}")
    return s


def _generate_plain() -> str:
    """生成 24 位 base36(全小写字母+数字)随机值。"""
    raw = secrets.token_bytes(16)
    n = int.from_bytes(raw, "big")
    chars = "0123456789abcdefghijklmnopqrstuvwxyz"
    out = []
    while n > 0 and len(out) < PLAIN_BYTES:
        n, r = divmod(n, 36)
        out.append(chars[r])
    return "".join(out).ljust(PLAIN_BYTES, "0")[:PLAIN_BYTES]


def get(db: Session, token_id: int) -> AccessToken:
    obj = db.get(AccessToken, token_id)
    if not obj:
        raise BusinessError(ErrorCode.TOKEN_NOT_FOUND, "令牌不存在")
    return obj


def _is_last_active(db: Session, exclude_id: Optional[int] = None) -> bool:
    """除自身外是否还有 active token。"""
    stmt = select(func.count(AccessToken.id))
    if exclude_id is not None:
        stmt = stmt.where(AccessToken.id != exclude_id)
    total = db.execute(stmt).scalar_one()
    return total == 0


def create(db: Session, *, label: str) -> Dict[str, str]:
    """创建新令牌:返回 {id, label, value, valueHash, createdAt}。"""
    clean_label = _ensure_label(label)
    # 重名检查
    existing = db.execute(
        select(AccessToken).where(AccessToken.label == clean_label)
    ).scalar_one_or_none()
    if existing:
        raise BusinessError(ErrorCode.TOKEN_LABEL_CONFLICT, "标签已存在")

    plain = _generate_plain()
    obj = AccessToken(label=clean_label, value_hash=_hash_token(plain))
    db.add(obj)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise BusinessError(ErrorCode.TOKEN_LABEL_CONFLICT, "标签已存在") from e
    db.refresh(obj)
    audit.write("token.create", resource=f"token:{obj.id}", payload={"label": clean_label})
    return {
        "id": str(obj.id),
        "label": obj.label,
        "value": plain,
        "valueHash": obj.value_hash,
        "createdAt": obj.created_at.isoformat() if obj.created_at else None,
    }


def regenerate(db: Session, token_id: int) -> Dict[str, str]:
    """重新生成 token:返回新明文 + 新 hash(旧 hash 即刻失效)。"""
    obj = get(db, token_id)
    plain = _generate_plain()
    obj.value_hash = _hash_token(plain)
    obj.regenerated_at = datetime.now(tz=timezone.utc)
    db.commit()
    db.refresh(obj)
    audit.write(
        "token.regenerate", resource=f"token:{obj.id}", payload={"label": obj.label}
    )
    return {
        "id": str(obj.id),
        "label": obj.label,
        "value": plain,
        "valueHash": obj.value_hash,
        "regeneratedAt": obj.regenerated_at.isoformat() if obj.regenerated_at else None,
    }


def delete(db: Session, token_id: int) -> None:
    obj = get(db, token_id)
    # 检查是否被课件引用(R-10)
    ref = db.execute(
        select(func.count(courseware_access_token.c.courseware_id)).where(
            courseware_access_token.c.access_token_id == token_id
        )
    ).scalar_one()
    if ref:
        raise BusinessError(ErrorCode.TOKEN_REFERENCED, "仍有课件引用此令牌，无法删除")
    # 最后 1 个 active token(R-11)
    if _is_last_active(db, exclude_id=token_id):
        raise BusinessError(ErrorCode.LAST_TOKEN_REQUIRED, "至少保留 1 个令牌")
    label = obj.label
    db.delete(obj)
    db.commit()
    audit.write("token.delete", resource=f"token:{token_id}", payload={"label": label})


def list_paged(
    db: Session,
    *,
    keyword: Optional[str],
    page: int,
    size: int,
) -> dict:
    base = select(AccessToken)
    if keyword:
        base = base.where(AccessToken.label.ilike(f"%{keyword}%"))
    total = db.execute(
        select(func.count()).select_from(base.subquery())
    ).scalar_one()
    items = (
        db.execute(
            base.order_by(AccessToken.id.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        .scalars()
        .all()
    )
    # 引用计数
    count_subq = (
        select(
            courseware_access_token.c.access_token_id,
            func.count(courseware_access_token.c.courseware_id).label("c"),
        )
        .group_by(courseware_access_token.c.access_token_id)
        .subquery()
    )
    counts = dict(db.execute(select(count_subq.c.access_token_id, count_subq.c.c)).all())
    return {
        "page": page,
        "size": size,
        "total": int(total),
        "items": [
            {
                "id": t.id,
                "label": t.label,
                "valueHash": t.value_hash,  # 仅哈希
                "coursewareCount": int(counts.get(t.id, 0)),
                "createdAt": t.created_at.isoformat() if t.created_at else None,
                "regeneratedAt": (
                    t.regenerated_at.isoformat() if t.regenerated_at else None
                ),
            }
            for t in items
        ],
    }


def verify(db: Session, plaintext: str) -> Optional[AccessToken]:
    """明文 token → 查找到的 AccessToken 或 None(常量时间比对)。"""
    if not plaintext:
        return None
    target_hash = _hash_token(plaintext)
    # 取所有 active token(实际场景通常 1-5 个,足够轻量)
    rows = db.execute(select(AccessToken)).scalars().all()
    import hmac as _hmac

    for r in rows:
        if _hmac.compare_digest(r.value_hash, target_hash):
            return r
    return None


def get_by_hash(db: Session, value_hash: str) -> Optional[AccessToken]:
    if not value_hash:
        return None
    return (
        db.execute(select(AccessToken).where(AccessToken.value_hash == value_hash))
        .scalars()
        .first()
    )


def list_by_ids(db: Session, ids: List[int]) -> List[AccessToken]:
    if not ids:
        return []
    return db.execute(select(AccessToken).where(AccessToken.id.in_(ids))).scalars().all()


__all__ = [
    "create",
    "regenerate",
    "delete",
    "list_paged",
    "get",
    "verify",
    "get_by_hash",
    "list_by_ids",
    "_hash_token",
    "_is_last_active",
]