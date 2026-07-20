import logging
from collections.abc import Generator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

logger = logging.getLogger(__name__)

engine = create_engine(
    settings.DATABASE_URL,
    future=True,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,
    future=True,
)


def check_database_connection() -> None:
    """Perform a lightweight connectivity check against the configured database."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        logger.info("Database connectivity check succeeded.")
    except SQLAlchemyError as exc:
        logger.exception("Database connectivity check failed.")
        raise RuntimeError("Database startup check failed.") from exc


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


DBSessionDep = Annotated[Session, Depends(get_db)]
