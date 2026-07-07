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
