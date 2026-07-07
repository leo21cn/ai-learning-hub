"""PPT/PPTX → PDF 转换服务：调用本地 LibreOffice headless 模式。

约定:
- 调用方传入源文件路径与输出目录;LibreOffice 会自动将同名 PDF 写入输出目录
- 失败/超时仅记录日志,绝不抛异常(避免阻塞素材上传)
- 默认调用 `/usr/bin/libreoffice`;在 Windows 本地开发时可通过 `LIBREOFFICE_PATH` 环境变量指向安装路径
"""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Optional

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def convert(src: Path, out_dir: Path, *, timeout: Optional[int] = None) -> Optional[Path]:
    """将 PPT/PPTX 转换为 PDF。返回 PDF 绝对路径;失败/超时返回 None。

    Args:
        src: 源 PPT/PPTX 文件绝对路径(必须存在)。
        out_dir: 输出目录(不存在会自动创建)。
        timeout: 单次转换超时(秒),默认从 Settings 取 `ppt_convert_timeout`。

    Returns:
        生成的 PDF 绝对路径;失败/超时返回 None。
    """
    s = get_settings()
    so_path = s.libreoffice_path
    so_timeout = timeout if timeout is not None else s.ppt_convert_timeout

    src = Path(src)
    out_dir = Path(out_dir)
    if not src.exists():
        logger.warning("ppt_to_pdf: source file not found: %s", src)
        return None

    out_dir.mkdir(parents=True, exist_ok=True)

    expected_pdf = out_dir / (src.stem + ".pdf")
    # 清理旧文件防止 LibreOffice 复用
    if expected_pdf.exists():
        try:
            expected_pdf.unlink()
        except OSError:
            pass

    cmd = [
        so_path,
        "--headless",
        "--convert-to",
        "pdf",
        "--outdir",
        str(out_dir),
        str(src),
    ]
    try:
        proc = subprocess.run(
            cmd,
            timeout=so_timeout,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        logger.warning("ppt_to_pdf: libreoffice binary not found at %s", so_path)
        return None
    except subprocess.TimeoutExpired:
        logger.warning("ppt_to_pdf: timeout (%ss) converting %s", so_timeout, src)
        return None
    except Exception as e:  # noqa: BLE001
        logger.warning("ppt_to_pdf: unexpected error converting %s: %s", src, e)
        return None

    if proc.returncode != 0:
        logger.warning(
            "ppt_to_pdf: libreoffice exit %s for %s; stdout=%s stderr=%s",
            proc.returncode,
            src,
            proc.stdout[:300] if proc.stdout else "",
            proc.stderr[:300] if proc.stderr else "",
        )
        return None

    if not expected_pdf.exists():
        logger.warning("ppt_to_pdf: expected PDF not produced at %s", expected_pdf)
        return None
    return expected_pdf


__all__ = ["convert"]