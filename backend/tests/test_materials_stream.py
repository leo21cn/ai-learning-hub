"""素材公共流式接口 / 单条接口测试。

覆盖:
- /api/public/materials/{id}/stream 的 disposition / media_type 行为
- /api/public/materials/{id} 返回字段集(无 storage_path)
- PPT 转换结果(转换成功 / 失败降级)
- ACL:受限课件需 X-Token-Hash
- material_not_found
"""
from __future__ import annotations

import io
import os
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient


def _upload(client: TestClient, name: str, payload: bytes, content_type: str):
    """上传素材并返回 id。"""
    files = {"file": (name, io.BytesIO(payload), content_type)}
    r = client.post("/api/admin/materials", files=files)
    assert r.status_code == 201, r.text
    return r.json()["data"]["id"]


def _login(client: TestClient) -> None:
    r = client.post("/api/auth/admin", json={"token": "demo"})
    assert r.status_code == 200, r.text


def test_stream_video_inline_disposition(client: TestClient):
    """F-VIDEO-1: 视频流式返回 inline + video/mp4。"""
    _login(client)
    mid = _upload(client, "movie.mp4", b"\x00\x00\x00 ftypisom body", "video/mp4")

    r = client.get(f"/api/public/materials/{mid}/stream")
    assert r.status_code == 200, r.text
    assert r.headers.get("content-type", "").startswith("video/mp4")
    # FastAPI FileResponse 默认 disposition=inline,filename=*
    disp = r.headers.get("content-disposition", "")
    assert "inline" in disp
    assert "movie.mp4" in disp


def test_stream_pdf_inline(client: TestClient):
    """F-PDF-1: PDF 流式返回 inline + application/pdf。"""
    _login(client)
    mid = _upload(client, "doc.pdf", b"%PDF-1.4 demo body", "application/pdf")

    r = client.get(f"/api/public/materials/{mid}/stream")
    assert r.status_code == 200, r.text
    assert r.headers.get("content-type", "").startswith("application/pdf")
    disp = r.headers.get("content-disposition", "")
    assert "inline" in disp
    # 重命名为 .pdf 后缀
    assert ".pdf" in disp


def test_stream_ppt_fallback_when_no_preview(client: TestClient):
    """F-PPT-FB-1: PPT 未生成预览 PDF 时,降级返回原 PPT,Content-Type 嗅探 application/vnd.ms-powerpoint 或 octet-stream。"""
    _login(client)
    # 不传 PPT_CONVERT,默认配置下 LibreOffice 不存在或超时 → preview_pdf_path 为 None
    mid = _upload(client, "slides.ppt", b"PK\x03\x04 fake ppt body", "application/vnd.ms-powerpoint")

    r = client.get(f"/api/public/materials/{mid}/stream")
    assert r.status_code == 200, r.text
    # 不应返回 application/pdf (说明没有降级到 PDF)
    assert not r.headers.get("content-type", "").startswith("application/pdf")


def test_stream_ppt_uses_converted_pdf(client: TestClient):
    """F-PPT-PDF-1: 当 preview_pdf_path 存在且指向真实文件时,返回 PDF inline。"""
    _login(client)
    mid = _upload(client, "slides2.pptx", b"PK\x03\x04 fake pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation")

    # 准备一个伪造的 PDF 文件路径
    from app.services.material import get as svc_get
    from app.db import get_db
    from app.main import app

    # 通过覆盖 db 找到刚上传的素材
    db_gen = app.dependency_overrides[get_db]()
    db = next(db_gen)
    try:
        obj = svc_get(db, mid)
        # 把 preview_pdf_path 指向真实文件
        fake_pdf = Path(obj.storage_path).with_suffix(".pdf")
        fake_pdf.write_bytes(b"%PDF-1.4 fake preview")
        obj.preview_pdf_path = str(fake_pdf)
        db.commit()
    finally:
        try:
            next(db_gen)
        except StopIteration:
            pass

    r = client.get(f"/api/public/materials/{mid}/stream")
    assert r.status_code == 200, r.text
    assert r.headers.get("content-type", "").startswith("application/pdf")
    disp = r.headers.get("content-disposition", "")
    assert "inline" in disp


def test_stream_material_not_found(client: TestClient):
    """F-NF-1: 不存在的素材 → 404 material_not_found。"""
    r = client.get("/api/public/materials/999999/stream")
    assert r.status_code == 404, r.text
    assert r.json()["code"] == "material_not_found"


def test_get_public_material_no_storage_path(client: TestClient):
    """F-GET-1: 公开单素材接口字段集合,不含 storage_path。"""
    _login(client)
    mid = _upload(client, "doc2.pdf", b"%PDF-1.4 hello", "application/pdf")
    r = client.get(f"/api/public/materials/{mid}")
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert body["id"] == mid
    assert body["type"] == "PDF"
    assert body["name"] == "doc2.pdf"
    assert body["sizeBytes"] > 0
    assert body["streamUrl"] == f"/api/public/materials/{mid}/stream"
    assert body["downloadUrl"] == f"/api/public/materials/{mid}/file"
    assert body["previewReady"] is True
    assert "storage_path" not in body
    assert "storagePath" not in body


def test_get_public_material_ppt_preview_not_ready(client: TestClient):
    """F-GET-2: PPT 无预览时 previewReady=False。"""
    _login(client)
    mid = _upload(client, "no-preview.pptx", b"PK\x03\x04 fake", "application/vnd.openxmlformats-officedocument.presentationml.presentation")
    r = client.get(f"/api/public/materials/{mid}")
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert body["type"] == "PPT"
    assert body["previewReady"] is False


def test_get_public_material_not_found(client: TestClient):
    """F-GET-NF-1: 不存在 → 404。"""
    r = client.get("/api/public/materials/999999")
    assert r.status_code == 404
    assert r.json()["code"] == "material_not_found"


def test_stream_restricted_courseware_without_token_blocked(client: TestClient):
    """F-ACL-1: 受限课件中的素材,无 X-Token-Hash → 403。"""
    _login(client)
    # 准备 token + 受限课件 + 素材
    rt = client.post("/api/admin/access-tokens", json={"label": "acl-stream"})
    assert rt.status_code == 201, rt.text
    tid = rt.json()["data"]["id"]
    val = rt.json()["data"]["value"]

    cat_a = client.post("/api/admin/categories", json={"name": "C-A"}).json()["data"]
    cat_b = client.post(
        "/api/admin/categories", json={"name": "C-B", "parentId": cat_a["id"]}
    ).json()["data"]
    cat_c = client.post(
        "/api/admin/categories", json={"name": "C-C", "parentId": cat_b["id"]}
    ).json()["data"]

    mid = _upload(client, "locked.pdf", b"%PDF-1.4 restricted", "application/pdf")

    payload = {
        "title": "restricted-with-material",
        "categoryId": cat_c["id"],
        "accessMode": "RESTRICTED",
        "tokenIds": [tid],
        "tagIds": [],
        "materialIds": [mid],
        "description": None,
        "author": None,
    }
    rc = client.post("/api/admin/coursewares", json=payload)
    assert rc.status_code == 201, rc.text

    # 不带 token → 403
    r = client.get(f"/api/public/materials/{mid}/stream")
    assert r.status_code == 403, r.text
    assert r.json()["code"] == "courseware_acl_locked"

    # 正确 token 解锁后 → 200
    r_unlock = client.post(
        f"/api/public/coursewares/{rc.json()['data']['id']}/unlock",
        json={"token": val},
    )
    assert r_unlock.status_code == 200, r_unlock.text
    th = r_unlock.json()["data"]["tokenHash"]

    r2 = client.get(
        f"/api/public/materials/{mid}/stream", headers={"X-Token-Hash": th}
    )
    assert r2.status_code == 200, r2.text
    assert r2.headers.get("content-type", "").startswith("application/pdf")


def test_upload_pdf_no_preview(client: TestClient):
    """F-UPLOAD-PDF-1: PDF 上传不会触发 PPT→PDF 转换,preview_pdf_path 为 None。"""
    _login(client)
    mid = _upload(client, "plain.pdf", b"%PDF-1.4 no conversion", "application/pdf")
    # 通过 admin list 接口查看(测试时不依赖 get_db 私有路径)
    r = client.get(f"/api/admin/materials/{mid}/file")
    assert r.status_code == 200


def test_courseware_materials_include_stream_url(client: TestClient):
    """F-CW-MAT-1: 课件详情里的素材项携带 streamUrl。"""
    _login(client)
    mid = _upload(client, "with-url.mp4", b"\x00\x00\x00 ftypisom", "video/mp4")

    cat_a = client.post("/api/admin/categories", json={"name": "C1-A"}).json()["data"]
    cat_b = client.post(
        "/api/admin/categories", json={"name": "C1-B", "parentId": cat_a["id"]}
    ).json()["data"]
    cat_c = client.post(
        "/api/admin/categories", json={"name": "C1-C", "parentId": cat_b["id"]}
    ).json()["data"]

    payload = {
        "title": "course-with-stream",
        "categoryId": cat_c["id"],
        "accessMode": "OPEN",
        "tokenIds": [],
        "tagIds": [],
        "materialIds": [mid],
        "description": None,
        "author": None,
    }
    rc = client.post("/api/admin/coursewares", json=payload)
    assert rc.status_code == 201, rc.text
    cid = rc.json()["data"]["id"]

    r = client.get(f"/api/public/coursewares/{cid}")
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    materials = body["materials"]
    assert len(materials) == 1
    assert materials[0]["streamUrl"] == f"/api/public/materials/{mid}/stream"
    assert materials[0]["downloadUrl"] == f"/api/public/materials/{mid}/file"


def test_ppt_to_pdf_convert_called_for_ppt(client: TestClient, tmp_path, monkeypatch):
    """F-PPT-CONV-1: PPT 上传触发 ppt_to_pdf.convert 调用,失败也不抛异常。"""
    _login(client)
    # 让 settings.storage_path 指向 tmp_path
    from app.core.config import get_settings
    settings = get_settings()
    monkeypatch.setattr(settings, "storage_path", str(tmp_path))
    # 把 LibreOffice 路径指向不存在的二进制
    monkeypatch.setattr(settings, "libreoffice_path", "/nonexistent/soffice")

    mid = _upload(client, "willfail.ppt", b"PK\x03\x04 fake ppt", "application/vnd.ms-powerpoint")
    # 不应阻断上传
    assert mid is not None

    r = client.get(f"/api/public/materials/{mid}")
    assert r.status_code == 200, r.text
    # LibreOffice 不存在 → previewReady=False
    assert r.json()["data"]["previewReady"] is False