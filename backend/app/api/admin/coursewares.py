"""课件(Courseware)管理 API。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.middleware.admin_auth import get_admin_principal
from app.schemas import ok
from app.schemas.courseware import (
    CoursewareCreateRequest,
    CoursewareUpdateRequest,
)
from app.services import courseware as svc

router = APIRouter(
    prefix="/api/admin/coursewares",
    tags=["admin/coursewares"],
    dependencies=[Depends(get_admin_principal)],
)


@router.get("")
def list_coursewares(
    keyword: str | None = Query(None),
    category_id: int | None = Query(None),
    access_mode: str | None = Query(None, alias="accessMode"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),  # type: ignore[no-untyped-def]
):
    data = svc.list_paged(
        db,
        keyword=keyword,
        category_id=category_id,
        access_mode=access_mode,
        page=page,
        size=size,
    )
    return ok(data=data)


@router.get("/{courseware_id}")
def get_courseware(
    courseware_id: int, db: Session = Depends(get_db)  # type: ignore[no-untyped-def]
):
    obj = svc.get(db, courseware_id)
    return ok(data=svc._to_item(obj, downloadable=True))


@router.post("", status_code=status.HTTP_201_CREATED)
def create_courseware(
    payload: CoursewareCreateRequest,
    db: Session = Depends(get_db),  # type: ignore[no-untyped-def]
):
    obj = svc.create(
        db,
        title=payload.title,
        category_id=payload.categoryId,
        author=payload.author,
        description=payload.description,
        access_mode=payload.accessMode,
        tag_ids=payload.tagIds,
        material_ids=payload.materialIds,
        token_ids=payload.tokenIds,
    )
    return ok(data=svc._to_item(obj, downloadable=True))


@router.put("/{courseware_id}")
def update_courseware(
    courseware_id: int,
    payload: CoursewareUpdateRequest,
    db: Session = Depends(get_db),  # type: ignore[no-untyped-def]
):
    obj = svc.update(
        db,
        courseware_id,
        title=payload.title,
        author=payload.author,
        description=payload.description,
        category_id=payload.categoryId,
        access_mode=payload.accessMode,
        tag_ids=payload.tagIds,
        material_ids=payload.materialIds,
        token_ids=payload.tokenIds,
    )
    return ok(data=svc._to_item(obj, downloadable=True))


@router.delete("/{courseware_id}")
def delete_courseware(
    courseware_id: int, db: Session = Depends(get_db)  # type: ignore[no-untyped-def]
):
    svc.delete(db, courseware_id)
    return ok(data=None)


__all__ = ["router"]