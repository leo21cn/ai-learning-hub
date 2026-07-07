"""标签管理 API。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.middleware.admin_auth import get_admin_principal
from app.schemas import ok
from app.schemas.tag import TagNameRequest
from app.services import tag as svc

router = APIRouter(
    prefix="/api/admin/tags",
    tags=["admin/tags"],
    dependencies=[Depends(get_admin_principal)],
)


@router.get("")
def list_tags(
    keyword: str | None = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),  # type: ignore[no-untyped-def]
):
    data = svc.list_paged(db, keyword=keyword, page=page, size=size)
    return ok(data=data)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_tag(payload: TagNameRequest, db: Session = Depends(get_db)):  # type: ignore[no-untyped-def]
    obj = svc.create(db, name=payload.name)
    return ok(
        data={
            "id": obj.id,
            "name": obj.name,
            "createdAt": obj.created_at.isoformat() if obj.created_at else None,
        }
    )


@router.put("/{tag_id}")
def rename_tag(
    tag_id: int,
    payload: TagNameRequest,
    db: Session = Depends(get_db),  # type: ignore[no-untyped-def]
):
    obj = svc.update(db, tag_id, name=payload.name)
    return ok(
        data={
            "id": obj.id,
            "name": obj.name,
            "createdAt": obj.created_at.isoformat() if obj.created_at else None,
        }
    )


@router.delete("/{tag_id}")
def delete_tag(tag_id: int, db: Session = Depends(get_db)):  # type: ignore[no-untyped-def]
    svc.delete(db, tag_id)
    return ok(data=None)


__all__ = ["router"]
