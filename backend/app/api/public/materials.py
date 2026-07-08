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


@router.get("/{material_id}/image/{page_no}")
@limiter.limit("60/minute")
def public_get_image(
    request: Request,
    material_id: int,
    page_no: int,
    db: Session = Depends(get_db),  # type: ignore[no-untyped-def]
):
    """公开 PPT 预览图片接口:返回第 N 张 PNG (1-indexed)。

    - 仅 PPT 类型且 preview_images_dir 非空时可用
    - page_no 越界返回 404
    - 与 /stream 共享同一个 _check_acl 限制
    """
    obj: Material = svc.get(db, material_id)
    _check_acl(request, material_id, db)
    if obj.type != MaterialType.PPT.value or not obj.preview_images_dir:
        raise BusinessError(ErrorCode.MATERIAL_NOT_FOUND, "该素材无可用预览")
    # 不依赖 pdftoppm 输出文件名约定(page-1.png / page-01.png 都要兼容),
    # 按文件名 page-NN.png 中的数字 glob 排序后按 1-indexed 取第 page_no 张。
    pages = sorted(
        Path(obj.preview_images_dir).glob("page-*.png"),
        key=lambda p: int(p.stem.split("-")[1]),
    )
    if page_no < 1 or page_no > len(pages):
        raise BusinessError(ErrorCode.MATERIAL_NOT_FOUND, "页码不存在")
    img_path = pages[page_no - 1]
    return FileResponse(
        path=str(img_path),
        media_type="image/png",
        content_disposition_type="inline",
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
    }
    # PPT 专属:返回 imageUrls + imageCount,用于 SlideshowViewer 直接显示图片
    if obj.type == MaterialType.PPT.value and obj.preview_images_dir:
        pages = sorted(
            Path(obj.preview_images_dir).glob("page-*.png"),
            key=lambda p: int(p.stem.split("-")[1]),
        )
        payload["imageCount"] = len(pages)
        payload["imageUrls"] = [
            f"/api/public/materials/{obj.id}/image/{i + 1}" for i in range(len(pages))
        ]
        payload["previewReady"] = len(pages) > 0
    else:
        payload["imageCount"] = 0
        payload["imageUrls"] = []
        payload["previewReady"] = obj.type != MaterialType.PPT.value
    return ok(data=payload)


__all__ = ["router"]