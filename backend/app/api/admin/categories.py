"""分类管理 API。"""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.middleware.admin_auth import get_admin_principal
from app.schemas import ok
from app.schemas.category import CategoryCreateRequest, CategoryNode, CategoryRenameRequest
from app.services import category as svc

router = APIRouter(
    prefix="/api/admin/categories",
    tags=["admin/categories"],
    dependencies=[Depends(get_admin_principal)],
)


def _to_node(c) -> CategoryNode:  # type: ignore[no-untyped-def]
    return CategoryNode(
        id=c.id,
        name=c.name,
        level=c.level,
        parentId=c.parent_id,
        children=[_to_node(ch) for ch in (c.children or [])],
    )


@router.get("")
def list_categories(db: Session = Depends(get_db)):  # type: ignore[no-untyped-def]
    tree = svc.get_tree(db)
    return ok(data=[_to_node(c).model_dump() for c in tree])


@router.post("", status_code=status.HTTP_201_CREATED)
def create_category(
    payload: CategoryCreateRequest, db: Session = Depends(get_db)  # type: ignore[no-untyped-def]
):
    obj = svc.create(db, name=payload.name, parent_id=payload.parentId)
    return ok(
        data={
            "id": obj.id,
            "parentId": obj.parent_id,
            "level": obj.level,
            "name": obj.name,
        }
    )


@router.put("/{category_id}")
def rename_category(
    category_id: int,
    payload: CategoryRenameRequest,
    db: Session = Depends(get_db),  # type: ignore[no-untyped-def]
):
    obj = svc.update(db, category_id, name=payload.name)
    return ok(
        data={
            "id": obj.id,
            "parentId": obj.parent_id,
            "level": obj.level,
            "name": obj.name,
        }
    )


@router.delete("/{category_id}")
def delete_category(category_id: int, db: Session = Depends(get_db)):  # type: ignore[no-untyped-def]
    svc.delete(db, category_id)
    return ok(data=None)


__all__ = ["router"]
