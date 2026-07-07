"""课件公共 API:搜索、详情、解锁。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Header, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.core.errors import BusinessError, ErrorCode
from app.core.rate_limit import limiter, rate_limit
from app.db import get_db
from app.models.courseware import AccessMode
from app.schemas import ok
from app.schemas.courseware import UnlockRequest, UnlockResponse
from app.services import access_token as token_svc
from app.services import courseware as svc
from app.services.search import search as search_service

router = APIRouter(prefix="/api/public/coursewares", tags=["public/coursewares"])

# 用法:@router.get(..., dependencies=[Depends(rate_limit("30/minute", "ip"))])


def _resolve_unlocked_token_hash(request: Request) -> Optional[str]:
    """读取当前请求的已解锁 token 哈希(由前端在 Cookie 或 header 中携带)。"""
    h = request.headers.get("X-Token-Hash")
    if h:
        return h
    return request.cookies.get("lh_token_hash")


@router.get("/search")
async def search_coursewares(
    q: str | None = Query(None, description="关键词(空则返回最新)"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),  # type: ignore[no-untyped-def]
):
    """统一搜索:LLM 语义排序 + 关键词回退,5 秒超时。

    返回 envelope `data`:`{items, source, total, page, size}`。
    source=`llm` 表示本次结果由大模型重排;`keyword` 表示纯 ILIKE。
    """
    result = await search_service(db, keyword=q or "", size=size)
    return ok(
        data={
            "items": result.items,
            "source": result.source,
            "total": result.total,
            "page": page,
            "size": size,
        }
    )


@router.get("/{courseware_id}")
def public_get_courseware(
    courseware_id: int,
    request: Request,
    db: Session = Depends(get_db),  # type: ignore[no-untyped-def]
):
    """前台课件详情。

    - OPEN:直接返回
    - RESTRICTED:校验 X-Token-Hash(命中任一绑定 token);否则 403
    """
    obj = svc.get(db, courseware_id)
    if obj.access_mode == AccessMode.RESTRICTED:
        provided_hash = _resolve_unlocked_token_hash(request)
        if not provided_hash:
            raise BusinessError(ErrorCode.COURSEWARE_ACL_LOCKED, "该课件需要令牌解锁")
        allowed_hashes = {t.value_hash for t in (obj.access_tokens or [])}
        if provided_hash not in allowed_hashes:
            raise BusinessError(ErrorCode.COURSEWARE_ACL_LOCKED, "令牌无效或已失效")
    return ok(data=svc._to_item(obj, downloadable=True))


@router.post("/{courseware_id}/unlock", status_code=status.HTTP_200_OK)
def public_unlock(
    courseware_id: int,
    payload: UnlockRequest,
    response: Response,
    db: Session = Depends(get_db),  # type: ignore[no-untyped-def]
):
    """凭 token 明文解锁单个课件。

    成功:返回 tokenHash,并将其写入 Cookie(7 天),供后续 GET 自动鉴权。
    """
    obj = svc.get(db, courseware_id)
    if obj.access_mode == AccessMode.OPEN:
        # OPEN 课件无需解锁,但也允许调用 — 返回当前课件列表的关联 token(若有)
        return ok(
            data=UnlockResponse(
                tokenHash="", coursewareIds=[obj.id]
            ).model_dump()
        )
    matched = token_svc.verify(db, payload.token)
    if not matched:
        raise BusinessError(ErrorCode.INVALID_TOKEN, "令牌无效")
    # 校验该 token 是否被此课件绑定
    allowed_ids = {t.id for t in (obj.access_tokens or [])}
    if matched.id not in allowed_ids:
        raise BusinessError(ErrorCode.INVALID_TOKEN, "此令牌无权访问该课件")

    # 找到该 token 关联的所有课件 id(并集)
    from app.models.association import courseware_access_token

    rows = (
        db.query(courseware_access_token.c.courseware_id)
        .filter(courseware_access_token.c.access_token_id == matched.id)
        .all()
    )
    courseware_ids = sorted({r[0] for r in rows})

    # 写 Cookie,供下次 GET 自动解锁
    response.set_cookie(
        key="lh_token_hash",
        value=matched.value_hash,
        max_age=7 * 24 * 3600,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return ok(
        data=UnlockResponse(
            tokenHash=matched.value_hash,
            coursewareIds=courseware_ids,
        ).model_dump()
    )


__all__ = ["router"]