"""公共 API:访问会话开始/结束(无需 admin 鉴权,凭 token hash 即可)。"""
from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock
from typing import Deque, Dict, Optional

from fastapi import APIRouter, Depends, Request
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.errors import BusinessError
from app.db import get_db
from app.schemas import ok
from app.schemas.access_token_usage import (
    AccessSessionLeaveRequest,
    AccessSessionLeaveResponse,
    AccessSessionStartRequest,
    AccessSessionStartResponse,
)
from app.services import access_token_usage as svc

router = APIRouter(
    prefix="/api/public/access-sessions", tags=["public/access-sessions"]
)


# ============ Spec §2.4 进程内 IP 限流(60/minute) ============
# 不用 @limiter.limit 装饰器的原因:
# slowapi 0.1.x 装饰器在 Pydantic body 路由上与 FastAPI 的依赖解析有
# 已知的兼容性问题(包装函数签名解析异常 / 与 __future__ annotations
# 冲突);改为函数体内手动限流,语义等价,工程更稳。
# 限制是进程内不跨 worker(多进程部署需结合 nginx limit_req);本字段
# 仅作为应用层兜底。
_RATE_LIMIT_PER_MIN = 60
_RATE_WINDOW_SEC = 60
_rate_buckets: Dict[str, Deque[float]] = defaultdict(deque)
_rate_lock = Lock()


def _allow_request(ip: str) -> bool:
    """滑动窗口 IP 限流。返回 True 表示放行。"""
    now = time.monotonic()
    cutoff = now - _RATE_WINDOW_SEC
    with _rate_lock:
        bucket = _rate_buckets[ip]
        # 弹出过期记录
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= _RATE_LIMIT_PER_MIN:
            return False
        bucket.append(now)
        return True


def _resolve_token_hash(request: Request) -> Optional[str]:
    """与 coursewares.py / materials.py 一致:优先 X-Token-Hash,否则 cookie。"""
    h = request.headers.get("X-Token-Hash")
    if h:
        return h
    return request.cookies.get("lh_token_hash")


@router.post("", response_model=None)
def start(
    request: Request,
    payload: AccessSessionStartRequest,
    db: Session = Depends(get_db),  # type: ignore[no-untyped-def]
):
    """开启一个 P-VIEWER 访问会话。

    行为:
    - 缺 token_hash → 400 missing_token
    - token 不存在 → 401 invalid_token
    - IP 命中 Spec §2.4 限流 → 200 recorded=False(降级,不阻塞)
    - 素材无引用或全部 OPEN → 200 recorded=False(不写库,语义:OPEN 不记录)
    - 素材被 RESTRICTED 课件引用但 token 未授权 → 403
    - 写入失败 → 200 recorded=False(吞错,不阻塞前台)
    """
    ip = request.client.host if request.client else "unknown"
    if not _allow_request(ip):
        # 限流命中:降级为不记录(不阻塞 P-VIEWER 主流程)
        return ok(
            data=AccessSessionStartResponse(
                sessionId=None, startedAt=None, recorded=False
            ).model_dump(exclude_none=True)
        )

    token_hash = _resolve_token_hash(request) or ""
    ua = request.headers.get("user-agent")
    try:
        data = svc.start_session(
            db,
            material_id=payload.materialId,
            token_hash=token_hash,
            ip=ip,
            ua=ua,
        )
    except BusinessError:
        # 业务校验(400/401/403):透传给上层统一 envelope 处理
        raise
    except SQLAlchemyError:
        # DB 故障:吞错,降级为不记录(不阻塞前台)
        data = {"sessionId": None, "startedAt": None, "recorded": False}
    return ok(data=AccessSessionStartResponse(**data).model_dump(exclude_none=True))


@router.post("/{session_id}/leave", response_model=None)
def leave(
    request: Request,
    session_id: int,
    payload: AccessSessionLeaveRequest,
    db: Session = Depends(get_db),  # type: ignore[no-untyped-def]
):
    """结束一个访问会话;幂等(不存在的 session 视为 ok)。

    鉴权:请求的 token_hash 必须与 session.token_id 对应的 value_hash 一致;
    否则 403,前端不感知(失败静默)。
    """
    token_hash = _resolve_token_hash(request) or ""
    try:
        ok_flag = svc.leave_session(
            db,
            session_id=session_id,
            token_hash=token_hash,
            duration_seconds=payload.durationSeconds,
        )
    except BusinessError:
        raise
    except SQLAlchemyError:
        ok_flag = False
    return ok(data=AccessSessionLeaveResponse(ok=ok_flag).model_dump())


__all__ = ["router"]
