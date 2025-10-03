import asyncio
from logging.config import fileConfig
import os
import sys
from typing import List, Dict, Any, Union

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))

from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from alembic import context
from alembic.config import Config

# Import your models for autogenerate support
from app.db.models import Base

# This is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config: Config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.

def get_url() -> str:
    """Get the database URL from the config file."""
    return config.get_main_option("sqlalchemy.url")

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=False,  # Changed from True to False
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # Added for better offline migrations
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations in the given connection."""
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.
    """
    connectable = create_async_engine(get_url())

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    import asyncio
    try:
        asyncio.run(run_migrations_online())
    except Exception as e:
        print(f"Online migrasyon hatası: {e}")
        print("Offline moda düşülüyor...")
        run_migrations_offline()