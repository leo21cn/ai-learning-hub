"""分类管理 happy path + 业务规则测试。"""
from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import login_admin


def _new_root(client: TestClient, name: str) -> dict:
    r = client.post("/api/admin/categories", json={"name": name})
    assert r.status_code == 201, r.text
    return r.json()["data"]


def _new_child(client: TestClient, name: str, parent_id: int) -> dict:
    r = client.post("/api/admin/categories", json={"name": name, "parentId": parent_id})
    assert r.status_code == 201, r.text
    return r.json()["data"]


def test_category_tree_3_levels(client: TestClient):
    login_admin(client)
    a = _new_root(client, "项目运营")
    b = _new_child(client, "通用", a["id"])
    c = _new_child(client, "入门", b["id"])
    assert a["level"] == 1 and b["level"] == 2 and c["level"] == 3

    r = client.get("/api/admin/categories")
    assert r.status_code == 200
    tree = r.json()["data"]
    assert len(tree) == 1
    assert tree[0]["children"][0]["children"][0]["name"] == "入门"


def test_category_name_required(client: TestClient):
    login_admin(client)
    r = client.post("/api/admin/categories", json={"name": "  "})
    assert r.status_code == 400
    assert r.json()["code"] == "category_name_required"


def test_category_name_conflict_siblings(client: TestClient):
    login_admin(client)
    _new_root(client, "项目运营")
    r = client.post("/api/admin/categories", json={"name": "项目运营"})
    assert r.status_code == 409
    assert r.json()["code"] == "category_name_conflict"


def test_category_max_level(client: TestClient):
    login_admin(client)
    a = _new_root(client, "L1")
    b = _new_child(client, "L2", a["id"])
    c = _new_child(client, "L3", b["id"])
    # 试图在 L3 下加第 4 级
    r = client.post("/api/admin/categories", json={"name": "L4", "parentId": c["id"]})
    assert r.status_code == 409
    assert r.json()["code"] == "category_max_level"


def test_category_rename(client: TestClient):
    login_admin(client)
    a = _new_root(client, "改名")
    r = client.put(f"/api/admin/categories/{a['id']}", json={"name": "新名"})
    assert r.status_code == 200
    assert r.json()["data"]["name"] == "新名"


def test_category_delete_with_child_blocked(client: TestClient):
    login_admin(client)
    a = _new_root(client, "A")
    _new_child(client, "B", a["id"])
    r = client.delete(f"/api/admin/categories/{a['id']}")
    assert r.status_code == 422
    assert r.json()["code"] == "category_has_children"


def test_category_delete_leaf_ok(client: TestClient):
    login_admin(client)
    a = _new_root(client, "X")
    r = client.delete(f"/api/admin/categories/{a['id']}")
    assert r.status_code == 200
