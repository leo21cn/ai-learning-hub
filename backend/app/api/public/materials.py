"""素材公共 API：下载、单条查询、流式预览。"""
from __future__ import annotations

import mimetypes
from pathlib import Path

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session

from app.core.errors import BusinessError, ErrorCode
from app.core.rate_limit import limiter
from app.db import get_db
from app.models.courseware import AccessMode
from app.models.material import Material, MaterialType
from app.schemas import ok
from app.services import material as svc
from app.services import courseware as courseware_svc

router = APIRouter(prefix="/api/public/materials", tags=["public/materials"])


def _resolve_unlocked_token_hash(request: Request) -> str | None:
    """读取当前请求的已解锁 token 哈希（与 coursewares.py 一致）。"""
    h = request.headers.get("X-Token-Hash")
    if h:
        return h
    return request.cookies.get("lh_token_hash")


def _check_acl(request: Request, material_id: int, db: Session) -> None:
    """若素材仅出现在 RESTRICTED 课件中，需校验 X-Token-Hash。

    - 至少有一处引用在 OPEN 课件 → 放行
    - 否则要求该 token 哈希能命中所有引用课件的至少一个 token
    """
    from app.models.association import courseware_material

    refs = (
        db.query(courseware_material.c.courseware_id)
        .filter(courseware_material.c.material_id == material_id)
        .all()
    )
    if not refs:
        return
    courseware_ids = [r[0] for r in refs]
    coursewares = courseware_svc.get_many(db, courseware_ids)
    # 任一引用课件是 OPEN → 公开可访问
    for c in coursewares:
        if c.access_mode == AccessMode.OPEN:
            return
    # 全是 RESTRICTED：要求命中至少一个 token
    provided = _resolve_unlocked_token_hash(request)
    if not provided:
        raise BusinessError(ErrorCode.COURSEWARE_ACL_LOCKED, "该素材需要令牌解锁")
    allowed_hashes: set[str] = set()
    for c in coursewares:
        for t in (c.access_tokens or []):
            allowed_hashes.add(t.value_hash)
    if provided not in allowed_hashes:
        raise BusinessError(ErrorCode.COURSEWARE_ACL_LOCKED, "令牌无效或已失效")


@router.get("/{material_id}/file")
def public_download(
    material_id: int,
    request: Request,
    db: Session = Depends(get_db),  # type: ignore[no-untyped-def]
):
    """公共下载接口：始终以 attachment disposition 返回原文件。"""
    obj = svc.get(db, material_id)
    _check_acl(request, material_id, db)
    p = Path(obj.storage_path)
    if not p.exists():
        raise BusinessError(ErrorCode.MATERIAL_STORAGE_UNAVAILABLE, "素材文件已丢失")
    media_type, _ = mimetypes.guess_type(obj.name)
    return FileResponse(
        path=str(p),
        media_type=media_type or "application/octet-stream",
        filename=obj.name,
    )


@router.get("/{material_id}/stream")
@limiter.limit("60/minute")
def public_stream(
    request: Request,
    material_id: int,
    db: Session = Depends(get_db),  # type: ignore[no-untyped-def]
):
    """公共流式预览接口：返回行内 (inline) 内容，供浏览器/Iframe/Video 直接渲染。

    - VIDEO: mp4 + video/mp4 + inline
    - PDF:   pdf + application/pdf + inline
    - PPT/PPTX:
        * 若已生成 preview_pdf_path → 返回该 PDF，inline，filename 改名 .pdf
        * 否则降级返回原 PPT，attachment（避免浏览器乱触发下载）
    """
    obj: Material = svc.get(db, material_id)
    _check_acl(request, material_id, db)

    if obj.type == MaterialType.VIDEO.value:
        p = Path(obj.storage_path)
        if not p.exists():
            raise BusinessError(ErrorCode.MATERIAL_STORAGE_UNAVAILABLE, "素材文件已丢失")
        return FileResponse(
            path=str(p),
            media_type="video/mp4",
            filename=obj.name,
            content_disposition_type="inline",
        )

    if obj.type == MaterialType.PDF.value:
        p = Path(obj.storage_path)
        if not p.exists():
            raise BusinessError(ErrorCode.MATERIAL_STORAGE_UNAVAILABLE, "素材文件已丢失")
        # 重命名文件名为 .pdf，避免部分浏览器按扩展名嗅探
        base = Path(obj.name).stem or "document"
        return FileResponse(
            path=str(p),
            media_type="application/pdf",
            filename=f"{base}.pdf",
            content_disposition_type="inline",
        )

    # PPT/PPTX：优先返回预览 PDF
    if obj.type == MaterialType.PPT.value and obj.preview_pdf_path:
        p = Path(obj.preview_pdf_path)
        if p.exists():
            base = Path(obj.name).stem or "slides"
            return FileResponse(
                path=str(p),
                media_type="application/pdf",
                filename=f"{base}.pdf",
                content_disposition_type="inline",
            )
    # 降级：返回原 PPT/PPTX，强制 attachment
    p = Path(obj.storage_path)
    if not p.exists():
        raise BusinessError(ErrorCode.MATERIAL_STORAGE_UNAVAILABLE, "素材文件已丢失")
    media_type, _ = mimetypes.guess_type(obj.name)
    return FileResponse(
        path=str(p),
        media_type=media_type or "application/octet-stream",
        filename=obj.name,
    )


@router.get("/{material_id}")
@limiter.limit("60/minute")
def public_get_material(
    request: Request,
    material_id: int,
    db: Session = Depends(get_db),  # type: ignore[no-untyped-def]
):
    """公开素材单条查询：返回 streamUrl / downloadUrl / sizeBytes / duration。

    不返回 storage_path；仅前台 P-VIEWER 加载用。
    """
    obj = svc.get(db, material_id)
    _check_acl(request, material_id, db)
    base = Path(obj.name).stem or "file"
    payload = {
        "id": obj.id,
        "name": obj.name,
        "type": obj.type,
        "sizeBytes": int(obj.size_bytes),
        "duration": obj.duration_or_pages,
        "streamUrl": f"/api/public/materials/{obj.id}/stream",
        "downloadUrl": f"/api/public/materials/{obj.id}/file",
        # 提示前端预览是否就绪（PPT 是否已转 PDF）
        "previewReady": (
            obj.type != MaterialType.PPT.value
            or bool(obj.preview_pdf_path and Path(obj.preview_pdf_path).exists())
        ),
    }
    return ok(data=payload)


__all__ = ["router"]