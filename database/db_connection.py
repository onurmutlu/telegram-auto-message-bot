#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
PostgreSQL veritabanı bağlantı ve connection pooling yönetimi
"""
import os
import logging
import asyncio
import psycopg2
import psycopg2.pool
import psycopg2.extras
from functools import wraps
from typing import Any, Optional, Tuple, List, Dict, Callable
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool
from contextlib import contextmanager

from database.setup_db import get_db_url

# Log ayarları
logger = logging.getLogger(__name__)

class DatabaseConnectionPool:
    """
    PostgreSQL bağlantı havuzu yöneticisi
    Singleton pattern ile tek bir bağlantı havuzu oluşturur
    """
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(DatabaseConnectionPool, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, min_connections=2, max_connections=10, db_url=None):
        """
        Bağlantı havuzunu başlatır
        
        Args:
            min_connections: Minimum bağlantı sayısı
            max_connections: Maksimum bağlantı sayısı
            db_url: Veritabanı bağlantı URL'si (None ise çevre değişkenlerinden oluşturulur)
        """
        if self._initialized:
            return
            
        self.db_url = db_url or get_db_url()
        self.min_connections = min_connections
        self.max_connections = max_connections
        self.connection_pool = None
        self.engine = None
        self.async_engine = None
        self.SessionLocal = None
        self.AsyncSessionLocal = None
        self._lock = asyncio.Lock()
        self._initialized = True
        
        # Havuzu başlat
        self._initialize_pool()
        
        logger.info(f"Veritabanı bağlantı havuzu başlatıldı. Min:{min_connections}, Max:{max_connections}")
    
    def _initialize_pool(self):
        """
        Bağlantı havuzunu başlatır ve SQLAlchemy engine'i oluşturur
        """
        try:
            # PSQLAlchemy bağlantı havuzu
            self.engine = create_engine(
                self.db_url,
                poolclass=QueuePool,
                pool_size=self.min_connections,
                max_overflow=self.max_connections - self.min_connections,
                pool_timeout=30,
                pool_recycle=1800,  # 30 dakikada bir bağlantıları yenile
                pool_pre_ping=True  # Bağlantıdan önce ping gönder (sağlık kontrolü)
            )
            
            # psycopg2 bağlantı havuzu (düşük seviyeli işlemler için)
            db_params = {}
            # URL'den parametreleri ayıkla
            if "postgresql://" in self.db_url:
                # URL formatı: postgresql://user:password@host:port/dbname
                url_parts = self.db_url.replace("postgresql://", "").split("@")
                user_pass = url_parts[0].split(":")
                host_port_db = url_parts[1].split("/")
                host_port = host_port_db[0].split(":")
                
                db_params["user"] = user_pass[0]
                db_params["password"] = user_pass[1] if len(user_pass) > 1 else ""
                db_params["host"] = host_port[0]
                db_params["port"] = host_port[1] if len(host_port) > 1 else "5432"
                db_params["dbname"] = host_port_db[1]
            else:
                # Çevre değişkenlerini kullan
                db_params["user"] = os.getenv("DB_USER", "postgres")
                db_params["password"] = os.getenv("DB_PASSWORD", "postgres")
                db_params["host"] = os.getenv("DB_HOST", "localhost")
                db_params["port"] = os.getenv("DB_PORT", "5432")
                db_params["dbname"] = os.getenv("DB_NAME", "telegram_bot")
            
            # Threading uyumlu bağlantı havuzu oluştur
            self.connection_pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=self.min_connections,
                maxconn=self.max_connections,
                **db_params
            )
            
            # Asenkron SQLAlchemy engine
            async_url = self.db_url.replace("postgresql://", "postgresql+asyncpg://")
            self.async_engine = create_async_engine(
                async_url,
                pool_size=self.min_connections,
                max_overflow=self.max_connections - self.min_connections,
                pool_timeout=30,
                pool_recycle=1800,
                pool_pre_ping=True
            )
            
            # Session oluşturucular
            self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
            self.AsyncSessionLocal = sessionmaker(
                class_=AsyncSession, 
                expire_on_commit=False, 
                autocommit=False, 
                autoflush=False, 
                bind=self.async_engine
            )
            
            logger.info("Veritabanı bağlantı havuzu ve engine başarıyla oluşturuldu")
            
        except Exception as e:
            logger.error(f"Bağlantı havuzu oluşturulurken hata: {str(e)}")
            raise
    
    @contextmanager
    def get_connection(self):
        """
        Bağlantı havuzundan bir bağlantı alır ve işlem bitince iade eder
        """
        connection = None
        try:
            connection = self.connection_pool.getconn()
            connection.autocommit = False
            yield connection
        except Exception as e:
            if connection:
                connection.rollback()
            logger.error(f"Veritabanı bağlantısı sırasında hata: {str(e)}")
            raise
        finally:
            if connection:
                self.connection_pool.putconn(connection)
    
    @contextmanager
    def get_cursor(self, cursor_factory=psycopg2.extras.DictCursor):
        """
        Bağlantı havuzundan bir cursor alır ve işlem bitince bağlantıyı iade eder
        """
        with self.get_connection() as connection:
            cursor = connection.cursor(cursor_factory=cursor_factory)
            try:
                yield cursor
                connection.commit()
            except Exception as e:
                connection.rollback()
                logger.error(f"Veritabanı işlemi sırasında hata: {str(e)}")
                raise
            finally:
                cursor.close()
    
    @contextmanager
    def get_session(self):
        """
        SQLAlchemy session oluşturur
        """
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Session işlemi sırasında hata: {str(e)}")
            raise
        finally:
            session.close()
    
    async def get_async_session(self):
        """
        Asenkron SQLAlchemy session oluşturur
        """
        async with self.AsyncSessionLocal() as session:
            return session
    
    def execute(self, query, params=None, fetchone=False, fetchall=False):
        """
        SQL sorgusu çalıştırır
        
        Args:
            query: SQL sorgusu
            params: Sorgu parametreleri
            fetchone: Tek sonuç döndür
            fetchall: Tüm sonuçları döndür
            
        Returns:
            Sorgu sonucu veya etkilenen satır sayısı
        """
        with self.get_cursor() as cursor:
            cursor.execute(query, params or ())
            
            if fetchone:
                return cursor.fetchone()
            elif fetchall:
                return cursor.fetchall()
            else:
                return cursor.rowcount
    
    async def execute_async(self, query, params=None, fetchone=False, fetchall=False):
        """
        Asenkron SQL sorgusu çalıştırır
        
        Args:
            query: SQL sorgusu
            params: Sorgu parametreleri
            fetchone: Tek sonuç döndür
            fetchall: Tüm sonuçları döndür
            
        Returns:
            Sorgu sonucu veya etkilenen satır sayısı
        """
        async with self._lock:
            async with self.get_async_session() as session:
                result = await session.execute(query, params or {})
                await session.commit()
                
                if fetchone:
                    return result.fetchone()
                elif fetchall:
                    return result.fetchall()
                else:
                    return result.rowcount
    
    def close(self):
        """
        Bağlantı havuzunu kapatır
        """
        if self.connection_pool:
            self.connection_pool.closeall()
            logger.info("Veritabanı bağlantı havuzu kapatıldı")
            
        if self.engine:
            self.engine.dispose()
            logger.info("SQLAlchemy engine kapatıldı")
            
        self._initialized = False
        DatabaseConnectionPool._instance = None

# Transaction decorator
def transactional(func):
    """
    İşlemi transaction içinde çalıştıran decorator
    """
    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        async with self._lock:
            async with self.get_async_session() as session:
                async with session.begin():
                    return await func(self, session, *args, **kwargs)
    return wrapper

# Bağlantı havuzu için lazy singleton
_pool = None

def get_db_pool(min_connections=2, max_connections=10):
    """
    Global bağlantı havuzunu döndürür, yoksa oluşturur
    """
    global _pool
    if _pool is None:
        _pool = DatabaseConnectionPool(min_connections, max_connections)
    return _pool