"""鉴权与响应信封基础测试。"""
from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_envelope(client: TestClient):
    r = client.get("/api/public/health")
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == "ok"
    assert body["data"]["status"] == "UP"


def test_admin_login_invalid_token(client: TestClient):
    r = client.post("/api/auth/admin", json={"token": "wrong"})
    assert r.status_code == 401
    assert r.json()["code"] == "invalid_admin_token"


def test_admin_login_then_logout(client: TestClient):
    r = client.post("/api/auth/admin", json={"token": "demo"})
    assert r.status_code == 200
    assert r.json()["code"] == "ok"
    assert r.cookies.get("LH_ADMIN_SESSION")

    r2 = client.post("/api/auth/logout")
    assert r2.status_code == 200


def test_admin_route_requires_auth(client: TestClient):
    r = client.get("/api/admin/categories")
    assert r.status_code == 401
    assert r.json()["code"] == "unauthenticated"
