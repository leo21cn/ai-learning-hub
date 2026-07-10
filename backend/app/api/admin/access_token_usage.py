"""管理 API:访问令牌 · 访问记录查询与按素材聚合。"""
from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.middleware.admin_auth import get_admin_principal
from app.schemas import ok
from app.schemas.access_token_usage import (
    AccessSessionPaged,
    AccessSessionSummary,
    MaterialUsagePaged,
)
from app.services import access_token_usage as svc

router = APIRouter(
    prefix="/api/admin/access-tokens",
    tags=["admin/access-token-usage"],
    dependencies=[Depends(get_admin_principal)],
)


def _default_range() -> tuple[str, str]:
    """默认 start=今天-6, end=今天(近 7 天)。"""
    today = date.today()
    return (today - timedelta(days=6)).isoformat(), today.isoformat()


@router.get("/{token_id}/access-sessions", response_model=None)
def list_sessions(
    token_id: int,
    start: str = Query(..., description="起 YYYY-MM-DD(默认近 7 天)"),
    end: str = Query(..., description="止 YYYY-MM-DD(默认近 7 天)"),
    material_id: int | None = Query(None, ge=1, alias="materialId"),
    courseware_id: int | None = Query(None, ge=1, alias="coursewareId"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),  # type: ignore[no-untyped-def]
):
    """某 token 在时间段内的访问台账(分页 + 区间聚合)。"""
    if not start or not end:
        start, end = _default_range()
    data = svc.list_sessions(
        db,
        token_id=token_id,
        start=start,
        end=end,
        material_id=material_id,
        courseware_id=courseware_id,
        page=page,
        size=size,
    )
    return ok(data=AccessSessionPaged(**data).model_dump())


@router.get(
    "/{token_id}/access-sessions/summary", response_model=None
)
def sessions_summary(
    token_id: int,
    start: str = Query(..., description="起 YYYY-MM-DD"),
    end: str = Query(..., description="止 YYYY-MM-DD"),
    db: Session = Depends(get_db),  # type: ignore[no-untyped-def]
):
    """某 token 在时间段内的 4 项聚合指标(总停留 / 次数 / 课件数 / 素材数)。

    供访问记录页首屏概览卡使用,避免拉全量台账(items)。
    """
    if not start or not end:
        start, end = _default_range()
    data = svc.summary_in_range(
        db, token_id=token_id, start=start, end=end
    )
    return ok(data=AccessSessionSummary(**data).model_dump())


@router.get(
    "/{token_id}/access-sessions/material-summary", response_model=None
)
def material_summary(
    token_id: int,
    start: str = Query(..., description="起 YYYY-MM-DD"),
    end: str = Query(..., description="止 YYYY-MM-DD"),
    db: Session = Depends(get_db),  # type: ignore[no-untyped-def]
):
    """按素材聚合(本期重点):返回该 token 在时间段内每个素材的
    累计停留时长 / 访问次数 / 最近一次访问时间。
    """
    if not start or not end:
        start, end = _default_range()
    data = svc.list_material_summary(
        db, token_id=token_id, start=start, end=end
    )
    return ok(data=MaterialUsagePaged(**data).model_dump())


__all__ = ["router"]
