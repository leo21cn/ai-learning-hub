"""PPT/PPTX → 多张 PNG 转换服务。

约定:
- 调用方传入源 PPT 文件路径,服务内部:
  1. 调用 `libreoffice --headless --convert-to pdf` 转为 PDF
  2. 调用 `pdftoppm -r 150 -png` 把 PDF 每页拆成 PNG
  3. 把 PNG 整理到 `{storage}/{ppt_stem}/` 目录下,命名为 `page-1.png` `page-2.png` ...
- 失败/超时仅记录 logger,绝不抛异常(避免阻塞素材上传)
- 默认调用 `/usr/bin/libreoffice` 与 `/usr/bin/pdftoppm`;
  Windows 本地开发可通过 `LIBREOFFICE_PATH` / `POPPLER_PATH` 环境变量指向安装路径
- 返回值:`Optional[tuple[Path, int]]` = (图片目录绝对路径, 页数);失败/超时返回 None
"""
from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def _resolve_bin(name: str, env_name: str, default_path: str) -> Optional[str]:
    """优先使用 settings 的可执行路径(可由 env 覆盖);其次 PATH。"""
    # 1) settings 已提供绝对路径
    s = get_settings()
    if env_name == "libreoffice_path":
        cfg_path = getattr(s, "libreoffice_path", None)
    elif env_name == "poppler_path":
        cfg_path = getattr(s, "poppler_path", None)
    else:
        cfg_path = None
    if cfg_path and Path(cfg_path).exists():
        return cfg_path
    # 2) PATH 查找
    found = shutil.which(name)
    if found:
        return found
    # 3) 默认路径兜底
    if Path(default_path).exists():
        return default_path
    return None


def convert(src: Path, *, timeout: Optional[int] = None) -> Optional[tuple[Path, int]]:
    """将 PPT/PPTX 转换为多张 PNG。

    Args:
        src: 源 PPT/PPTX 文件绝对路径(必须存在)。
        timeout: 单次 LibreOffice 调用超时(秒),默认从 Settings 取 `ppt_convert_timeout`。
                 pdftoppm 阶段使用相同上限。

    Returns:
        (图片目录绝对路径, 页数) 元组; 失败/超时返回 None。
        生成的文件命名固定为 `page-1.png`, `page-2.png`, ...;
        目录内还会有一个中间产物 `slides.pdf`, 可保留作 fallback。
    """
    s = get_settings()
    so_timeout = timeout if timeout is not None else s.ppt_convert_timeout

    src = Path(src)
    if not src.exists():
        logger.warning("ppt_to_images: source file not found: %s", src)
        return None

    so_path = _resolve_bin("libreoffice", "libreoffice_path", "/usr/bin/libreoffice")
    if so_path is None:
        logger.warning("ppt_to_images: libreoffice binary not found")
        return None
    pdftoppm_path = _resolve_bin("pdftoppm", "poppler_path", "/usr/bin/pdftoppm")
    if pdftoppm_path is None:
        logger.warning("ppt_to_images: pdftoppm binary not found (poppler-utils not installed?)")
        return None

    # 输出目录: 与源文件同级,名字为 <stem>
    out_dir = src.parent / src.stem
    out_dir.mkdir(parents=True, exist_ok=True)
    # 清空旧产物
    for p in out_dir.iterdir():
        try:
            if p.is_file():
                p.unlink()
        except OSError:
            pass

    # LibreOffice 输出的 PDF 文件名固定为 <src.stem>.pdf(同源文件 stem,中文也保留)
    pdf_path = out_dir / f"{src.stem}.pdf"

    # Step 1: PPT -> PDF
    so_cmd = [
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
            so_cmd,
            timeout=so_timeout,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        logger.warning("ppt_to_images: libreoffice binary not executable: %s", so_path)
        return None
    except subprocess.TimeoutExpired:
        logger.warning("ppt_to_images: libreoffice timeout (%ss) for %s", so_timeout, src)
        return None
    except Exception as e:  # noqa: BLE001
        logger.warning("ppt_to_images: libreoffice unexpected error for %s: %s", src, e)
        return None

    if proc.returncode != 0:
        logger.warning(
            "ppt_to_images: libreoffice exit %s for %s; stderr=%s",
            proc.returncode,
            src,
            (proc.stderr or "")[:300],
        )
        return None
    if not pdf_path.exists():
        logger.warning("ppt_to_images: PDF not produced at %s", pdf_path)
        return None

    # Step 2: PDF -> PNGs (page-1.png, page-2.png, ...)
    pp_cmd = [
        pdftoppm_path,
        "-r",
        "150",
        "-png",
        str(pdf_path),
        str(out_dir / "page"),
    ]
    try:
        proc2 = subprocess.run(
            pp_cmd,
            timeout=so_timeout,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        logger.warning("ppt_to_images: pdftoppm not executable: %s", pdftoppm_path)
        return None
    except subprocess.TimeoutExpired:
        logger.warning("ppt_to_images: pdftoppm timeout (%ss) for %s", so_timeout, src)
        return None
    except Exception as e:  # noqa: BLE001
        logger.warning("ppt_to_images: pdftoppm unexpected error for %s: %s", src, e)
        return None

    if proc2.returncode != 0:
        logger.warning(
            "ppt_to_images: pdftoppm exit %s for %s; stderr=%s",
            proc2.returncode,
            src,
            (proc2.stderr or "")[:300],
        )
        return None

    # 统计 PNG 页数
    pages = sorted(out_dir.glob("page-*.png"))
    if not pages:
        logger.warning("ppt_to_images: no PNGs produced in %s", out_dir)
        return None

    # 删除中间 PDF (保留只 PNG,前端不需要 PDF)
    try:
        pdf_path.unlink()
    except OSError:
        pass

    logger.info("ppt_to_images: %s -> %d PNG(s) in %s", src, len(pages), out_dir)
    return out_dir, len(pages)


__all__ = ["convert"]
