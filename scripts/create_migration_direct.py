#!/usr/bin/env python3
import os
import uuid
from datetime import datetime
from pathlib import Path

def create_migration():
    # Get the migrations directory
    migrations_dir = Path("app/db/migrations/versions")
    migrations_dir.mkdir(parents=True, exist_ok=True)
    
    # Create a timestamp for the migration
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    
    # Create migration file name
    migration_name = f"{timestamp}_mark_existing_schema.py"
    migration_path = migrations_dir / migration_name
    
    # Generate a revision ID (first 12 chars of a UUID)
    revision = str(uuid.uuid4())[:12]
    create_date = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    
    # Migration content
    content = f""""""Mark existing schema as base

Revision ID: {revision}
Revises: 
Create Date: {create_date}

"""
    
    content += """from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '""" + revision + """
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # This is an empty migration to mark the existing schema as the base
    pass


def downgrade():
    # This is an empty migration to mark the existing schema as the base
    pass
"""
    
    # Write the migration file
    with open(migration_path, 'w') as f:
        f.write(content)
    
    print(f"Created empty migration: {migration_path}")
    print("\nNow you can run: ALEMBIC_CONFIG=alembic.ini alembic stamp head")

if __name__ == "__main__":
    create_migration()
