"""Database connection management."""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from aiosqlite import connect
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy.orm import declarative_base

from app.config import settings

# SQLAlchemy async engine
_engine: AsyncEngine | None = None
_async_session_maker: async_sessionmaker[AsyncSession] | None = None

# Base class for models
Base = declarative_base()


async def get_engine() -> AsyncEngine:
    """Get or create the database engine."""
    global _engine, _async_session_maker

    if _engine is None:
        # Ensure data directory exists
        db_path = settings.database_url.replace("sqlite+aiosqlite:///", "")
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        _engine = create_async_engine(
            settings.database_url,
            echo=False,
            pool_pre_ping=True,
        )

        # Create session maker
        _async_session_maker = async_sessionmaker(
            _engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    return _engine


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get database session for dependency injection."""
    engine = await get_engine()
    async_session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database tables."""
    from app.database.models import Folder, File, Embedding, IndexingJob

    engine = await get_engine()

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Load sqlite-vec extension
    db_path = settings.database_url.replace("sqlite+aiosqlite:///", "")
    async with connect(db_path) as db:
        await db.enable_load_extension(True)
        # Try to load sqlite-vec (may need to be installed separately)
        try:
            await db.load_extension("vec0")
        except Exception:
            # sqlite-vec not available, will use fallback
            pass
        await db.enable_load_extension(False)


async def close_db() -> None:
    """Close database connections."""
    global _engine

    if _engine is not None:
        await _engine.dispose()
        _engine = None


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """Get database session for use in services."""
    engine = await get_engine()
    async_session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()
