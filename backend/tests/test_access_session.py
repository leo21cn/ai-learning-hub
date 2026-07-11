"""访问会话(AccessSession)服务单元 + 公共 API 集成测试。

覆盖:
- B-1 OPEN 课件不记录
- B-2 客户端 duration 偏差 > 60s 时按服务端时间校正
- 鉴权:缺 token_hash / 无效 token / 跨 token 篡改 session
- 接口幂等:leave 多次调用安全
"""
from __future__ import annotations

import hashlib
import io

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import get_db
from app.main import app
from app.models.access_session import AccessSession
from app.services import access_token as token_svc
from app.services import access_token_usage as usage_svc

from tests.conftest import login_admin


def _hash(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _mk_cat_leaf(client: TestClient) -> int:
    a = client.post("/api/admin/categories", json={"name": "U-A"}).json()["data"]
    b = client.post(
        "/api/admin/categories", json={"name": "U-B", "parentId": a["id"]}
    ).json()["data"]
    c = client.post(
        "/api/admin/categories", json={"name": "U-C", "parentId": b["id"]}
    ).json()["data"]
    return c["id"]


def _upload_pdf(client: TestClient, name: str = "x.pdf") -> int:
    files = {"file": (name, io.BytesIO(b"%PDF-1.4 demo"), "application/pdf")}
    r = client.post("/api/admin/materials", files=files)
    assert r.status_code == 201, r.text
    return int(r.json()["data"]["id"])


def _mk_token(client: TestClient, label: str) -> tuple[int, str]:
    r = client.post("/api/admin/access-tokens", json={"label": label})
    assert r.status_code == 201
    payload = r.json()["data"]
    return int(payload["id"]), payload["value"]


def _mk_restricted_courseware_with_material(
    client: TestClient, *, token_ids: list[int], material_id: int
) -> int:
    leaf = _mk_cat_leaf(client)
    payload = {
        "title": f"cw-{material_id}",
        "categoryId": leaf,
        "accessMode": "RESTRICTED",
        "tagIds": [],
        "materialIds": [material_id],
        "tokenIds": token_ids,
        "description": None,
        "author": None,
    }
    r = client.post("/api/admin/coursewares", json=payload)
    assert r.status_code == 201, r.text
    return int(r.json()["data"]["id"])


def _mk_open_courseware_with_material(
    client: TestClient, material_id: int
) -> int:
    leaf = _mk_cat_leaf(client)
    payload = {
        "title": f"open-{material_id}",
        "categoryId": leaf,
        "accessMode": "OPEN",
        "tagIds": [],
        "materialIds": [material_id],
        "tokenIds": [],
        "description": None,
        "author": None,
    }
    r = client.post("/api/admin/coursewares", json=payload)
    assert r.status_code == 201, r.text
    return int(r.json()["data"]["id"])


# ============ 公共 API · start ============

def test_public_start_requires_token_hash(client: TestClient):
    login_admin(client)
    mid = _upload_pdf(client)
    # 没有任何 token hash → 400 missing_token(ErrorCode.MISSING_TOKEN 映射 400)
    r = client.post(
        "/api/public/access-sessions", json={"materialId": mid}
    )
    assert r.status_code == 400
    assert r.json()["code"] == "missing_token"


def test_public_start_invalid_token_hash(client: TestClient):
    login_admin(client)
    mid = _upload_pdf(client)
    r = client.post(
        "/api/public/access-sessions",
        json={"materialId": mid},
        headers={"X-Token-Hash": "deadbeef" * 8},
    )
    assert r.status_code == 401
    assert r.json()["code"] == "invalid_token"


def test_public_start_open_material_returns_not_recorded(
    client: TestClient, admin_login
):
    """B-1:素材仅在 OPEN 课件中 → recorded=False,不写库。"""
    t_id, plain = _mk_token(client, "t-open")
    th = _hash(plain)
    mid = _upload_pdf(client)
    _mk_open_courseware_with_material(client, mid)

    r = client.post(
        "/api/public/access-sessions",
        json={"materialId": mid},
        headers={"X-Token-Hash": th},
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["recorded"] is False
    assert data.get("sessionId") in (None,)


def test_public_start_restricted_records_session(
    client: TestClient, admin_login
):
    """RESTRICTED 课件 + 有效 token → recorded=True,落库 1 条。"""
    token_id, plain = _mk_token(client, "t-rec")
    token_hash = _hash(plain)
    mid = _upload_pdf(client)
    _mk_restricted_courseware_with_material(
        client, token_ids=[token_id], material_id=mid
    )

    r = client.post(
        "/api/public/access-sessions",
        json={"materialId": mid},
        headers={"X-Token-Hash": token_hash},
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["recorded"] is True
    assert isinstance(data["sessionId"], int)

    # 校验落库
    db_gen = app.dependency_overrides[get_db]()
    db = next(db_gen)
    try:
        rows = (
            db.execute(
                select(AccessSession).where(
                    AccessSession.token_id == token_id
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 1
        assert rows[0].material_id == mid
        assert rows[0].duration_seconds is None
    finally:
        try:
            next(db_gen)
        except StopIteration:
            pass


def test_public_start_token_not_authorized_for_courseware(
    client: TestClient, admin_login
):
    """token 有效,但该课件不绑定此 token → 403。"""
    t1, _plain1 = _mk_token(client, "t-1")
    _t2, plain2 = _mk_token(client, "t-2")
    mid = _upload_pdf(client)
    _mk_restricted_courseware_with_material(
        client, token_ids=[t1], material_id=mid
    )

    r = client.post(
        "/api/public/access-sessions",
        json={"materialId": mid},
        headers={"X-Token-Hash": _hash(plain2)},
    )
    assert r.status_code == 403
    assert r.json()["code"] == "courseware_acl_locked"


# ============ 公共 API · leave ============

def test_public_leave_records_duration_and_correction(
    client: TestClient, admin_login
):
    """B-2:客户端上报偏差 > 60s 时按服务端时间校正。"""
    token_id, plain = _mk_token(client, "t-leave")
    token_hash = _hash(plain)
    mid = _upload_pdf(client)
    _mk_restricted_courseware_with_material(
        client, token_ids=[token_id], material_id=mid
    )

    r1 = client.post(
        "/api/public/access-sessions",
        json={"materialId": mid},
        headers={"X-Token-Hash": token_hash},
    )
    sid = r1.json()["data"]["sessionId"]

    r2 = client.post(
        f"/api/public/access-sessions/{sid}/leave",
        json={"durationSeconds": 99999},
        headers={"X-Token-Hash": token_hash},
    )
    assert r2.status_code == 200
    assert r2.json()["data"]["ok"] is True

    db_gen = app.dependency_overrides[get_db]()
    db = next(db_gen)
    try:
        obj = db.get(AccessSession, sid)
        assert obj is not None
        assert obj.client_leave is True
        assert obj.ended_at is not None
        # 服务端实测 < 60s,客户端报 99999 → 校正为服务端值
        from datetime import timezone
        started_at = obj.started_at
        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=timezone.utc)
        server_dur = int(
            (obj.ended_at.replace(tzinfo=timezone.utc) - started_at).total_seconds()
        )
        assert obj.duration_seconds == server_dur
        assert obj.duration_seconds < 60
    finally:
        try:
            next(db_gen)
        except StopIteration:
            pass


def test_public_leave_within_tolerance_keeps_client_value(
    client: TestClient, admin_login
):
    """B-2:客户端上报偏差 ≤ 60s → 信任客户端值。"""
    token_id, plain = _mk_token(client, "t-keep")
    token_hash = _hash(plain)
    mid = _upload_pdf(client)
    _mk_restricted_courseware_with_material(
        client, token_ids=[token_id], material_id=mid
    )

    r1 = client.post(
        "/api/public/access-sessions",
        json={"materialId": mid},
        headers={"X-Token-Hash": token_hash},
    )
    sid = r1.json()["data"]["sessionId"]

    r2 = client.post(
        f"/api/public/access-sessions/{sid}/leave",
        json={"durationSeconds": 5},
        headers={"X-Token-Hash": token_hash},
    )
    assert r2.status_code == 200

    db_gen = app.dependency_overrides[get_db]()
    db = next(db_gen)
    try:
        obj = db.get(AccessSession, sid)
        assert obj.duration_seconds == 5
    finally:
        try:
            next(db_gen)
        except StopIteration:
            pass


def test_public_leave_idempotent_for_missing_session(
    client: TestClient,
):
    """不存在的 session → 200 + ok=True(幂等)。"""
    r = client.post(
        "/api/public/access-sessions/9999999/leave",
        json={"durationSeconds": 1},
    )
    assert r.status_code == 200
    assert r.json()["data"]["ok"] is True


def test_public_leave_cross_token_blocked(
    client: TestClient, admin_login
):
    """用别的 token 试图 leave 该 session → 403。"""
    token_id, plain = _mk_token(client, "t-cross-a")
    token_hash_a = _hash(plain)
    _token_id_b, plain_b = _mk_token(client, "t-cross-b")
    token_hash_b = _hash(plain_b)
    mid = _upload_pdf(client)
    _mk_restricted_courseware_with_material(
        client, token_ids=[token_id], material_id=mid
    )

    r1 = client.post(
        "/api/public/access-sessions",
        json={"materialId": mid},
        headers={"X-Token-Hash": token_hash_a},
    )
    sid = r1.json()["data"]["sessionId"]

    r2 = client.post(
        f"/api/public/access-sessions/{sid}/leave",
        json={"durationSeconds": 5},
        headers={"X-Token-Hash": token_hash_b},
    )
    assert r2.status_code == 403


# ============ Admin 聚合接口 ============

def test_admin_material_summary_orders_by_total_duration(
    client: TestClient, admin_login
):
    """按素材聚合:totalDurationSeconds DESC。"""
    t_id, plain = _mk_token(client, "t-sum")
    token_hash = _hash(plain)
    leaf = _mk_cat_leaf(client)

    m1 = _upload_pdf(client, "a.pdf")
    m2 = _upload_pdf(client, "b.pdf")

    p1 = {
        "title": "cw1",
        "categoryId": leaf,
        "accessMode": "RESTRICTED",
        "tagIds": [],
        "materialIds": [m1, m2],
        "tokenIds": [t_id],
        "description": None,
        "author": None,
    }
    r1 = client.post("/api/admin/coursewares", json=p1)
    assert r1.status_code == 201

    def _do(mid: int, dur: int) -> None:
        r = client.post(
            "/api/public/access-sessions",
            json={"materialId": mid},
            headers={"X-Token-Hash": token_hash},
        )
        sid = r.json()["data"]["sessionId"]
        client.post(
            f"/api/public/access-sessions/{sid}/leave",
            json={"durationSeconds": dur},
            headers={"X-Token-Hash": token_hash},
        )

    _do(m1, 10)
    _do(m2, 3)
    _do(m2, 3)

    r = client.get(
        f"/api/admin/access-tokens/{t_id}/access-sessions/material-summary",
        params={"start": "2000-01-01", "end": "2099-12-31"},
    )
    assert r.status_code == 200, r.text
    items = r.json()["data"]["items"]
    assert items[0]["materialId"] == m1
    assert items[0]["totalDurationSeconds"] == 10
    assert items[1]["materialId"] == m2
    assert items[1]["totalDurationSeconds"] == 6
    assert items[1]["viewCount"] == 2


def test_admin_list_sessions_paging_and_summary(
    client: TestClient, admin_login
):
    """明细分页 + 概览。"""
    t_id, plain = _mk_token(client, "t-page")
    token_hash = _hash(plain)
    mid = _upload_pdf(client)
    _mk_restricted_courseware_with_material(
        client, token_ids=[t_id], material_id=mid
    )

    for _ in range(3):
        r = client.post(
            "/api/public/access-sessions",
            json={"materialId": mid},
            headers={"X-Token-Hash": token_hash},
        )
        sid = r.json()["data"]["sessionId"]
        client.post(
            f"/api/public/access-sessions/{sid}/leave",
            json={"durationSeconds": 4},
            headers={"X-Token-Hash": token_hash},
        )

    r = client.get(
        f"/api/admin/access-tokens/{t_id}/access-sessions",
        params={"start": "2000-01-01", "end": "2099-12-31", "size": 2},
    )
    assert r.status_code == 200
    body = r.json()["data"]
    assert body["total"] == 3
    assert body["size"] == 2
    assert len(body["items"]) == 2
    assert body["summary"]["sessionCount"] == 3
    assert body["summary"]["totalDurationSeconds"] == 12
    assert body["summary"]["materialCount"] == 1
    assert body["summary"]["coursewareCount"] == 1


# ============ B-3:regenerate 不影响历史 session ============

def test_regenerate_keeps_history_attached_to_old_token_id(
    client: TestClient, admin_login
):
    """regenerate 后,旧 session 仍归属原 token_id;用旧 hash leave 旧 session → 403。"""
    t_id, plain = _mk_token(client, "t-regen-hist")
    token_hash = _hash(plain)
    mid = _upload_pdf(client)
    _mk_restricted_courseware_with_material(
        client, token_ids=[t_id], material_id=mid
    )

    r = client.post(
        "/api/public/access-sessions",
        json={"materialId": mid},
        headers={"X-Token-Hash": token_hash},
    )
    sid = r.json()["data"]["sessionId"]
    client.post(
        f"/api/public/access-sessions/{sid}/leave",
        json={"durationSeconds": 1},
        headers={"X-Token-Hash": token_hash},
    )

    # regenerate
    r2 = client.post(f"/api/admin/access-tokens/{t_id}/regenerate")
    assert r2.status_code == 200
    new_hash = r2.json()["data"]["valueHash"]
    assert new_hash != token_hash

    # 历史 session 仍属该 token_id
    r3 = client.get(
        f"/api/admin/access-tokens/{t_id}/access-sessions",
        params={"start": "2000-01-01", "end": "2099-12-31"},
    )
    assert r3.status_code == 200
    body = r3.json()["data"]
    assert body["total"] == 1
    assert body["items"][0]["id"] == sid
    # 用旧 hash 试图 leave 旧 session → 403(token_hash 不匹配)
    r4 = client.post(
        f"/api/public/access-sessions/{sid}/leave",
        json={"durationSeconds": 1},
        headers={"X-Token-Hash": token_hash},
    )
    assert r4.status_code == 403


# ============ 服务层直测 ============

def test_service_resolve_restricted_filters_open(client: TestClient):
    """service 层 _resolve_restricted_courseware:全部 OPEN → all_open=True。"""
    login_admin(client)
    mid = _upload_pdf(client)
    _mk_open_courseware_with_material(client, mid)

    db_gen = app.dependency_overrides[get_db]()
    db = next(db_gen)
    try:
        cws, all_open = usage_svc._resolve_restricted_courseware(db, mid)
        assert all_open is True
        assert all(c.access_mode.value == "OPEN" for c in cws)
    finally:
        try:
            next(db_gen)
        except StopIteration:
            pass


# ============ §3.2 GET /api/admin/access-tokens/{id} usageSummary 扩展 ============

def test_admin_get_token_without_usage_default(
    client: TestClient, admin_login
):
    """默认 ?withUsage 不传 → 不返回 usageSummary 字段。"""
    t_id, _ = _mk_token(client, "t-default-usage")
    r = client.get(f"/api/admin/access-tokens/{t_id}")
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["id"] == t_id
    assert "usageSummary" not in data


def test_admin_get_token_with_usage_1_includes_summary(
    client: TestClient, admin_login
):
    """?withUsage=1 → 返回 usageSummary 字段(含全时段聚合指标)。"""
    t_id, plain = _mk_token(client, "t-with-usage")
    token_hash = _hash(plain)
    mid = _upload_pdf(client, "u.pdf")
    _mk_restricted_courseware_with_material(
        client, token_ids=[t_id], material_id=mid
    )

    # 灌一条 5s session
    r1 = client.post(
        "/api/public/access-sessions",
        json={"materialId": mid},
        headers={"X-Token-Hash": token_hash},
    )
    sid = r1.json()["data"]["sessionId"]
    client.post(
        f"/api/public/access-sessions/{sid}/leave",
        json={"durationSeconds": 5},
        headers={"X-Token-Hash": token_hash},
    )

    r = client.get(
        f"/api/admin/access-tokens/{t_id}?withUsage=1"
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert "usageSummary" in data
    s = data["usageSummary"]
    assert s["sessionCount"] == 1
    assert s["totalDurationSeconds"] == 5
    assert s["coursewareCount"] == 1
    assert s["materialCount"] == 1


def test_admin_get_token_with_usage_0_excludes_summary(
    client: TestClient, admin_login
):
    """显式 ?withUsage=0 → 不返回 usageSummary(语义:false 等价于默认)。"""
    t_id, _ = _mk_token(client, "t-with-usage-0")
    r = client.get(f"/api/admin/access-tokens/{t_id}?withUsage=0")
    assert r.status_code == 200
    assert "usageSummary" not in r.json()["data"]


def test_admin_get_token_not_found_returns_404(
    client: TestClient, admin_login
):
    """不存在的 token_id → 404 token_not_found。"""
    r = client.get("/api/admin/access-tokens/9999999")
    assert r.status_code == 404
    assert r.json()["code"] == "token_not_found"


# ============ §2.4 限流(60/minute) ============

def test_public_start_rate_limit_blocks_after_burst(
    client: TestClient, admin_login
):
    """连续 60 次成功, 第 61 次被限流降级为 recorded=False(不阻塞)。"""
    t_id, plain = _mk_token(client, "t-rl")
    token_hash = _hash(plain)
    mid = _upload_pdf(client, "rl.pdf")
    _mk_restricted_courseware_with_material(
        client, token_ids=[t_id], material_id=mid
    )

    # 1..60 应全成功(sessionId 落库)
    for i in range(60):
        r = client.post(
            "/api/public/access-sessions",
            json={"materialId": mid},
            headers={"X-Token-Hash": token_hash},
        )
        assert r.status_code == 200, f"#{i+1} got {r.status_code} {r.text}"
        assert r.json()["data"]["recorded"] is True, f"#{i+1} not recorded"

    # 第 61 次:限流降级 recorded=false, 仍 200
    r = client.post(
        "/api/public/access-sessions",
        json={"materialId": mid},
        headers={"X-Token-Hash": token_hash},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == "ok"
    assert body["data"]["recorded"] is False


# ============ sessions/summary endpoint ============

def test_admin_sessions_summary_returns_overview_only(
    client, admin_login
):
    t_id, plain = _mk_token(client, "t-sum-ep")
    token_hash = _hash(plain)
    mid = _upload_pdf(client, "sum.pdf")
    _mk_restricted_courseware_with_material(
        client, token_ids=[t_id], material_id=mid
    )
    for dur in (12, 7):
        r1 = client.post(
            "/api/public/access-sessions",
            json={"materialId": mid},
            headers={"X-Token-Hash": token_hash},
        )
        sid = r1.json()["data"]["sessionId"]
        client.post(
            f"/api/public/access-sessions/{sid}/leave",
            json={"durationSeconds": dur},
            headers={"X-Token-Hash": token_hash},
        )
    r = client.get(
        f"/api/admin/access-tokens/{t_id}/access-sessions/summary",
        params={"start": "2000-01-01", "end": "2099-12-31"},
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert set(data.keys()) == {
        "totalDurationSeconds",
        "sessionCount",
        "coursewareCount",
        "materialCount",
    }
    assert data["sessionCount"] == 2
    assert data["totalDurationSeconds"] == 19
    assert data["coursewareCount"] == 1
    assert data["materialCount"] == 1


# ============ 业务时区(Asia/Shanghai)下日期区间语义 ============

def test_admin_list_sessions_uses_business_timezone(
    client: TestClient, admin_login
):
    """业务时区为 settings.timezone(默认 Asia/Shanghai)。

    场景:本地 2026-07-11 07:35 的访问 = UTC 2026-07-10 23:35 存库。
    查询 start=end="2026-07-11"(本地日历日)应命中 1 条;
    查询 start=end="2026-07-10"(本地日历日)应 0 条。

    旧实现按 UTC 解析会导致本地 7-11 0:00-8:00 间的访问查不到。
    """
    from datetime import datetime, timezone as _tz
    from app.models.access_session import AccessSession

    t_id, plain = _mk_token(client, "t-tz")
    token_hash = _hash(plain)
    mid = _upload_pdf(client, "tz.pdf")
    _mk_restricted_courseware_with_material(
        client, token_ids=[t_id], material_id=mid
    )

    r = client.post(
        "/api/public/access-sessions",
        json={"materialId": mid},
        headers={"X-Token-Hash": token_hash},
    )
    sid = r.json()["data"]["sessionId"]

    # 改 started_at 到 UTC 2026-07-10 23:35 = 本地 2026-07-11 07:35
    db_gen = app.dependency_overrides[get_db]()
    db = next(db_gen)
    try:
        obj = db.get(AccessSession, sid)
        obj.started_at = datetime(2026, 7, 10, 23, 35, 0, tzinfo=_tz.utc)
        db.commit()
    finally:
        try:
            next(db_gen)
        except StopIteration:
            pass

    # 本地 7-11 应命中 1 条
    r = client.get(
        f"/api/admin/access-tokens/{t_id}/access-sessions",
        params={"start": "2026-07-11", "end": "2026-07-11"},
    )
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert body["total"] == 1, f"本地 7-11 应命中 1 条,实际 {body['total']}"
    assert body["items"][0]["id"] == sid
    # summary 也应一致
    assert body["summary"]["sessionCount"] == 1

    # 本地 7-10 不应命中(UTC 7-10 23:35 = 本地 7-11)
    r = client.get(
        f"/api/admin/access-tokens/{t_id}/access-sessions",
        params={"start": "2026-07-10", "end": "2026-07-10"},
    )
    assert r.status_code == 200
    body = r.json()["data"]
    assert body["total"] == 0, f"本地 7-10 不应命中,实际 {body['total']}"

    # 跨日范围:本地 7-10 ~ 7-11 应命中 1 条
    r = client.get(
        f"/api/admin/access-tokens/{t_id}/access-sessions",
        params={"start": "2026-07-10", "end": "2026-07-11"},
    )
    assert r.status_code == 200
    body = r.json()["data"]
    assert body["total"] == 1
