from typing import Any, Dict, List, Optional, Type, TypeVar, Union
from sqlalchemy import select, update, delete, insert, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from sqlalchemy.sql.expression import Select, Update, Delete, Insert

T = TypeVar('T')

class DatabaseUtils:
    """Utility class for common async database operations."""
    
    @staticmethod
    async def execute_query(
        session: AsyncSession,
        query: Union[Select, Update, Delete, Insert, str],
        params: Optional[Dict[str, Any]] = None,
        commit: bool = False
    ) -> Any:
        """Execute a SQL query asynchronously."""
        try:
            if isinstance(query, str):
                result = await session.execute(text(query), params or {})
            else:
                result = await session.execute(query, params or {})
                
            if commit:
                await session.commit()
                
            return result
        except Exception as e:
            await session.rollback()
            raise e
    
    @staticmethod
    async def fetch_one(
        session: AsyncSession,
        query: Union[Select, str],
        params: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Fetch a single row asynchronously."""
        result = await DatabaseUtils.execute_query(session, query, params)
        row = result.first()
        if row:
            return dict(row._mapping) if hasattr(row, '_mapping') else dict(row)
        return None
    
    @staticmethod
    async def fetch_all(
        session: AsyncSession,
        query: Union[Select, str],
        params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Fetch all rows asynchronously."""
        result = await DatabaseUtils.execute_query(session, query, params)
        rows = result.all()
        if rows and hasattr(rows[0], '_mapping'):
            return [dict(row._mapping) for row in rows]
        return [dict(row) for row in rows]
    
    @staticmethod
    async def insert(
        session: AsyncSession,
        table: Type[T],
        data: Dict[str, Any],
        commit: bool = True
    ) -> Any:
        """Insert a new record asynchronously."""
        stmt = insert(table).values(**data)
        result = await DatabaseUtils.execute_query(session, stmt, commit=commit)
        if commit:
            return result
        return result.inserted_primary_key[0] if result.inserted_primary_key else None
    
    @staticmethod
    async def update(
        session: AsyncSession,
        table: Type[T],
        where: Dict[str, Any],
        data: Dict[str, Any],
        commit: bool = True
    ) -> int:
        """Update records asynchronously."""
        stmt = update(table).where(
            *[getattr(table, k) == v for k, v in where.items()]
        ).values(**data)
        result = await DatabaseUtils.execute_query(session, stmt, commit=commit)
        return result.rowcount
    
    @staticmethod
    async def delete(
        session: AsyncSession,
        table: Type[T],
        where: Dict[str, Any],
        commit: bool = True
    ) -> int:
        """Delete records asynchronously."""
        stmt = delete(table).where(
            *[getattr(table, k) == v for k, v in where.items()]
        )
        result = await DatabaseUtils.execute_query(session, stmt, commit=commit)
        return result.rowcount
    
    @staticmethod
    async def execute_raw_sql(
        session: AsyncSession,
        sql: str,
        params: Optional[Dict[str, Any]] = None,
        commit: bool = False
    ) -> Any:
        """Execute raw SQL asynchronously."""
        return await DatabaseUtils.execute_query(session, text(sql), params, commit=commit)
