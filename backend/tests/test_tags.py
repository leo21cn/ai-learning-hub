"""标签管理 happy path 测试。"""
from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import login_admin


def test_tag_create_list_rename_delete(client: TestClient):
    login_admin(client)

    # create
    r = client.post("/api/admin/tags", json={"name": "项目管理"})
    assert r.status_code == 201, r.text
    tid = r.json()["data"]["id"]

    # conflict
    r2 = client.post("/api/admin/tags", json={"name": "项目管理"})
    assert r2.status_code == 409
    assert r2.json()["code"] == "tag_name_conflict"

    # list
    r3 = client.get("/api/admin/tags")
    assert r3.status_code == 200
    body = r3.json()["data"]
    assert body["total"] == 1
    assert body["items"][0]["name"] == "项目管理"
    assert body["items"][0]["coursewareCount"] == 0

    # rename
    r4 = client.put(f"/api/admin/tags/{tid}", json={"name": "PM"})
    assert r4.status_code == 200
    assert r4.json()["data"]["name"] == "PM"

    # delete
    r5 = client.delete(f"/api/admin/tags/{tid}")
    assert r5.status_code == 200

    r6 = client.get("/api/admin/tags")
    assert r6.json()["data"]["total"] == 0


def test_tag_name_required(client: TestClient):
    login_admin(client)
    # 空字符串:Pydantic min_length 校验先拦下,返回 422
    r = client.post("/api/admin/tags", json={"name": ""})
    assert r.status_code == 422
    # 纯空白:service 内部 trim 后报业务码
    r2 = client.post("/api/admin/tags", json={"name": "   "})
    assert r2.status_code == 400
    assert r2.json()["code"] == "tag_name_required"
