"""访问会话业务服务。

- start_session:开新会话(供公共 API 调用,带 B-1 OPEN 跳过 / 鉴权)
- leave_session:结束会话(供公共 API 调用,带 B-2 时长校正)
- list_sessions:分页明细(供管理 API 调用)
- list_material_summary:按素材聚合(本期重点,供管理 API 调用)
- summary_overall:全时段聚合(供管理 API 在 GET /api/admin/access-tokens/{id}?withUsage=1 时使用)

业务规则详见 plan §1.1 / §2.2 / §2.3 / §3.2。
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from sqlalchemy import case, Float, func, select
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session
from sqlalchemy.sql.expression import ColumnElement, FunctionElement

from app.core.config import get_settings
from app.core.errors import BusinessError, ErrorCode
from app.models.access_session import AccessSession
from app.models.access_token import AccessToken
from app.models.association import courseware_material
from app.models.courseware import AccessMode, Courseware
from app.models.material import Material
from app.services import access_token as token_svc
from app.services import audit
from app.services import courseware as courseware_svc

# 客户端/服务端 duration 偏差阈值,超过则按服务端时间校正(防客户端时钟漂移/篡改)
DURATION_TOLERANCE_SECONDS = 60


def _as_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """统一将 DB 读出的 datetime 视为 UTC(naive → 补 UTC tzinfo)。"""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _resolve_restricted_courseware(
    db: Session, material_id: int
) -> Tuple[List[Courseware], bool]:
    """返回 (含此素材的所有引用课件, 是否全部为 OPEN)。

    B-1:若全部为 OPEN,调用方应直接返回 recorded=False,不写库。
    """
    refs = (
        db.query(courseware_material.c.courseware_id)
        .filter(courseware_material.c.material_id == material_id)
        .all()
    )
    if not refs:
        return [], True
    cw_ids = [r[0] for r in refs]
    coursewares = courseware_svc.get_many(db, cw_ids)
    all_open = all(c.access_mode == AccessMode.OPEN for c in coursewares)
    return coursewares, all_open


def start_session(
    db: Session,
    *,
    material_id: int,
    token_hash: str,
    ip: Optional[str] = None,
    ua: Optional[str] = None,
) -> Dict[str, Optional[str]]:
    """开一条 access_session。"""
    if not token_hash:
        raise BusinessError(ErrorCode.MISSING_TOKEN, "缺少令牌")

    token = token_svc.get_by_hash(db, token_hash)
    if not token:
        raise BusinessError(ErrorCode.INVALID_TOKEN, "令牌无效")

    material = db.get(Material, material_id)
    if not material:
        raise BusinessError(ErrorCode.MATERIAL_NOT_FOUND, "素材不存在")

    coursewares, all_open = _resolve_restricted_courseware(db, material_id)
    if all_open or not coursewares:
        return {"sessionId": None, "startedAt": None, "recorded": False}

    allowed_hashes: set[str] = set()
    for c in coursewares:
        for t in (c.access_tokens or []):
            allowed_hashes.add(t.value_hash)
    if token_hash not in allowed_hashes:
        raise BusinessError(
            ErrorCode.COURSEWARE_ACL_LOCKED, "令牌无权访问该素材"
        )

    restricted = [c for c in coursewares if c.access_mode == AccessMode.RESTRICTED]
    target_courseware = sorted(restricted, key=lambda c: c.id)[0]

    started_at = datetime.now(tz=timezone.utc)
    obj = AccessSession(
        token_id=token.id,
        courseware_id=target_courseware.id,
        material_id=material_id,
        started_at=started_at,
        ip=ip,
        ua=(ua or "")[:256] or None,
    )
    db.add(obj)
    try:
        db.commit()
    except Exception as e:  # pragma: no cover
        db.rollback()
        audit.write(
            "access_session.start_failed",
            resource=f"material:{material_id}",
            payload={"error": str(e)[:200]},
        )
        return {"sessionId": None, "startedAt": None, "recorded": False}
    db.refresh(obj)
    return {
        "sessionId": int(obj.id),
        "startedAt": obj.started_at.isoformat() if obj.started_at else None,
        "recorded": True,
    }


def leave_session(
    db: Session,
    *,
    session_id: int,
    token_hash: str,
    duration_seconds: Optional[int] = None,
) -> bool:
    """结束一条 access_session;幂等(不存在直接返回 True)。"""
    obj = db.get(AccessSession, session_id)
    if not obj:
        return True

    token = db.get(AccessToken, obj.token_id)
    if not token or token.value_hash != token_hash:
        raise BusinessError(ErrorCode.COURSEWARE_ACL_LOCKED, "令牌不匹配")

    ended_at = datetime.now(tz=timezone.utc)
    started_at = _as_utc(obj.started_at) or ended_at
    server_duration = int((ended_at - started_at).total_seconds())
    if server_duration < 0:
        server_duration = 0

    if duration_seconds is None:
        final_duration = server_duration
    else:
        if abs(int(duration_seconds) - server_duration) > DURATION_TOLERANCE_SECONDS:
            final_duration = server_duration
        else:
            final_duration = max(0, int(duration_seconds))

    obj.ended_at = ended_at
    obj.duration_seconds = final_duration
    obj.client_leave = True
    try:
        db.commit()
    except Exception as e:  # pragma: no cover
        db.rollback()
        audit.write(
            "access_session.leave_failed",
            resource=f"session:{session_id}",
            payload={"error": str(e)[:200]},
        )
        return False
    return True


# ============ Admin 查询 ============

def _parse_range(start: str, end: str) -> Tuple[datetime, datetime]:
    """解析 start/end(YYYY-MM-DD)为 UTC 区间 [start 00:00, end+1 00:00)。

    业务时区为 settings.timezone(默认 Asia/Shanghai),
    把用户输入的"本地日历日"翻译为 UTC 区间,与 DB 存储的 UTC 时间比较。
    例:用户传 start=end="2026-07-11" 时,在 UTC+8 下
      → [2026-07-10 16:00 UTC, 2026-07-11 16:00 UTC)
      这样 2026-07-11 07:35(本地)的访问 = 2026-07-10 23:35 UTC 可被命中。
    """
    try:
        sd = date.fromisoformat(start)
        ed = date.fromisoformat(end)
    except Exception as e:
        raise BusinessError(
            ErrorCode.INTERNAL_ERROR, f"日期格式错误(start/end): {e}"
        ) from e
    if sd > ed:
        raise BusinessError(
            ErrorCode.INTERNAL_ERROR, "起始日期不能晚于结束日期"
        )
    tz = ZoneInfo(get_settings().timezone)
    start_dt = datetime.combine(sd, time.min, tzinfo=tz).astimezone(timezone.utc)
    end_exclusive = datetime.combine(
        ed + timedelta(days=1), time.min, tzinfo=tz
    ).astimezone(timezone.utc)
    return start_dt, end_exclusive


def _epoch_diff_sql(end_expr, start_expr):
    """返回 (end - start) 的秒数表达式。

    跨方言:
    - PostgreSQL:EXTRACT(EPOCH FROM (end - start))  →  float8
    - SQLite  : (julianday(end) - julianday(start)) * 86400  →  real
    """
    return _EpochDiff(end_expr, start_expr)


class _EpochDiff(ColumnElement):
    """跨方言的 (end - start) 秒数表达式。

    继承 ColumnElement 并显式提供 type=Float() 使其能在 case() 中被推导。
    使用 clauses 属性装填子节点,SQLAlchemy 递归 compiler.process() 会逐个访问它们。
    """

    type = Float()
    inherit_cache = True

    def __init__(self, end, start):
        super().__init__()
        # 保存原始子节点供 _compiler_dispatch 调用
        self._end = end
        self._start = start

    def _compiler_dispatch(self, visitor, **kw):
        # 这个方法会被 SQLAlchemy 生成的匿名子类在编译时调用
        # 手动调用 compiler 生成 SQL
        end_sql = visitor.process(self._end, **kw)
        start_sql = visitor.process(self._start, **kw)
        return f"({end_sql} - {start_sql})"


@compiles(_EpochDiff, "postgresql")
def _pg_epoch_diff(element, compiler, **kw):
    end = compiler.process(element._end, **kw)
    start = compiler.process(element._start, **kw)
    return f"EXTRACT(EPOCH FROM ({end} - {start}))"


@compiles(_EpochDiff, "sqlite")
def _sqlite_epoch_diff(element, compiler, **kw):
    end = compiler.process(element._end, **kw)
    start = compiler.process(element._start, **kw)
    return f"(julianday({end}) - julianday({start})) * 86400"


def _session_dur_expr():
    """单条 session 持续秒数表达式。

    优先用 leave 时写入的 duration_seconds(精确整数);
    进行中(ended_at=NULL)用 now()-started_at 估算(秒)。
    """
    return case(
        (
            AccessSession.ended_at.is_(None),
            _epoch_diff_sql(func.now(), AccessSession.started_at),
        ),
        else_=func.coalesce(
            AccessSession.duration_seconds,
            _epoch_diff_sql(AccessSession.ended_at, AccessSession.started_at),
        ),
    )


def _summary_query(
    db: Session,
    token_id: int,
    start_dt: Optional[datetime] = None,
    end_dt: Optional[datetime] = None,
):
    """对 (token, [start_dt, end_dt)) 计算总停留 / 次数 / 课件数 / 素材数。

    start_dt/end_dt=None 表示无时段限制(全时段聚合)。
    """
    cond = [AccessSession.token_id == token_id]
    if start_dt is not None:
        cond.append(AccessSession.started_at >= start_dt)
    if end_dt is not None:
        cond.append(AccessSession.started_at < end_dt)
    base = select(
        func.coalesce(func.sum(_session_dur_expr()), 0).label("total_duration"),
        func.count(AccessSession.id).label("session_count"),
        func.count(func.distinct(AccessSession.courseware_id)).label("cw_count"),
        func.count(func.distinct(AccessSession.material_id)).label("mat_count"),
    ).where(*cond)
    return db.execute(base).one()


def summary_overall(db: Session, token_id: int) -> dict:
    """全时段聚合,供 GET /api/admin/access-tokens/{id}?withUsage=1 使用。"""
    row = _summary_query(db, token_id)
    return {
        "totalDurationSeconds": int(row.total_duration or 0),
        "sessionCount": int(row.session_count or 0),
        "coursewareCount": int(row.cw_count or 0),
        "materialCount": int(row.mat_count or 0),
    }


def summary_in_range(
    db: Session, token_id: int, start: str, end: str
) -> dict:
    """区间聚合,供 GET /api/admin/access-tokens/{id}/access-sessions/summary 使用。

    不返回 items,仅返回 4 个聚合指标(总停留 / 次数 / 课件数 / 素材数),
    供前端概览卡首屏即用,避免拉全量台账数据。
    """
    start_dt, end_dt = _parse_range(start, end)
    row = _summary_query(db, token_id, start_dt, end_dt)
    return {
        "totalDurationSeconds": int(row.total_duration or 0),
        "sessionCount": int(row.session_count or 0),
        "coursewareCount": int(row.cw_count or 0),
        "materialCount": int(row.mat_count or 0),
    }


def list_sessions(
    db: Session,
    *,
    token_id: int,
    start: str,
    end: str,
    material_id: Optional[int] = None,
    courseware_id: Optional[int] = None,
    page: int = 1,
    size: int = 20,
) -> dict:
    """分页访问台账 + 区间内聚合。"""
    start_dt, end_dt = _parse_range(start, end)
    if not db.get(AccessToken, token_id):
        raise BusinessError(ErrorCode.TOKEN_NOT_FOUND, "令牌不存在")

    count_q = select(func.count(AccessSession.id)).where(
        AccessSession.token_id == token_id,
        AccessSession.started_at >= start_dt,
        AccessSession.started_at < end_dt,
    )
    if material_id is not None:
        count_q = count_q.where(AccessSession.material_id == material_id)
    if courseware_id is not None:
        count_q = count_q.where(AccessSession.courseware_id == courseware_id)
    total = int(db.execute(count_q).scalar_one() or 0)

    sum_row = _summary_query(db, token_id, start_dt, end_dt)

    items_q = (
        select(AccessSession, Material.name, Material.type, Courseware.title)
        .join(Material, AccessSession.material_id == Material.id)
        .join(Courseware, AccessSession.courseware_id == Courseware.id)
        .where(
            AccessSession.token_id == token_id,
            AccessSession.started_at >= start_dt,
            AccessSession.started_at < end_dt,
        )
    )
    if material_id is not None:
        items_q = items_q.where(AccessSession.material_id == material_id)
    if courseware_id is not None:
        items_q = items_q.where(AccessSession.courseware_id == courseware_id)
    items_q = (
        items_q.order_by(AccessSession.started_at.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    rows = db.execute(items_q).all()

    def _fmt_dt(d: Optional[datetime]) -> Optional[str]:
        d2 = _as_utc(d)
        return d2.isoformat() if d2 else None

    items = [
        {
            "id": int(s.id),
            "startedAt": _fmt_dt(s.started_at),
            "endedAt": _fmt_dt(s.ended_at),
            "durationSeconds": (
                int(s.duration_seconds) if s.duration_seconds is not None else None
            ),
            "clientLeave": bool(s.client_leave),
            "coursewareId": int(s.courseware_id),
            "coursewareTitle": cw_title,
            "materialId": int(s.material_id),
            "materialName": m_name,
            "materialType": m_type,
            "ip": s.ip,
            "ua": s.ua,
        }
        for (s, m_name, m_type, cw_title) in rows
    ]

    return {
        "page": page,
        "size": size,
        "total": total,
        "summary": {
            "totalDurationSeconds": int(sum_row.total_duration or 0),
            "sessionCount": int(sum_row.session_count or 0),
            "coursewareCount": int(sum_row.cw_count or 0),
            "materialCount": int(sum_row.mat_count or 0),
        },
        "items": items,
    }


def list_material_summary(
    db: Session,
    *,
    token_id: int,
    start: str,
    end: str,
) -> dict:
    """按素材聚合(本期重点)。"""
    start_dt, end_dt = _parse_range(start, end)
    if not db.get(AccessToken, token_id):
        raise BusinessError(ErrorCode.TOKEN_NOT_FOUND, "令牌不存在")

    sub = (
        select(
            AccessSession.material_id.label("material_id"),
            AccessSession.courseware_id.label("courseware_id"),
            AccessSession.started_at.label("started_at"),
            _session_dur_expr().label("dur"),
        )
        .where(
            AccessSession.token_id == token_id,
            AccessSession.started_at >= start_dt,
            AccessSession.started_at < end_dt,
        )
        .subquery()
    )
    from sqlalchemy import desc as _desc

    ranked = (
        select(
            sub.c.material_id,
            sub.c.courseware_id,
            sub.c.started_at,
            sub.c.dur,
            func.row_number()
            .over(
                partition_by=sub.c.material_id,
                order_by=sub.c.started_at.desc(),
            )
            .label("rn"),
        )
        .subquery()
    )
    agg_q = (
        select(
            ranked.c.material_id,
            func.sum(ranked.c.dur).label("total_dur"),
            func.count(ranked.c.material_id).label("view_count"),
            func.max(ranked.c.started_at).label("last_viewed"),
            func.max(
                case(
                    (ranked.c.rn == 1, ranked.c.courseware_id), else_=None
                )
            ).label("latest_cw_id"),
        )
        .group_by(ranked.c.material_id)
        .order_by(_desc("total_dur"))
    )
    rows = db.execute(agg_q).all()

    if not rows:
        return {"start": start, "end": end, "items": []}

    mat_ids = sorted({int(r.material_id) for r in rows})
    cw_ids = sorted(
        {int(r.latest_cw_id) for r in rows if r.latest_cw_id is not None}
    )
    mat_map: Dict[int, Material] = {}
    cw_map: Dict[int, Courseware] = {}
    if mat_ids:
        for m in db.execute(
            select(Material).where(Material.id.in_(mat_ids))
        ).scalars():
            mat_map[int(m.id)] = m
    if cw_ids:
        for c in db.execute(
            select(Courseware).where(Courseware.id.in_(cw_ids))
        ).scalars():
            cw_map[int(c.id)] = c

    items = []
    for r in rows:
        m = mat_map.get(int(r.material_id))
        cw = (
            cw_map.get(int(r.latest_cw_id))
            if r.latest_cw_id is not None
            else None
        )
        items.append(
            {
                "materialId": int(r.material_id),
                "materialName": m.name if m else f"#{r.material_id}",
                "materialType": m.type if m else "",
                "coursewareId": int(r.latest_cw_id) if r.latest_cw_id else 0,
                "coursewareTitle": cw.title if cw else f"#{r.latest_cw_id}",
                "totalDurationSeconds": int(r.total_dur or 0),
                "viewCount": int(r.view_count or 0),
                "lastViewedAt": (
                    _as_utc(r.last_viewed).isoformat() if r.last_viewed else None
                ),
            }
        )

    return {"start": start, "end": end, "items": items}


__all__ = [
    "start_session",
    "leave_session",
    "list_sessions",
    "list_material_summary",
    "summary_overall",
    "summary_in_range",
    "DURATION_TOLERANCE_SECONDS",
]
