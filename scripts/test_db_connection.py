#!/usr/bin/env python3
import asyncio
import os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

async def test_connection():
    # Get database URL from environment or use default
    db_url = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/telegram_bot"
    )
    
    print(f"Connecting to database: {db_url}")
    
    # Create async engine
    engine = create_async_engine(
        db_url,
        echo=True,
        future=True,
        connect_args={"server_settings": {"application_name": "test_connection"}}
    )
    
    try:
        # Test connection
        async with engine.connect() as conn:
            print("Connection successful!")
            
            # Test query
            result = await conn.execute(text("SELECT version()"))
            version = result.scalar()
            print(f"PostgreSQL version: {version}")
            
            # Test extensions
            result = await conn.execute(
                text("SELECT extname FROM pg_extension WHERE extname IN ('uuid-ossp', 'pgcrypto')")
            )
            extensions = [row[0] for row in result.all()]
            print(f"Installed extensions: {', '.join(extensions) if extensions else 'None'}")
            
    except Exception as e:
        print(f"Error: {e}")
        raise
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(test_connection())
