"""健康检查端点。"""
from __future__ import annotations

import time

from fastapi import APIRouter

from app import __version__
from app.schemas import ok

router = APIRouter(prefix="/api/public", tags=["public"])

_startup_ts = time.time()


@router.get("/health")
def health() -> dict:
    """Liveness probe;为负载均衡器 / k8s / 监控提供 UP 探针。"""
    return ok(
        data={
            "status": "UP",
            "version": __version__,
            "uptimeSec": int(time.time() - _startup_ts),
        }
    )
