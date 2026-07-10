"""AccessToken 管理 API。"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.middleware.admin_auth import get_admin_principal
from app.models.association import courseware_access_token
from app.schemas import ok
from app.schemas.access_token import (
    AccessTokenCreateRequest,
    AccessTokenCreatedResponse,
)
from app.services import access_token as svc
from app.services import access_token_usage as usage_svc

router = APIRouter(
    prefix="/api/admin/access-tokens",
    tags=["admin/access-tokens"],
    dependencies=[Depends(get_admin_principal)],
)


def _serialize_token(obj, *, courseware_count: int = 0) -> Dict[str, Any]:
    """把 AccessToken ORM 对象序列化为 dict(与 AccessTokenItem 字段对齐)。"""
    return {
        "id": int(obj.id),
        "label": obj.label,
        "valueHash": obj.value_hash,
        "coursewareCount": int(courseware_count),
        "createdAt": (
            obj.created_at.isoformat()
            if obj.created_at is not None
            else None
        ),
        "regeneratedAt": (
            obj.regenerated_at.isoformat()
            if obj.regenerated_at is not None
            else None
        ),
    }


def _count_coursewares(db: Session, token_id: int) -> int:
    """token 被多少课件引用。"""
    return int(
        db.execute(
            select(func.count(courseware_access_token.c.courseware_id)).where(
                courseware_access_token.c.access_token_id == token_id
            )
        ).scalar_one()
        or 0
    )


@router.get("")
def list_tokens(
    keyword: str | None = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),  # type: ignore[no-untyped-def]
):
    data = svc.list_paged(db, keyword=keyword, page=page, size=size)
    return ok(data=data)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_token(
    payload: AccessTokenCreateRequest, db: Session = Depends(get_db),  # type: ignore[no-untyped-def]
):
    data = svc.create(db, label=payload.label)
    return ok(data=AccessTokenCreatedResponse(**data).model_dump())


@router.get("/{token_id}")
def get_token(
    token_id: int,
    with_usage: bool = Query(
        False,
        alias="withUsage",
        description=(
            "是否附加 usageSummary(总停留/次数/课件/素材),"
            "默认不附加,避免列表页 N+1"
        ),
    ),
    db: Session = Depends(get_db),  # type: ignore[no-untyped-def]
):
    """取单条 access token 详情。

    Spec §3.2:维持现有接口;扩展返回 `usageSummary` 字段(仅在 URL 带
    `?withUsage=1` 时计算,默认不计算)。summary 来自全时段聚合的
    access_session。
    """
    obj = svc.get(db, token_id)  # 404 if not found
    item = _serialize_token(obj, courseware_count=_count_coursewares(db, token_id))
    if with_usage:
        item["usageSummary"] = usage_svc.summary_overall(db, token_id)
    return ok(data=item)


@router.post("/{token_id}/regenerate")
def regenerate_token(
    token_id: int, db: Session = Depends(get_db),  # type: ignore[no-untyped-def]
):
    data = svc.regenerate(db, token_id)
    return ok(data=AccessTokenCreatedResponse(**data).model_dump())


@router.delete("/{token_id}")
def delete_token(token_id: int, db: Session = Depends(get_db)):  # type: ignore[no-untyped-def]
    svc.delete(db, token_id)
    return ok(data=None)


__all__ = ["router"]
