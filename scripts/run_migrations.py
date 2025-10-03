#!/usr/bin/env python3
import asyncio
import os
from alembic.config import Config
from alembic import command

def run_migrations():
    # Get the directory containing this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # Get the project root directory
    project_root = os.path.abspath(os.path.join(script_dir, '..'))
    
    # Set up Alembic config
    alembic_cfg = Config(os.path.join(project_root, "alembic.ini"))
    
    # Ensure the script directory is in the Python path
    import sys
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    
    print("Running database migrations...")
    
    # Run the migrations
    command.upgrade(alembic_cfg, "head")
    
    print("Migrations completed successfully!")

if __name__ == "__main__":
    run_migrations()
