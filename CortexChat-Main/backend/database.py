"""
backend/database.py — Asynchronous Database Orchestration.

This module is responsible for managing the connection lifecycle between the FastAPI application
and the underlying relational database (SQLite for local dev, PostgreSQL/Supabase for production).

Key Components:
  - Engine: The async SQLAlchemy engine configured with connection pooling.
  - Session Factory: `AsyncSessionLocal`, used by dependencies to yield isolated database sessions.
  - Base: The `DeclarativeBase` subclass from which all ORM models inherit.
  - Initialization: `init_db()` is called during app startup to ensure all tables are created.
"""

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine
)

from sqlalchemy.orm import DeclarativeBase

from backend.config import get_settings

settings = get_settings()

# ─────────────────────────────────────────────────────────────
# ENGINE CONFIGURATION
# ─────────────────────────────────────────────────────────────

engine_kwargs = {
    "echo": False,
    "future": True,
}

# PostgreSQL-specific optimizations
if settings.database_url.startswith("postgresql+asyncpg"):

    engine_kwargs.update({

        "pool_size": 20,

        "max_overflow": 30,

        "pool_timeout": 30,

        "pool_recycle": 1800,

        "pool_pre_ping": True,

        "execution_options": {
            "prepared_statement_cache_size": 0
        },

        "connect_args": {
            "statement_cache_size": 0
        }

    })

# ─────────────────────────────────────────────────────────────
# CREATE ENGINE
# ─────────────────────────────────────────────────────────────

engine = create_async_engine(
    settings.database_url,
    **engine_kwargs
)

# ─────────────────────────────────────────────────────────────
# SESSION FACTORY
# ─────────────────────────────────────────────────────────────

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# ─────────────────────────────────────────────────────────────
# BASE CLASS
# ─────────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    """
    Declarative base class for all ORM models.
    """
    pass

# ─────────────────────────────────────────────────────────────
# DATABASE INITIALIZATION
# ─────────────────────────────────────────────────────────────

async def init_db() -> None:
    """
    Create all database tables during application startup.
    """

    # Import models to register them with SQLAlchemy
    from backend.models.user import (
        User,
        OTPRecord,
        UserPreferences
    )

    from backend.models.chat import (
        Chat,
        Message
    )

    from backend.models.file import (
        UploadedFile
    )

    print(
        f"Initialising database..."
        f" (Discovered {len(Base.metadata.tables)} tables)"
    )

    async with engine.begin() as conn:

        await conn.run_sync(
            Base.metadata.create_all
        )

    print("Database ready.")

# ─────────────────────────────────────────────────────────────
# DATABASE DEPENDENCY
# ─────────────────────────────────────────────────────────────

async def get_db():
    """
    FastAPI dependency that provides
    an AsyncSession per request.
    """

    async with AsyncSessionLocal() as session:
        yield session