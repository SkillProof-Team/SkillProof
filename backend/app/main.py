import logging
import os
import sqlite3
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .api_auth import router as auth_router
from .api_catalog import load_catalog, router as catalog_router
from .config import Settings
from .db import initialize
from .reports import router as reports_router
from .request_guard import RequestGuard

LOGGER = logging.getLogger("skillproof")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        initialize(settings)
        app.state.catalog = load_catalog(settings.content_dir)
        yield

    app = FastAPI(
        title=os.getenv("APP_NAME", "SkillProof"),
        version="0.1.0-alpha",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.add_middleware(RequestGuard, settings=settings)

    @app.exception_handler(RequestValidationError)
    async def invalid_input(request: Request, exc: RequestValidationError):
        errors = [
            {"field": ".".join(map(str, error["loc"])), "message": error["msg"]}
            for error in exc.errors()
        ]
        # Do not serialize Pydantic's input or context: either can contain secrets.
        return JSONResponse(
            {"detail": {"message": "输入内容不符合要求", "errors": errors}}, status_code=422
        )

    @app.exception_handler(sqlite3.OperationalError)
    async def database_error(request: Request, exc: sqlite3.OperationalError):
        LOGGER.error("Database operation failed: %s", type(exc).__name__)
        return JSONResponse({"detail": "数据服务暂时不可用，请稍后重试"}, status_code=503)

    @app.exception_handler(sqlite3.IntegrityError)
    async def conflicting_write(request: Request, exc: sqlite3.IntegrityError):
        return JSONResponse({"detail": "数据状态已变化，请刷新后重试"}, status_code=409)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"Status": "ok"}

    app.include_router(auth_router)
    app.include_router(catalog_router)
    app.include_router(reports_router)
    return app


app = create_app()
