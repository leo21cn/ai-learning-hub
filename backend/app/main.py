"""FastAPI 应用入口:装配中间件、路由、错误处理、CORS。"""
from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from app import __version__
from app.api import auth as api_auth
from app.api.admin import (
    access_tokens,
    access_token_usage,
    categories,
    coursewares,
    materials,
    tags,
)
from app.api.public import access_sessions as public_access_sessions
from app.api.public import coursewares as public_coursewares
from app.api.public import health as public_health
from app.api.public import materials as public_materials
from app.core.config import get_settings
from app.core.errors import BusinessError
from app.core.rate_limit import limiter
from app.schemas import envelope_or_business, fail

_settings = get_settings()
logging.basicConfig(
    level=_settings.log_level,
    format="%(asctime)s [%(levelname)s] %(name)s :: %(message)s",
)
logger = logging.getLogger("lh.app")


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            yield
        finally:
            pass

    app = FastAPI(
        title="Learning Hub API",
        version=__version__,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_settings.cors_origins_list or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-Id"],
    )

    # SlowAPI 异常处理
    app.state.limiter = limiter

    @app.middleware("http")
    async def add_request_id(request: Request, call_next):  # type: ignore[no-untyped-def]
        rid = request.headers.get("X-Request-Id") or f"req-{uuid.uuid4().hex[:12]}"
        request.state.request_id = rid
        response = await call_next(request)
        response.headers["X-Request-Id"] = rid
        return response

    @app.exception_handler(BusinessError)
    async def business_error_handler(request: Request, exc: BusinessError):  # type: ignore[no-untyped-def]
        rid = getattr(request.state, "request_id", None)
        body = envelope_or_business(exc, request_id=rid)
        return JSONResponse(status_code=exc.status_code, content=body, headers={"X-Request-Id": rid or ""})

    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(request: Request, exc: RateLimitExceeded):  # type: ignore[no-untyped-def]
        rid = getattr(request.state, "request_id", None)
        body = fail("rate_limited", "操作过于频繁，请稍后再试")
        body["requestId"] = rid
        return JSONResponse(status_code=429, content=body, headers={"X-Request-Id": rid or ""})

    # 路由注册
    app.include_router(public_health.router)
    app.include_router(public_coursewares.router)
    app.include_router(public_materials.router)
    app.include_router(public_access_sessions.router)
    app.include_router(api_auth.router)
    app.include_router(categories.router)
    app.include_router(tags.router)
    app.include_router(materials.router)
    app.include_router(coursewares.router)
    app.include_router(access_tokens.router)
    app.include_router(access_token_usage.router)

    @app.get("/")
    def root():  # type: ignore[no-untyped-def]
        return {
            "service": "learning-hub",
            "version": __version__,
            "docs": "/api/docs",
        }

    return app


app = create_app()
