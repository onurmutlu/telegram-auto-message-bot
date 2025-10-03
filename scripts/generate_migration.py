#!/usr/bin/env python3
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path

def create_migration():
    # Get the migrations directory
    migrations_dir = Path("app/db/migrations/versions")
    
    # Create a timestamp for the migration
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    
    # Create migration file name
    migration_name = f"{timestamp}_mark_existing_schema.py"
    migration_path = migrations_dir / migration_name
    
    # Generate a revision ID (first 12 chars of a UUID)
    revision = str(uuid.uuid4())[:12]
    create_date = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    
    # Create the migration content
    content = f""""""Mark existing schema as base

Revision ID: {revision}
Revises: 
Create Date: {create_date}

"""
    
    content += """from alembic import context
from sqlalchemy import engine_from_config
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine

# revision identifiers, used by Alembic.
revision = '""" + f"{revision}" + """
down_revision = None
branch_labels = None
depends_on = None


def do_run_migrations(connection: Connection) -> None:
    """Run migrations in 'online' mode."""
    context.configure(connection=connection, target_metadata=None)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = AsyncEngine(
        engine_from_config(
            context.config.get_section(context.config.config_ini_section),
            prefix="sqlalchemy.",
            future=True,
        )
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def upgrade() -> None:
    """Run upgrade migrations."""
    if context.is_offline_mode():
        print("Can't run async migrations in offline mode")
        return
    
    import asyncio
    asyncio.run(run_migrations_online())


def downgrade() -> None:
    """Run downgrade migrations."""
    if context.is_offline_mode():
        print("Can't run async migrations in offline mode")
        return
    
    import asyncio
    asyncio.run(run_migrations_online())
"""
    
    # Ensure the migrations directory exists
    migrations_dir.mkdir(parents=True, exist_ok=True)
    
    # Write the migration file
    with open(migration_path, 'w') as f:
        f.write(content)
    
    print(f"Created empty migration: {migration_path}")
    print("\nNow you can run: ALEMBIC_CONFIG=alembic.ini alembic stamp head")

if __name__ == "__main__":
    create_migration()
