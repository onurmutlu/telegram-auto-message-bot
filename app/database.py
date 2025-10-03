from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, AsyncEngine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from typing import AsyncGenerator

from .config import config

# Convert postgresql:// to postgresql+asyncpg://
def get_async_db_url() -> str:
    db_url = config.DATABASE_URL
    if db_url.startswith('postgresql://'):
        return db_url.replace('postgresql://', 'postgresql+asyncpg://', 1)
    return db_url

SQLALCHEMY_DATABASE_URL = get_async_db_url()

# Create async engine
engine: AsyncEngine = create_async_engine(
    SQLALCHEMY_DATABASE_URL,
    echo=True,  # Set to False in production
    future=True,
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_size=20,
    max_overflow=10,
    pool_timeout=30
)

# Create async session factory
async_session_factory = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

Base = declarative_base()

# Dependency to get DB session
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get an async database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
