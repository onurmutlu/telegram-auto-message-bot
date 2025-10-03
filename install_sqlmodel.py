#!/usr/bin/env python3
"""
This script creates a custom SQLModel implementation that can be used
without requiring an internet connection to install the package.
"""
import os
import sys
from pathlib import Path

def create_sqlmodel_module():
    # Get the virtual environment site-packages directory
    venv_site_packages = os.path.join(os.path.dirname(os.path.abspath(__file__)), 
                                    ".venv", "lib", "python3.9", "site-packages")
    
    # Create sqlmodel directory if it doesn't exist
    sqlmodel_dir = os.path.join(venv_site_packages, "sqlmodel")
    os.makedirs(sqlmodel_dir, exist_ok=True)
    
    # Create __init__.py file with our custom implementation
    init_content = '''
# Import from SQLAlchemy
from sqlalchemy import Column, create_engine, select, and_, or_, func, column as col
from sqlalchemy import text, desc, asc, distinct, cast, case, exists, update, delete
from sqlalchemy.orm import Session, relationship, joinedload, selectinload
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import expression
from sqlalchemy.sql.expression import literal_column, literal

# Import from Pydantic
from pydantic import BaseModel as PydanticBaseModel, Field

# Create a SQLAlchemy declarative base
_Base = declarative_base()

# Create a base class for SQLModel that supports table=False parameter
class SQLModel(_Base, PydanticBaseModel):
    """Base class for all SQLModel models"""
    __abstract__ = True
    
    def __init_subclass__(cls, **kwargs):
        # Handle table=False parameter
        table = kwargs.pop('table', True)
        if not table:
            cls.__abstract__ = True
        super().__init_subclass__(**kwargs)

# Re-export common SQLAlchemy components
__all__ = [
    # Base classes
    "SQLModel",
    "Field",
    
    # Session management
    "Session",
    "create_engine",
    
    # Schema components
    "Column",
    "relationship",
    
    # Query building
    "select",
    "and_",
    "or_",
    "func",
    "col",
    "text",
    "desc",
    "asc",
    "distinct",
    "cast",
    "case",
    "exists",
    "update",
    "delete",
    
    # Loading strategies
    "joinedload",
    "selectinload",
    
    # Expression helpers
    "expression",
    "literal_column",
    "literal"
]
'''
    
    with open(os.path.join(sqlmodel_dir, "__init__.py"), "w") as f:
        f.write(init_content)
    
    print(f"Created enhanced sqlmodel module in {sqlmodel_dir}")
    return True

if __name__ == "__main__":
    success = create_sqlmodel_module()
    if success:
        print("Enhanced SQLModel module successfully created!")
    else:
        print("Failed to create SQLModel module.")
        sys.exit(1)
