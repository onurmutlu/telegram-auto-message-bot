#!/usr/bin/env python3
import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

async def check_tables():
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
            # Get list of tables
            result = await conn.execute(
                text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name;
                """)
            )
            
            tables = [row[0] for row in result.all()]
            
            if tables:
                print("\nFound tables:")
                for table in tables:
                    print(f"- {table}")
                    
                    # Get table structure
                    print(f"\nStructure of {table}:")
                    columns = await conn.execute(
                        text("""
                        SELECT column_name, data_type, is_nullable, column_default
                        FROM information_schema.columns
                        WHERE table_name = :table_name
                        ORDER BY ordinal_position;
                        """),
                        {"table_name": table}
                    )
                    
                    print(f"{'Column':<30} {'Type':<20} {'Nullable':<10} {'Default'}")
                    print("-" * 70)
                    for col in columns:
                        print(f"{col[0]:<30} {col[1]:<20} {col[2]:<10} {col[3] or ''}")
                    print()
            else:
                print("No tables found in the database.")
                
    except Exception as e:
        print(f"Error: {e}")
        raise
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(check_tables())
