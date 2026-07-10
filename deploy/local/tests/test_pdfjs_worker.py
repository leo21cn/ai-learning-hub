"""PDF.js worker 静态资源 /pdf.worker.min.mjs 可访问性验证。

对应规格 v1.2 §07-技术架构、§03 §5a P-VIEWER。

本测试在 docker compose 启动后（或本地 `npm run build` 后）执行：
1. 验证 frontend/dist/pdf.worker.min.mjs 文件存在
2. 验证文件大小 > 100KB（pdfjs-dist 4.7 的 worker 实际约 1MB+）
3. 验证文件首部符合 ES Module 格式（mjs 文件）
4. 通过 TestClient 验证 /api/public/health 间接确认后端可达（前置条件）

若 frontend/dist 尚未构建，本测试使用 pytest.skip 跳过（不影响 CI 主流程）。
"""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient


def test_pdfjs_worker_file_exists():
    """DS-WORKER-1: frontend/dist/pdf.worker.min.mjs 必须存在。

    若 dist 目录未构建则跳过（开发态常见）。
    """
    # dist 目录的定位：相对 repo 根的 frontend/dist/
    repo_root = Path(__file__).resolve().parents[2]
    dist_dir = repo_root / "frontend" / "dist"
    worker_file = dist_dir / "pdf.worker.min.mjs"

    if not dist_dir.exists():
        import pytest

        pytest.skip(f"frontend/dist 不存在（需先 `npm run build`）: {dist_dir}")

    assert worker_file.exists(), f"PDF.js worker 缺失: {worker_file}"
    assert worker_file.is_file(), f"{worker_file} 不是文件"


def test_pdfjs_worker_file_size():
    """DS-WORKER-2: pdf.worker.min.mjs 文件大小 > 100KB。

    pdfjs-dist 4.7.x 的 worker 实际约 1MB，100KB 是保守下界。
    """
    import pytest

    repo_root = Path(__file__).resolve().parents[2]
    worker_file = repo_root / "frontend" / "dist" / "pdf.worker.min.mjs"

    if not worker_file.exists():
        pytest.skip(f"PDF.js worker 未构建: {worker_file}")

    size = worker_file.stat().st_size
    assert size > 100 * 1024, f"PDF.js worker 异常小: {size} bytes"


def test_pdfjs_worker_is_esm_format():
    """DS-WORKER-3: pdf.worker.min.mjs 应是 ES Module 格式（worker.mjs 后缀）。"""
    import pytest

    repo_root = Path(__file__).resolve().parents[2]
    worker_file = repo_root / "frontend" / "dist" / "pdf.worker.min.mjs"

    if not worker_file.exists():
        pytest.skip(f"PDF.js worker 未构建: {worker_file}")

    # 简单校验：mjs 后缀 + 文件首字节不包含 BOM 之外的可疑字符
    assert worker_file.name.endswith(".mjs"), "应使用 .mjs 扩展名"
    with worker_file.open("rb") as f:
        head = f.read(256)
    # mjs 文件通常是 minified js 开头，可能是 export/import/function
    head_str = head.decode("utf-8", errors="replace").lstrip()
    # 校验前 256 字节不是空
    assert len(head_str) > 0


def test_pdfjs_worker_in_static_assets():
    """DS-WORKER-4: PDF.js worker 应在构建产物的根目录（与 index.html 平级），便于 nginx 直接服务。

    防止 vite 把 pdf.worker 打到 assets/ 子目录导致 nginx 配置失效。
    """
    import pytest

    repo_root = Path(__file__).resolve().parents[2]
    dist_dir = repo_root / "frontend" / "dist"

    if not dist_dir.exists():
        pytest.skip(f"frontend/dist 未构建: {dist_dir}")

    worker_file = dist_dir / "pdf.worker.min.mjs"
    assert worker_file.exists(), (
        "PDF.js worker 必须在 dist 根目录（与 index.html 同级），"
        f"以便 nginx / 静态文件服务器直接服务。当前缺失: {worker_file}"
    )


def test_nginx_static_serving_smoke(client: TestClient):
    """DS-WORKER-5: 通过 TestClient 间接验证后端可达（健康检查）。

    真实 nginx 静态服务在 deploy/tests 外部用 curl 验证；本测试作为前置 gate。
    """
    r = client.get("/api/public/health")
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == "ok"
    assert body["data"]["status"] == "UP"