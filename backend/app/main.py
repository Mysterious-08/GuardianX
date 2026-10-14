from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.auth import router as auth_router
from app.core.config import settings
from app.database.session import check_database_connection
from app.api.routes.device import router as device_router
from app.api.routes.dashboard import router as dashboard_router
from app.api.routes.security_events import router as security_events_router
from app.api.routes.backups import router as backups_router
from app.exceptions.handlers import register_exception_handlers
from app.services.backup_scheduler import build_backup_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    check_database_connection()
    scheduler = getattr(app.state, "backup_scheduler", None)
    if scheduler is None:
        scheduler = build_backup_scheduler()
        app.state.backup_scheduler = scheduler
    await scheduler.start()
    try:
        yield
    finally:
        await scheduler.stop()
        app.state.backup_scheduler = None


app = FastAPI(
    title=f"{settings.APP_NAME} API",
    description=f"{settings.APP_NAME} Backend API",
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Accept", "Authorization", "Content-Type"],
)

# Register centralized exception handlers for domain errors.
register_exception_handlers(app)

app.include_router(auth_router)
app.include_router(device_router)
app.include_router(dashboard_router)
app.include_router(security_events_router)
app.include_router(backups_router)


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "application": settings.APP_NAME,
        "status": "Running",
        "version": settings.APP_VERSION,
    }