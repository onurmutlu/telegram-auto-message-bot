#!/usr/bin/env python3
import os
import sys
import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

async def reset_alembic():
    # Connection URL - make sure it matches your setup
    db_url = "postgresql+asyncpg://postgres:postgres@localhost:5432/telegram_bot"
    
    print(f"Connecting to database: {db_url}")
    
    engine = create_async_engine(
        db_url,
        echo=True,
        future=True
    )
    
    try:
        async with engine.connect() as conn:
            # Drop the alembic_version table if it exists
            await conn.execute(text("DROP TABLE IF EXISTS alembic_version CASCADE"))
            await conn.commit()
            print("Dropped alembic_version table")
            
            # Create a new alembic_version table
            await conn.execute(text("""
                CREATE TABLE alembic_version (
                    version_num VARCHAR(32) NOT NULL,
                    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
                )
            """))
            await conn.commit()
            print("Created new alembic_version table")
            
            # Get the latest migration
            migrations_dir = "app/db/migrations/versions"
            if os.path.exists(migrations_dir):
                migration_files = [f for f in os.listdir(migrations_dir) if f.endswith('.py')]
                if migration_files:
                    # Sort to get the latest migration
                    latest_migration = sorted(migration_files)[-1]
                    version_num = latest_migration.split('_')[0]
                    
                    # Insert the latest version
                    await conn.execute(
                        text("INSERT INTO alembic_version (version_num) VALUES (:version)"),
                        {"version": version_num}
                    )
                    await conn.commit()
                    print(f"Set current version to: {version_num}")
            
    except Exception as e:
        print(f"Error: {e}")
        await conn.rollback()
        raise
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(reset_alembic())
