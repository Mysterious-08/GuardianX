from fastapi import FastAPI

from app.core.config import settings

app = FastAPI(
    title=f"{settings.APP_NAME} API",
    description=f"{settings.APP_NAME} Backend API",
    version=settings.APP_VERSION,
)


@app.get("/")
async def root():
    return {
        "application": settings.APP_NAME,
        "status": "Running",
        "version": settings.APP_VERSION,
    }