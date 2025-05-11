from logging.config import fileConfig
import os
import sys

# Ana dizini sys.path'e ekle
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))

from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context
from app.db.models import Base
from sqlalchemy import create_engine

# Alembic ayarları
config = context.config
fileConfig(config.config_file_name)
target_metadata = Base.metadata

# Fake URL for dry-run
config.set_main_option("sqlalchemy.url", "postgresql://postgres:postgres@localhost/telegram_bot")

def run_migrations_offline() -> None:
    """
    Bağlantısız migrasyon çalıştırır.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Canlı veritabanı bağlantısı ile migrasyon çalıştırır.
    """
    try:
        connectable = engine_from_config(
            config.get_section(config.config_ini_section),
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
        )

        with connectable.connect() as connection:
            context.configure(
                connection=connection, 
                target_metadata=target_metadata,
                compare_type=True,
                compare_server_default=True,
            )

            with context.begin_transaction():
                context.run_migrations()
    except Exception as e:
        print(f"Online migrasyon hatası: {e}")
        print("Offline moda düşülüyor...")
        run_migrations_offline()


if context.is_offline_mode():
    run_migrations_offline()
else:
    try:
        run_migrations_online()
    except Exception:
        run_migrations_offline() 