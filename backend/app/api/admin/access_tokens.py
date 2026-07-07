"""AccessToken 管理 API。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.middleware.admin_auth import get_admin_principal
from app.schemas import ok
from app.schemas.access_token import (
    AccessTokenCreateRequest,
    AccessTokenCreatedResponse,
)
from app.services import access_token as svc

router = APIRouter(
    prefix="/api/admin/access-tokens",
    tags=["admin/access-tokens"],
    dependencies=[Depends(get_admin_principal)],
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
    payload: AccessTokenCreateRequest, db: Session = Depends(get_db)  # type: ignore[no-untyped-def]
):
    data = svc.create(db, label=payload.label)
    return ok(data=AccessTokenCreatedResponse(**data).model_dump())


@router.post("/{token_id}/regenerate")
def regenerate_token(
    token_id: int, db: Session = Depends(get_db)  # type: ignore[no-untyped-def]
):
    data = svc.regenerate(db, token_id)
    return ok(data=AccessTokenCreatedResponse(**data).model_dump())


@router.delete("/{token_id}")
def delete_token(token_id: int, db: Session = Depends(get_db)):  # type: ignore[no-untyped-def]
    svc.delete(db, token_id)
    return ok(data=None)


__all__ = ["router"]