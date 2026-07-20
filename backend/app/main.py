from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes.auth import router as auth_router
from app.core.config import settings
from app.database.session import check_database_connection


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    check_database_connection()
    yield


app = FastAPI(
    title=f"{settings.APP_NAME} API",
    description=f"{settings.APP_NAME} Backend API",
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.include_router(auth_router)


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "application": settings.APP_NAME,
        "status": "Running",
        "version": settings.APP_VERSION,
    }