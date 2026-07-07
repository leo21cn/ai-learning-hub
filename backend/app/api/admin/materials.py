"""素材管理 API。"""
from __future__ import annotations

import mimetypes
from pathlib import Path

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.middleware.admin_auth import get_admin_principal
from app.schemas import ok
from app.services import material as svc

router = APIRouter(
    prefix="/api/admin/materials",
    tags=["admin/materials"],
    dependencies=[Depends(get_admin_principal)],
)


@router.get("")
def list_materials(
    keyword: str | None = Query(None),
    type: str | None = Query(None, description="VIDEO/PDF/PPT"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),  # type: ignore[no-untyped-def]
):
    data = svc.list_paged(db, keyword=keyword, mtype=type, page=page, size=size)
    return ok(data=data)


@router.post("", status_code=status.HTTP_201_CREATED)
async def upload_material(
    file: UploadFile = File(...),  # type: ignore[no-untyped-def]
    db: Session = Depends(get_db),  # type: ignore[no-untyped-def]
):
    obj = await svc.upload(db, file)
    return ok(
        data={
            "id": obj.id,
            "name": obj.name,
            "type": obj.type,
            "sizeBytes": int(obj.size_bytes),
        }
    )


@router.delete("/{material_id}")
def delete_material(material_id: int, db: Session = Depends(get_db)):  # type: ignore[no-untyped-def]
    svc.delete(db, material_id)
    return ok(data=None)


@router.get("/{material_id}/file")
def download_material(material_id: int, db: Session = Depends(get_db)):  # type: ignore[no-untyped-def]
    obj = svc.get(db, material_id)
    p = Path(obj.storage_path)
    if not p.exists():
        from app.core.errors import BusinessError, ErrorCode

        raise BusinessError(ErrorCode.MATERIAL_STORAGE_UNAVAILABLE, "素材文件已丢失")
    media_type, _ = mimetypes.guess_type(obj.name)
    return FileResponse(
        path=str(p),
        media_type=media_type or "application/octet-stream",
        filename=obj.name,
    )


__all__ = ["router"]
