"""AccessToken 服务单元 + 接口测试。"""
from __future__ import annotations

from app.core.errors import ErrorCode


def test_token_create_returns_value_then_hashed(client, admin_login):
    r1 = client.post("/api/admin/access-tokens", json={"label": "team-x"})
    assert r1.status_code == 201
    body = r1.json()
    assert body["code"] == "ok"
    payload = body["data"]
    # 一次性返回值格式
    assert "value" in payload
    assert "valueHash" in payload
    assert payload["label"] == "team-x"
    assert len(payload["value"]) >= 20

    # 列表中不再返回明文 value
    r2 = client.get("/api/admin/access-tokens")
    assert r2.status_code == 200
    items = r2.json()["data"]["items"]
    matched = [t for t in items if t["label"] == "team-x"]
    assert matched, "新创建的 token 应在列表里"
    assert "value" not in matched[0]
    assert matched[0]["valueHash"] == payload["valueHash"]


def test_token_label_required(client, admin_login):
    # 空字符串 → Pydantic min_length 422
    r = client.post("/api/admin/access-tokens", json={"label": ""})
    assert r.status_code == 422
    # 纯空白 → 业务校验 400
    r2 = client.post("/api/admin/access-tokens", json={"label": "   "})
    assert r2.status_code == 400
    assert r2.json()["code"] == "token_label_required"


def test_token_label_conflict(client, admin_login):
    """重复 label 应返回业务错误码 token_label_conflict(状态码可为 400 或 409)。"""
    client.post("/api/admin/access-tokens", json={"label": "dup"})
    r = client.post("/api/admin/access-tokens", json={"label": "dup"})
    assert r.status_code in (400, 409)
    assert r.json()["code"] == "token_label_conflict"


def test_token_label_too_long(client, admin_login):
    r = client.post("/api/admin/access-tokens", json={"label": "x" * 100})
    assert r.status_code == 422


def test_token_regenerate_changes_hash_and_keeps_label(client, admin_login):
    r = client.post("/api/admin/access-tokens", json={"label": "regen"})
    h1 = r.json()["data"]["valueHash"]
    tid = int(r.json()["data"]["id"])
    r2 = client.post(f"/api/admin/access-tokens/{tid}/regenerate")
    assert r2.status_code == 200
    payload = r2.json()["data"]
    assert payload["valueHash"] != h1
    assert payload["label"] == "regen"


def test_token_last_required(client, admin_login):
    # 先创建唯一一个 token
    r = client.post("/api/admin/access-tokens", json={"label": "only"})
    tid = int(r.json()["data"]["id"])
    rd = client.delete(f"/api/admin/access-tokens/{tid}")
    # 错误码 last_token_required 映射到 422
    assert rd.status_code == 422
    body = rd.json()
    assert body["code"] in (ErrorCode.LAST_TOKEN_REQUIRED, "last_token_required")


def test_token_delete_when_unreferenced_ok(client, admin_login):
    # 创建两个 token,然后删其中一个,不应被 block
    r1 = client.post("/api/admin/access-tokens", json={"label": "A"})
    r2 = client.post("/api/admin/access-tokens", json={"label": "B"})
    assert r1.status_code == 201
    assert r2.status_code == 201
    tid = int(r1.json()["data"]["id"])
    rd = client.delete(f"/api/admin/access-tokens/{tid}")
    assert rd.status_code == 200


def test_token_delete_when_referenced_blocked(client, courseware_payload, admin_login):
    """当课件引用了 token,删除应被 block(token_referenced)。"""
    # 创建 2 个 token
    r1 = client.post("/api/admin/access-tokens", json={"label": "refA"})
    r2 = client.post("/api/admin/access-tokens", json={"label": "refB"})
    t1 = int(r1.json()["data"]["id"])
    t2 = int(r2.json()["data"]["id"])
    # 建一棵 3 级分类
    a = client.post("/api/admin/categories", json={"name": "T-A"}).json()["data"]
    b = client.post(
        "/api/admin/categories", json={"name": "T-B", "parentId": a["id"]}
    ).json()["data"]
    leaf = client.post(
        "/api/admin/categories", json={"name": "T-C", "parentId": b["id"]}
    ).json()["data"]["id"]
    # 用 refA 创建一个受限课件
    payload = courseware_payload(token_ids=[t1], access_mode="RESTRICTED", category_id=leaf)
    rc = client.post("/api/admin/coursewares", json=payload)
    assert rc.status_code == 201, rc.text
    # 试图删除被引用的 token
    rd = client.delete(f"/api/admin/access-tokens/{t1}")
    # 错误码 token_referenced 映射到 422
    assert rd.status_code == 422
    assert rd.json()["code"] in ("token_referenced", ErrorCode.TOKEN_REFERENCED)
    # 删除未被引用的 token
    rd2 = client.delete(f"/api/admin/access-tokens/{t2}")
    assert rd2.status_code == 200