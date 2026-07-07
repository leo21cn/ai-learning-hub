"""Courseware + ACL 业务测试。"""
from __future__ import annotations


def _mk_cat_leaf(client) -> int:
    """建一棵 3 级分类并返回叶子节点 id。"""
    a = client.post("/api/admin/categories", json={"name": "T-A"}).json()["data"]
    b = client.post(
        "/api/admin/categories", json={"name": "T-B", "parentId": a["id"]}
    ).json()["data"]
    c = client.post(
        "/api/admin/categories", json={"name": "T-C", "parentId": b["id"]}
    ).json()["data"]
    return c["id"]


def test_courseware_create_open(client, courseware_payload):
    leaf = _mk_cat_leaf(client)
    payload = courseware_payload(category_id=leaf, access_mode="OPEN")
    r = client.post("/api/admin/coursewares", json=payload)
    assert r.status_code == 201
    body = r.json()["data"]
    assert body["title"] == payload["title"]
    assert body["accessMode"] == "OPEN"


def test_courseware_restricted_requires_token(client, courseware_payload):
    leaf = _mk_cat_leaf(client)
    # 没有 token → 应 400 + courseware_token_required
    payload = courseware_payload(token_ids=[], access_mode="RESTRICTED", category_id=leaf)
    r = client.post("/api/admin/coursewares", json=payload)
    assert r.status_code == 400
    assert r.json()["code"] == "courseware_token_required"


def test_courseware_category_must_be_leaf(client, courseware_payload):
    # 2 级节点 → 应失败(courseware_category_not_leaf)
    a = client.post("/api/admin/categories", json={"name": "Top"}).json()["data"]
    b = client.post(
        "/api/admin/categories", json={"name": "L2", "parentId": a["id"]}
    ).json()["data"]
    payload = courseware_payload(category_id=b["id"], access_mode="OPEN")
    r = client.post("/api/admin/coursewares", json=payload)
    assert r.status_code == 400
    assert r.json()["code"] == "courseware_category_not_leaf"


def test_courseware_search_endpoint(client, courseware_payload):
    leaf = _mk_cat_leaf(client)
    client.post("/api/admin/coursewares", json=courseware_payload(
        category_id=leaf, access_mode="OPEN", title="fastapi-intro"
    ))
    r = client.get("/api/public/coursewares/search?q=fastapi")
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == "ok"
    assert "source" in body["data"]
    assert body["data"]["source"] in ("keyword", "llm")


def test_courseware_search_includes_restricted(client, courseware_payload):
    """F-019a:RESTRICTED 课件也应出现在关键词搜索结果中。"""
    # 需要先有一个 token 才能建 RESTRICTED
    rt = client.post("/api/admin/access-tokens", json={"label": "src"})
    tid = rt.json()["data"]["id"]
    leaf = _mk_cat_leaf(client)
    client.post("/api/admin/coursewares", json=courseware_payload(
        category_id=leaf,
        access_mode="RESTRICTED",
        token_ids=[tid],
        title="restricted-topic",
    ))
    r = client.get("/api/public/coursewares/search?q=restricted")
    assert r.status_code == 200
    items = r.json()["data"]["items"]
    assert any(c["title"] == "restricted-topic" for c in items)


def test_courseware_open_detail_public(client, courseware_payload):
    leaf = _mk_cat_leaf(client)
    rc = client.post("/api/admin/coursewares", json=courseware_payload(
        category_id=leaf, access_mode="OPEN", title="open-detail"
    ))
    cid = rc.json()["data"]["id"]
    r = client.get(f"/api/public/coursewares/{cid}")
    assert r.status_code == 200
    assert r.json()["data"]["title"] == "open-detail"


def test_courseware_restricted_detail_without_token_blocked(
    client, courseware_payload
):
    rt = client.post("/api/admin/access-tokens", json={"label": "blk"})
    tid = int(rt.json()["data"]["id"])
    leaf = _mk_cat_leaf(client)
    rc = client.post("/api/admin/coursewares", json=courseware_payload(
        category_id=leaf,
        access_mode="RESTRICTED",
        token_ids=[tid],
        title="restricted-detail",
    ))
    cid = int(rc.json()["data"]["id"])
    r = client.get(f"/api/public/coursewares/{cid}")
    assert r.status_code == 403
    assert r.json()["code"] == "courseware_acl_locked"


def test_courseware_unlock_then_detail(client, courseware_payload):
    rt = client.post("/api/admin/access-tokens", json={"label": "uk"})
    val = rt.json()["data"]["value"]
    tid = int(rt.json()["data"]["id"])
    leaf = _mk_cat_leaf(client)
    rc = client.post("/api/admin/coursewares", json=courseware_payload(
        category_id=leaf,
        access_mode="RESTRICTED",
        token_ids=[tid],
        title="locked-then-unlock",
    ))
    cid = int(rc.json()["data"]["id"])
    # 错误 token → 401 invalid_token
    r0 = client.post(
        f"/api/public/coursewares/{cid}/unlock", json={"token": "WRONG"}
    )
    assert r0.status_code == 401
    assert r0.json()["code"] == "invalid_token"
    # 正确 token
    r1 = client.post(
        f"/api/public/coursewares/{cid}/unlock", json={"token": val}
    )
    assert r1.status_code == 200
    assert "tokenHash" in r1.json()["data"]
    # 详情可访问
    r2 = client.get(f"/api/public/coursewares/{cid}")
    assert r2.status_code == 200


def test_courseware_demote_open_clears_tokens(client, courseware_payload):
    rt = client.post("/api/admin/access-tokens", json={"label": "dm"})
    tid = int(rt.json()["data"]["id"])
    leaf = _mk_cat_leaf(client)
    rc = client.post("/api/admin/coursewares", json=courseware_payload(
        category_id=leaf,
        access_mode="RESTRICTED",
        token_ids=[tid],
        title="demote",
    ))
    cid = int(rc.json()["data"]["id"])
    # 升级校验:从 RESTRICTED -> OPEN → token 自动清空
    r = client.put(
        f"/api/admin/coursewares/{cid}",
        json={"accessMode": "OPEN", "tokenIds": []},
    )
    assert r.status_code == 200
    detail = client.get(f"/api/public/coursewares/{cid}").json()["data"]
    assert detail["accessMode"] == "OPEN"
    assert detail["tokenIds"] == []
