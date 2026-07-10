"""v1.5 课件素材顺序编辑(AC-041~050)测试。

覆盖：
- AC-041 新建课件挂多个素材,sortOrder 默认按数组下标 0..N-1
- AC-042 删除素材时,其余素材 sortOrder 保持不变
- AC-043 专用 PUT /materials/order 接口成功反转顺序
- AC-044 order 接口传入未绑定 ID → 400 + courseware_materials_invalid
- AC-045 order 接口传入重复 ID → 400
- AC-046 顺序变更后前台 P-DETAIL 按新顺序渲染
- AC-047 现有 PUT /{id} 替换素材,旧素材保留 sortOrder,新素材追加末尾
- AC-048 迁移后既有课件 sortOrder 按 material_id 升序回填(集成到 ORM 测试)
- AC-049 索引 ix_courseware_material_courseware_order 存在
"""
from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect, select

from app.db import get_db
from app.main import app
from app.models.association import courseware_material
from app.models.courseware import Courseware
from app.models.material import Material


# ----------------------- 工具 -----------------------

def _make_category_leaf(client: TestClient) -> int:
    a = client.post("/api/admin/categories", json={"name": "T-A"}).json()["data"]
    b = client.post(
        "/api/admin/categories", json={"name": "T-B", "parentId": a["id"]}
    ).json()["data"]
    c = client.post(
        "/api/admin/categories", json={"name": "T-C", "parentId": b["id"]}
    ).json()["data"]
    return c["id"]


def _upload_material(client: TestClient, name: str) -> int:
    files = {"file": (name, io.BytesIO(b"%PDF-1.4 demo " + name.encode()), "application/pdf")}
    r = client.post("/api/admin/materials", files=files)
    assert r.status_code == 201, r.text
    return r.json()["data"]["id"]


def _get_db():
    """绕过 FastAPI 依赖注入,直接拿到测试 Session。"""
    db_gen = app.dependency_overrides[get_db]()
    db = next(db_gen)
    return db, db_gen


def _sort_orders(db, courseware_id: int) -> list[tuple[int, int]]:
    """读出 (material_id, sort_order) 并按 sort_order 排序。"""
    rows = db.execute(
        select(
            courseware_material.c.material_id,
            courseware_material.c.sort_order,
        ).where(courseware_material.c.courseware_id == courseware_id)
    ).all()
    return sorted([(r[0], r[1]) for r in rows], key=lambda x: x[1])


# ----------------------- AC-041 -----------------------

def test_courseware_materials_default_sort_order_on_create(
    client: TestClient, courseware_payload
):
    """AC-041: 新建课件挂 3 个素材,sortOrder 应为 0,1,2。"""
    m1 = _upload_material(client, "a.pdf")
    m2 = _upload_material(client, "b.pdf")
    m3 = _upload_material(client, "c.pdf")

    leaf = _make_category_leaf(client)
    r = client.post(
        "/api/admin/coursewares",
        json=courseware_payload(
            category_id=leaf, access_mode="OPEN", material_ids=[m1, m2, m3]
        ),
    )
    assert r.status_code == 201, r.text
    cid = r.json()["data"]["id"]
    detail = client.get(f"/api/admin/coursewares/{cid}").json()["data"]
    sort_orders = [m["sortOrder"] for m in detail["materials"]]
    assert sort_orders == [0, 1, 2]
    # materialIds 顺序与 sortOrder 一致
    assert detail["materialIds"] == [m1, m2, m3]


# ----------------------- AC-042 -----------------------

def test_courseware_delete_material_preserves_other_sort_order(
    client: TestClient, courseware_payload
):
    """AC-042: 通过 PUT 把素材从 3 个减到 2 个,保留的两个 sortOrder 不变。"""
    m1 = _upload_material(client, "a.pdf")
    m2 = _upload_material(client, "b.pdf")
    m3 = _upload_material(client, "c.pdf")
    leaf = _make_category_leaf(client)
    cid = client.post(
        "/api/admin/coursewares",
        json=courseware_payload(
            category_id=leaf, access_mode="OPEN", material_ids=[m1, m2, m3]
        ),
    ).json()["data"]["id"]
    # 移除 m2(原 sortOrder=1),只保留 m1(0) / m3(2)
    r = client.put(
        f"/api/admin/coursewares/{cid}",
        json={"materialIds": [m1, m3]},
    )
    assert r.status_code == 200, r.text
    detail = client.get(f"/api/admin/coursewares/{cid}").json()["data"]
    # 剩下的两个保持原 sortOrder(0,2),不重排
    assert detail["materialIds"] == [m1, m3]
    assert [m["sortOrder"] for m in detail["materials"]] == [0, 2]


# ----------------------- AC-043 -----------------------

def test_courseware_reorder_endpoint_success(
    client: TestClient, courseware_payload
):
    """AC-043: 专用排序接口按数组下标重写 sortOrder。"""
    m1 = _upload_material(client, "a.pdf")
    m2 = _upload_material(client, "b.pdf")
    m3 = _upload_material(client, "c.pdf")
    leaf = _make_category_leaf(client)
    cid = client.post(
        "/api/admin/coursewares",
        json=courseware_payload(
            category_id=leaf, access_mode="OPEN", material_ids=[m1, m2, m3]
        ),
    ).json()["data"]["id"]

    # 反转顺序
    r = client.put(
        f"/api/admin/coursewares/{cid}/materials/order",
        json={"materialIds": [m3, m2, m1]},
    )
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert body["materialIds"] == [m3, m2, m1]
    assert [m["sortOrder"] for m in body["materials"]] == [0, 1, 2]

    # 验证 DB 中 sortOrder 同步生效
    db, db_gen = _get_db()
    try:
        orders = _sort_orders(db, cid)
        assert orders == [(m3, 0), (m2, 1), (m1, 2)]
    finally:
        try:
            next(db_gen)
        except StopIteration:
            pass


# ----------------------- AC-046 -----------------------

def test_courseware_reorder_reflected_on_public_detail(
    client: TestClient, courseware_payload
):
    """AC-046: 前台 P-DETAIL 在重排后按新顺序返回。"""
    m1 = _upload_material(client, "a.pdf")
    m2 = _upload_material(client, "b.pdf")
    m3 = _upload_material(client, "c.pdf")
    leaf = _make_category_leaf(client)
    cid = client.post(
        "/api/admin/coursewares",
        json=courseware_payload(
            category_id=leaf, access_mode="OPEN", material_ids=[m1, m2, m3]
        ),
    ).json()["data"]["id"]
    client.put(
        f"/api/admin/coursewares/{cid}/materials/order",
        json={"materialIds": [m3, m1, m2]},
    )
    pub = client.get(f"/api/public/coursewares/{cid}").json()["data"]
    assert pub["materialIds"] == [m3, m1, m2]
    assert [m["sortOrder"] for m in pub["materials"]] == [0, 1, 2]


# ----------------------- AC-044 -----------------------

def test_courseware_reorder_invalid_membership(
    client: TestClient, courseware_payload
):
    """AC-044: 传入未绑定的 material_id → 400 + courseware_materials_invalid。"""
    m1 = _upload_material(client, "a.pdf")
    m_unbound = _upload_material(client, "x.pdf")
    leaf = _make_category_leaf(client)
    cid = client.post(
        "/api/admin/coursewares",
        json=courseware_payload(
            category_id=leaf, access_mode="OPEN", material_ids=[m1]
        ),
    ).json()["data"]["id"]
    r = client.put(
        f"/api/admin/coursewares/{cid}/materials/order",
        json={"materialIds": [m_unbound]},  # 不属于该课件
    )
    assert r.status_code == 400, r.text
    assert r.json()["code"] == "courseware_materials_invalid"


# ----------------------- AC-045 -----------------------

def test_courseware_reorder_duplicate_ids(
    client: TestClient, courseware_payload
):
    """AC-045: 重复 ID → 400。"""
    m1 = _upload_material(client, "a.pdf")
    m2 = _upload_material(client, "b.pdf")
    leaf = _make_category_leaf(client)
    cid = client.post(
        "/api/admin/coursewares",
        json=courseware_payload(
            category_id=leaf, access_mode="OPEN", material_ids=[m1, m2]
        ),
    ).json()["data"]["id"]
    r = client.put(
        f"/api/admin/coursewares/{cid}/materials/order",
        json={"materialIds": [m1, m1]},  # 重复
    )
    assert r.status_code == 400, r.text
    assert r.json()["code"] == "courseware_materials_invalid"


# ----------------------- AC-047 -----------------------

def test_courseware_update_material_ids_keeps_old_sort_order(
    client: TestClient, courseware_payload
):
    """AC-047: PUT /{id} 替换素材集合时,旧素材保留原 sortOrder,新素材追加末尾。"""
    m1 = _upload_material(client, "a.pdf")
    m2 = _upload_material(client, "b.pdf")
    m3 = _upload_material(client, "c.pdf")
    leaf = _make_category_leaf(client)
    cid = client.post(
        "/api/admin/coursewares",
        json=courseware_payload(
            category_id=leaf, access_mode="OPEN", material_ids=[m1, m2]
        ),
    ).json()["data"]["id"]
    # 此时 m1.sortOrder=0, m2.sortOrder=1
    # 替换为 [m2, m3]  → m2 保留 1;m3 追加为 2
    r = client.put(
        f"/api/admin/coursewares/{cid}",
        json={"materialIds": [m2, m3]},
    )
    assert r.status_code == 200, r.text
    detail = client.get(f"/api/admin/coursewares/{cid}").json()["data"]
    assert detail["materialIds"] == [m2, m3]
    so = {m["id"]: m["sortOrder"] for m in detail["materials"]}
    assert so[m2] == 1
    assert so[m3] == 2


# ----------------------- AC-049 -----------------------

def test_courseware_material_order_index_exists():
    """AC-049: 索引 ix_courseware_material_courseware_order 在表上存在。"""
    db, db_gen = _get_db()
    try:
        inspector = inspect(db.get_bind())
        indexes = inspector.get_indexes("courseware_material")
        names = {ix["name"] for ix in indexes}
        assert "ix_courseware_material_courseware_order" in names
    finally:
        try:
            next(db_gen)
        except StopIteration:
            pass


# ----------------------- AC-048(模型级校验) -----------------------

def test_courseware_material_default_sort_order_zero():
    """AC-048(配套): 课程表单没有显式传 sortOrder 时,默认值(Column default)为 0。

    直接构造 ORM 行写入,验证默认行为。
    """
    db, db_gen = _get_db()
    try:
        # 准备一个课程与素材
        cat = _make_category_leaf_via_db(db)
        cw = Courseware(
            title="orm-default",
            category_id=cat.id,
            access_mode="OPEN",
        )
        m = Material(
            name="o.pdf",
            type="PDF",
            size_bytes=10,
            storage_path="o.pdf",
        )
        db.add(cw)
        db.add(m)
        db.flush()
        # 通过二级表直接插入;若 Column default 生效,sort_order 应为 0
        db.execute(
            courseware_material.insert().values(
                courseware_id=cw.id, material_id=m.id
            )
        )
        db.commit()
        row = db.execute(
            select(courseware_material.c.sort_order).where(
                (courseware_material.c.courseware_id == cw.id)
                & (courseware_material.c.material_id == m.id)
            )
        ).first()
        assert row[0] == 0
    finally:
        try:
            next(db_gen)
        except StopIteration:
            pass


def _make_category_leaf_via_db(db):
    """绕过 HTTP,直接用 ORM 建一棵 3 级分类并返回叶子节点。"""
    from app.models.category import Category

    a = Category(name="ORM-A", level=1, parent_id=None)
    db.add(a)
    db.flush()
    b = Category(name="ORM-B", level=2, parent_id=a.id)
    db.add(b)
    db.flush()
    c = Category(name="ORM-C", level=3, parent_id=b.id)
    db.add(c)
    db.flush()
    return c


# ----------------------- 课件不存在 -----------------------

def test_courseware_reorder_not_found(client: TestClient, admin_login):
    """对不存在的 courseware_id 调 order 接口 → 404 courseware_not_found。"""
    r = client.put(
        "/api/admin/coursewares/9999999/materials/order",
        json={"materialIds": [1]},
    )
    assert r.status_code == 404, r.text
    assert r.json()["code"] == "courseware_not_found"
