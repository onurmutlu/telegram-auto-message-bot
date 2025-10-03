#!/usr/bin/env python3
import os
import sys
import asyncio
import subprocess
import uuid
from datetime import datetime
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

def get_migration_files():
    """Get all migration files and their revision IDs"""
    migrations_dir = Path("app/db/migrations/versions")
    migration_files = []
    
    for file in migrations_dir.glob("*.py"):
        # Read the file to extract revision ID
        content = file.read_text()
        for line in content.split('\n'):
            if line.strip().startswith("revision") and "=" in line:
                revision = line.split("=")[1].strip().strip("'\"")
                migration_files.append((file.name, revision))
                break
    
    # Sort by filename (which should have timestamps)
    migration_files.sort(key=lambda x: x[0])
    return migration_files

async def mark_existing_schema():
    print("Synchronizing database with migration files...")
    
    # Get all migration files and their revision IDs
    migration_files = get_migration_files()
    if not migration_files:
        print("Error: No migration files found")
        return
    
    print(f"Found {len(migration_files)} migration files:")
    for filename, revision in migration_files:
        print(f"  {filename}: {revision}")
    
    # Get the latest revision
    latest_file, latest_revision = migration_files[-1]
    print(f"\nLatest revision: {latest_revision} from {latest_file}")
    
    # Get database URL from alembic.ini
    db_url = None
    with open('alembic.ini', 'r') as f:
        for line in f:
            if line.strip().startswith('sqlalchemy.url ='):
                db_url = line.split('=')[1].strip()
                break
    
    if not db_url:
        print("Error: Could not find database URL in alembic.ini")
        return
    
    print(f"\nUsing database URL: {db_url}")
    
    # Create engine and connect to the database
    engine = create_async_engine(db_url)
    
    try:
        # Check if alembic_version table exists
        async with engine.connect() as conn:
            # Create alembic_version table if it doesn't exist
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS alembic_version (
                    version_num VARCHAR(32) NOT NULL, 
                    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
                )
            """))
            
            # Check if there's already a version
            result = await conn.execute(text("SELECT version_num FROM alembic_version"))
            versions = result.fetchall()
            
            if versions:
                current_version = versions[0][0]
                print(f"Current version in database: {current_version}")
                
                # Check if current version is in our migration files
                current_in_files = any(rev == current_version for _, rev in migration_files)
                
                if not current_in_files:
                    print(f"Warning: Current version {current_version} not found in migration files")
                
                # Update to the latest version
                await conn.execute(text("DELETE FROM alembic_version"))
                await conn.execute(text(f"INSERT INTO alembic_version (version_num) VALUES ('{latest_revision}')"))
                print(f"Updated database version to {latest_revision}")
            else:
                # Insert the latest version
                await conn.execute(text(f"INSERT INTO alembic_version (version_num) VALUES ('{latest_revision}')"))
                print(f"Set database version to {latest_revision}")
            
            await conn.commit()
        
        print("\nSuccessfully synchronized database with migration files!")
        print("You can now run migrations normally.")
        
        # Test if alembic commands work now
        try:
            print("\nTesting alembic current command:")
            result = subprocess.run(
                "ALEMBIC_CONFIG=alembic.ini alembic current",
                shell=True,
                capture_output=True,
                text=True
            )
            print(result.stdout)
            if result.returncode != 0:
                print(f"Warning: alembic current command failed with error:\n{result.stderr}")
        except Exception as e:
            print(f"Error testing alembic command: {e}")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(mark_existing_schema())