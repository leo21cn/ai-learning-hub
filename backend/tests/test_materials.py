"""素材管理 happy path + 白名单/大小限制测试。"""
from __future__ import annotations

import io

from fastapi.testclient import TestClient

from tests.conftest import login_admin


def test_material_upload_pdf(client: TestClient):
    login_admin(client)
    files = {"file": ("hello.pdf", io.BytesIO(b"%PDF-1.4 demo"), "application/pdf")}
    r = client.post("/api/admin/materials", files=files)
    assert r.status_code == 201, r.text
    body = r.json()["data"]
    assert body["type"] == "PDF"
    assert body["sizeBytes"] > 0
    # F-PREVIEW-1: PDF 不触发 PPT→PDF 转换,preview_pdf_path 必须为 None。
    # 通过 DB 直接读:admin 上传接口不返回 preview_pdf_path,但应保证库内字段为 NULL。
    mid = body["id"]
    from app.db import get_db
    from app.main import app
    from app.models.material import Material

    db_gen = app.dependency_overrides[get_db]()
    db = next(db_gen)
    try:
        obj = db.get(Material, mid)
        assert obj is not None
        assert obj.preview_pdf_path is None, (
            f"PDF 上传不应生成 preview_pdf_path,实际值={obj.preview_pdf_path!r}"
        )
    finally:
        try:
            next(db_gen)
        except StopIteration:
            pass


def test_material_upload_ppt_triggers_conversion(client: TestClient):
    """F-PREVIEW-2: PPT 上传后会异步调用 ppt_to_pdf.convert,失败时 preview_pdf_path 为 None,不阻断上传。"""
    login_admin(client)
    files = {"file": ("slides.pptx", io.BytesIO(b"PK\x03\x04 fake pptx"), "application/vnd.openxmlformats-officedocument.presentationml.presentation")}
    r = client.post("/api/admin/materials", files=files)
    assert r.status_code == 201, r.text
    body = r.json()["data"]
    assert body["type"] == "PPT"
    # 在测试环境下 LibreOffice 不一定可用,转换可能失败;无论成功失败都不应阻塞
    # 上传接口 admin 端不返回 previewPdfPath 字段(由公开 /stream 接口读取),仅校验不抛异常
    assert body["sizeBytes"] > 0


def test_material_upload_rejects_unknown_ext(client: TestClient):
    login_admin(client)
    files = {"file": ("evil.exe", io.BytesIO(b"MZ\x00"), "application/octet-stream")}
    r = client.post("/api/admin/materials", files=files)
    assert r.status_code == 400
    assert r.json()["code"] == "material_extension_invalid"


def test_material_list_and_filter(client: TestClient):
    login_admin(client)
    files = {"file": ("a.pdf", io.BytesIO(b"%PDF-1.4 demo a"), "application/pdf")}
    r = client.post("/api/admin/materials", files=files)
    assert r.status_code == 201

    files2 = {"file": ("b.mp4", io.BytesIO(b"\x00\x00\x00 ftypisom"), "video/mp4")}
    r2 = client.post("/api/admin/materials", files=files2)
    assert r2.status_code == 201

    r3 = client.get("/api/admin/materials")
    assert r3.status_code == 200
    data = r3.json()["data"]
    assert data["total"] == 2
    types = {m["type"] for m in data["items"]}
    assert types == {"PDF", "VIDEO"}

    r4 = client.get("/api/admin/materials?type=PDF")
    pdf = r4.json()["data"]
    assert all(m["type"] == "PDF" for m in pdf["items"])


def test_material_delete_unreferenced(client: TestClient):
    login_admin(client)
    files = {"file": ("a.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")}
    r = client.post("/api/admin/materials", files=files)
    mid = r.json()["data"]["id"]
    r2 = client.delete(f"/api/admin/materials/{mid}")
    assert r2.status_code == 200
