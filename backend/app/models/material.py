"""素材(Material)表:文件元数据 + 存储路径。"""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class MaterialType(str, enum.Enum):
    """素材类型枚举;前端、数据库共用。"""

    VIDEO = "VIDEO"
    PDF = "PDF"
    PPT = "PPT"


# 扩展名 → 类型的映射
_EXT_MAP = {
    "mp4": MaterialType.VIDEO,
    "pdf": MaterialType.PDF,
    "ppt": MaterialType.PPT,
    "pptx": MaterialType.PPT,
}


def infer_type(filename: str) -> MaterialType:
    """从文件名推断素材类型;无法识别时抛业务异常。"""
    from app.core.errors import BusinessError, ErrorCode

    if "." not in filename:
        raise BusinessError(ErrorCode.MATERIAL_EXTENSION_INVALID, "不支持的文件类型")
    ext = filename.rsplit(".", 1)[1].lower()
    mat = _EXT_MAP.get(ext)
    if mat is None:
        raise BusinessError(ErrorCode.MATERIAL_EXTENSION_INVALID, "不支持的文件类型")
    return mat


class Material(Base):
    """素材文件元数据;二进制存储在文件系统的 storage_path 中。"""

    __tablename__ = "material"
    __table_args__ = ({"comment": "素材表;二进制在文件系统"},)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(16), nullable=False)  # VIDEO/PDF/PPT
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    duration_or_pages: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    storage_path: Mapped[str] = mapped_column(String(512), nullable=False)
    # PPT 上传后由 LibreOffice 转 PDF、再由 pdftoppm 拆成多张 PNG
    # 存放于该目录下: {preview_images_dir}/page-1.png, page-2.png, ...
    # 为 NULL 表示未转换或失败未重试; 前端 P-VIEWER 走降级「下载到本地」
    preview_images_dir: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    uploaded_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Material id={self.id} name={self.name!r} type={self.type}>"


__all__ = ["Material", "MaterialType", "infer_type"]
