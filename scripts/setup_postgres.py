#!/usr/bin/env python3
import os
import sys
import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, AsyncEngine
from sqlalchemy.orm import sessionmaker

# Get database URL from environment or use default
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/postgres"
)

async def setup_database():
    """Create database and extensions if they don't exist."""
    # Ensure we're using asyncpg in the connection URL
    db_url = DATABASE_URL
    if "postgresql://" in db_url and "+asyncpg" not in db_url:
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    
    # Connect to the default 'postgres' database
    temp_engine: AsyncEngine = create_async_engine(
        db_url.rsplit("/", 1)[0] + "/postgres",
        echo=True,
        future=True,
        connect_args={"server_settings": {"application_name": "setup_script"}}
    )
    
    # Extract database name from URL
    db_name = db_url.split("/")[-1].split("?")[0]
    if db_name == "postgres":
        # If we're using the default postgres database, use the one from the URL
        db_name = DATABASE_URL.split("/")[-1].split("?")[0]
    
    try:
        # Check if database exists
        async with temp_engine.connect() as conn:
            result = await conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :dbname"),
                {"dbname": db_name}
            )
            db_exists = result.scalar()
            
            if not db_exists:
                # Create the database
                await conn.execute(text(f"CREATE DATABASE {db_name}"))
                await conn.commit()
                print(f"Created database: {db_name}")
        
        # Now connect to the new database to create extensions
        db_engine = create_async_engine(
            db_url.rsplit("/", 1)[0] + f"/{db_name}",
            echo=True,
            future=True,
            connect_args={"server_settings": {"application_name": "setup_script"}}
        )
        
        async with db_engine.connect() as conn:
            # Create necessary extensions
            extensions = ["uuid-ossp", "pgcrypto"]
            for ext in extensions:
                try:
                    await conn.execute(text(f"CREATE EXTENSION IF NOT EXISTS \"{ext}\";"))
                    await conn.commit()
                    print(f"Created extension: {ext}")
                except Exception as e:
                    print(f"Error creating extension {ext}: {e}")
                    await conn.rollback()
        
        print("Database setup completed successfully!")
        
    except Exception as e:
        print(f"Error during database setup: {e}")
        raise
    finally:
        # Ensure engines are properly closed
        if 'db_engine' in locals():
            await db_engine.dispose()
        await temp_engine.dispose()

if __name__ == "__main__":
    asyncio.run(setup_database())
