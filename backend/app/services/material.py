"""素材(Material)业务服务：列表 + 上传 + 删除。"""
from __future__ import annotations

import json
import logging
import os
import secrets
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import BusinessError, ErrorCode
from app.models.association import courseware_material
from app.models.material import Material, MaterialType, infer_type
from app.services import ppt_to_images


MAX_SIZE_BYTES = 500 * 1024 * 1024  # 500MB（与 frontend/nginx.conf + nginx-gateway 的 client_max_body_size 对齐）
logger = logging.getLogger(__name__)


def _storage_root() -> Path:
    s = get_settings()
    root = Path(s.storage_path)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _probe_video_duration(path: Path) -> Optional[str]:
    """用 ffprobe 探测视频时长并格式化为 MM:SS / HH:MM:SS。

    - 调用 `ffprobe -v error -show_entries format=duration -of json <path>` 取秒数。
    - 失败（ffprobe 未安装 / 文件损坏 / 超时）返回 None，不阻断上传。
    - 返回字符串与 PPT 的 duration_or_pages（页数字符串）同型，方便前端统一处理。
    """
    try:
        out = subprocess.check_output(
            [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "json",
                str(path),
            ],
            stderr=subprocess.STDOUT,
            timeout=30,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.CalledProcessError) as e:
        logger.warning("ffprobe failed for %s: %s", path, e)
        return None

    try:
        data = json.loads(out.decode("utf-8", errors="ignore") or "{}")
        dur_raw = data.get("format", {}).get("duration")
        if not dur_raw:
            return None
        sec = float(dur_raw)
        if sec <= 0 or not sec or sec != sec:  # 排除 NaN/0
            return None
    except (ValueError, TypeError) as e:
        logger.warning("ffprobe parse duration failed for %s: %s", path, e)
        return None

    total = int(round(sec))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    pad = lambda n: f"{n:02d}"
    return f"{pad(h)}:{pad(m)}:{pad(s)}" if h > 0 else f"{pad(m)}:{pad(s)}"


def list_paged(
    db: Session, *, keyword: Optional[str], mtype: Optional[str], page: int, size: int
) -> dict:
    base = select(Material)
    if keyword:
        base = base.where(Material.name.ilike(f"%{keyword}%"))
    if mtype:
        base = base.where(Material.type == mtype.upper())
    total = db.execute(
        select(func.count()).select_from(base.subquery())
    ).scalar_one()
    items = (
        db.execute(base.order_by(Material.id.desc()).offset((page - 1) * size).limit(size))
        .scalars()
        .all()
    )
    # referenced 标记
    ref_subq = (
        select(courseware_material.c.material_id, func.count(courseware_material.c.courseware_id).label("c"))
        .group_by(courseware_material.c.material_id)
        .subquery()
    )
    refs = dict(db.execute(select(ref_subq.c.material_id, ref_subq.c.c)).all())

    return {
        "page": page,
        "size": size,
        "total": int(total),
        "items": [
            {
                "id": m.id,
                "name": m.name,
                "type": m.type,
                "sizeBytes": int(m.size_bytes),
                "duration": m.duration_or_pages,
                "uploadedAt": m.uploaded_at.isoformat() if m.uploaded_at else None,
                "referenced": int(refs.get(m.id, 0)) > 0,
                "downloadUrl": f"/api/admin/materials/{m.id}/file",
            }
            for m in items
        ],
    }


def get(db: Session, material_id: int) -> Material:
    obj = db.get(Material, material_id)
    if not obj:
        raise BusinessError(ErrorCode.MATERIAL_NOT_FOUND, "素材不存在")
    return obj


async def upload(db: Session, upload: UploadFile) -> Material:
    name = upload.filename or "upload.bin"
    mat_type = infer_type(name)
    # 大小检查:读全部流到磁盘;预先累计大小
    root = _storage_root()
    subdir = root / datetime.utcnow().strftime("%Y%m")
    subdir.mkdir(parents=True, exist_ok=True)
    # 唯一文件名
    safe_name = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(4)}-{os.path.basename(name)}"
    full_path = subdir / safe_name
    total = 0
    try:
        with full_path.open("wb") as f:
            while True:
                chunk = await upload.read(8 * 1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_SIZE_BYTES:
                    # 主动清理半文件
                    f.close()
                    try:
                        full_path.unlink(missing_ok=True)
                    except Exception:
                        pass
                    raise BusinessError(ErrorCode.MATERIAL_SIZE_EXCEEDED, "文件大小不能超过 200MB")
                f.write(chunk)
    except BusinessError:
        raise
    except Exception as e:
        raise BusinessError(ErrorCode.MATERIAL_UPLOAD_FAILED, "文件写入失败") from e

    obj = Material(
        name=name,
        type=mat_type.value,
        size_bytes=total,
        storage_path=str(full_path),
    )
    # VIDEO:用 ffprobe 探测时长,写入 duration_or_pages(与 PPT 页数同字段同型)
    if mat_type == MaterialType.VIDEO:
        try:
            obj.duration_or_pages = _probe_video_duration(full_path)
        except Exception as e:  # noqa: BLE001
            logger.warning("probe duration crashed for %s: %s", full_path, e)
    # PPT/PPTX 后台拆成多张 PNG,用于在线浏览
    if mat_type == MaterialType.PPT:
        try:
            result = ppt_to_images.convert(full_path)
            if result is not None:
                images_dir, page_count = result
                obj.preview_images_dir = str(images_dir)
                # 顺便记录 PPT 页数,前端不必再读 PDF
                obj.duration_or_pages = str(page_count)
        except Exception as e:  # noqa: BLE001
            # 转换服务必须不能阻断上传
            logger.warning(
                "ppt_to_images crashed unexpectedly for %s: %s", full_path, e
            )
    db.add(obj)
    try:
        db.commit()
    except Exception as e:
        # 入库失败,清理文件
        try:
            full_path.unlink(missing_ok=True)
            if obj.preview_images_dir:
                import shutil as _shutil

                _shutil.rmtree(obj.preview_images_dir, ignore_errors=True)
        except Exception:
            pass
        raise BusinessError(ErrorCode.MATERIAL_UPLOAD_FAILED, "文件写入失败") from e
    db.refresh(obj)
    return obj


def delete(db: Session, material_id: int) -> None:
    obj = get(db, material_id)
    # 是否被引用?
    ref = db.execute(
        select(func.count(courseware_material.c.courseware_id)).where(
            courseware_material.c.material_id == material_id
        )
    ).scalar_one()
    if ref:
        raise BusinessError(ErrorCode.MATERIAL_REFERENCED, "素材已被课件引用，无法删除")
    path = Path(obj.storage_path)
    preview_dir = Path(obj.preview_images_dir) if obj.preview_images_dir else None
    db.delete(obj)
    db.commit()
    # 物理删除
    try:
        if path.exists():
            path.unlink()
    except OSError:
        pass
    if preview_dir is not None:
        try:
            if preview_dir.exists():
                shutil.rmtree(preview_dir, ignore_errors=True)
        except OSError:
            pass


__all__ = ["MAX_SIZE_BYTES", "list_paged", "get", "upload", "delete"]
