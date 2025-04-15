import asyncio
import logging
import os
import time
import sqlite3
import threading
from typing import Dict, Any, Optional, Union
import psycopg2
import psycopg2.extras
from psycopg2 import pool
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

class SqliteConnectionPool:
    """
    SQLite için bağlantı havuzu implementasyonu
    """
    def __init__(self, db_path, min_connections=1, max_connections=5):
        self.db_path = db_path
        self.min_connections = min_connections
        self.max_connections = max_connections
        self.pool = []
        self.in_use = {}
        self.lock = threading.RLock()
        self._initialize_pool()
        
    def _initialize_pool(self):
        """İlk bağlantıları oluştur"""
        for _ in range(self.min_connections):
            self._add_connection_to_pool()
            
    def _add_connection_to_pool(self):
        """Havuza yeni bağlantı ekle"""
        try:
            conn = sqlite3.connect(
                self.db_path,
                timeout=60,
                isolation_level=None,  # autocommit
                check_same_thread=False
            )
            # Performans ayarları
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=30000")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA cache_size=10000")
            conn.execute("PRAGMA temp_store=MEMORY")
            conn.row_factory = sqlite3.Row
            
            # Test sorgusu
            conn.execute("SELECT 1")
            
            self.pool.append(conn)
            logger.debug(f"SQLite havuzuna yeni bağlantı eklendi. Havuz boyutu: {len(self.pool)}")
            return conn
        except Exception as e:
            logger.error(f"SQLite bağlantısı oluşturma hatası: {str(e)}")
            return None
            
    def getconn(self):
        """Havuzdan bağlantı al"""
        with self.lock:
            if not self.pool:
                # Havuzda aktif bağlantı kalmadıysa ve maksimuma ulaşılmadıysa yeni ekle
                if len(self.in_use) < self.max_connections:
                    conn = self._add_connection_to_pool()
                    if conn:
                        self.pool.remove(conn)
                        conn_id = id(conn)
                        self.in_use[conn_id] = conn
                        return conn
                    else:
                        raise Exception("Yeni SQLite bağlantısı oluşturulamadı")
                else:
                    # Maksimum bağlantı sayısına ulaşıldı, bekle
                    for _ in range(10):  # Maksimum 5 saniye bekle
                        time.sleep(0.5)
                        if self.pool:
                            break
                    else:
                        raise Exception("Tüm SQLite bağlantıları kullanımda ve timeout aşıldı")
            
            # Havuzdan bir bağlantı al
            conn = self.pool.pop(0)
            conn_id = id(conn)
            self.in_use[conn_id] = conn
            
            # Bağlantıyı test et
            try:
                conn.execute("SELECT 1")
            except sqlite3.Error:
                # Bağlantı hatalıysa, yeni bir bağlantı oluştur
                try:
                    conn.close()
                except:
                    pass
                    
                conn = self._add_connection_to_pool()
                if not conn:
                    raise Exception("SQLite bağlantısı test edilemedi ve yeni bağlantı kurulamadı")
                
                self.pool.remove(conn)
                conn_id = id(conn)
                self.in_use[conn_id] = conn
                
            return conn
            
    def putconn(self, conn):
        """Bağlantıyı havuza geri ver"""
        if conn is None:
            return
            
        with self.lock:
            conn_id = id(conn)
            
            # Bağlantı kullanımdaysa, havuza geri koy
            if conn_id in self.in_use:
                del self.in_use[conn_id]
                
                # Havuzda çok fazla bağlantı varsa kapat
                if len(self.pool) >= self.max_connections:
                    try:
                        conn.close()
                        logger.debug("Fazla SQLite bağlantısı kapatıldı")
                    except:
                        pass
                else:
                    # Bağlantı havuza geri konmadan önce test et
                    try:
                        conn.execute("SELECT 1")
                        self.pool.append(conn)
                    except Exception as e:
                        # Hatalı bağlantıyı kapat
                        try:
                            conn.close()
                        except:
                            pass
                        logger.warning(f"Hasarlı SQLite bağlantısı havuza geri konulmadı: {e}")
                        
    def closeall(self):
        """Tüm bağlantıları kapat"""
        with self.lock:
            # Havuzdaki bağlantıları kapat
            for conn in self.pool:
                try:
                    conn.close()
                except:
                    pass
            
            # Kullanımdaki bağlantıları kapat
            for conn_id, conn in list(self.in_use.items()):
                try:
                    conn.close()
                except:
                    pass
                    
            self.pool = []
            self.in_use = {}
            logger.info("SQLite bağlantı havuzu kapatıldı")

class DatabaseConnectionManager:
    """
    Veritabanı bağlantı yöneticisi. 
    PostgreSQL veya SQLite bağlantılarını yönetir.
    """
    
    def __init__(self, connection_string: str = None, pool_size: int = 5):
        """
        Bağlantı yöneticisini başlatır.
        
        Args:
            connection_string: Bağlantı dizesi (Örn: "postgresql://user:pass@host:port/db")
            pool_size: Bağlantı havuzu boyutu
        """
        self.connection_string = connection_string or os.getenv("DB_CONNECTION", "")
        self.pool_size = pool_size
        self.connection_pool = None
        self.sqlite_pool = None
        
        # Bağlantı tipini belirle
        if "postgresql" in self.connection_string.lower():
            self.db_type = "postgresql"
        else:
            self.db_type = "sqlite"
            
        logger.info(f"Veritabanı tipi: {self.db_type}")
    
    async def initialize(self) -> bool:
        """
        Bağlantı havuzunu başlatır.
        
        Returns:
            bool: Başarılı ise True
        """
        try:
            if self.db_type == "postgresql":
                # PostgreSQL bağlantı havuzu oluştur
                self.connection_pool = psycopg2.pool.ThreadedConnectionPool(
                    minconn=1,
                    maxconn=self.pool_size,
                    dsn=self.connection_string
                )
                
                # Test bağlantısı yap
                conn = self.connection_pool.getconn()
                cursor = conn.cursor()
                cursor.execute("SELECT version();")
                version = cursor.fetchone()
                logger.info(f"PostgreSQL bağlantısı başarılı. Sürüm: {version[0]}")
                
                # Bağlantıyı havuza geri ver
                self.connection_pool.putconn(conn)
                
                return True
            else:
                # SQLite için bağlantı havuzu oluştur
                db_path = os.path.join("data", "users.db")
                self.sqlite_pool = SqliteConnectionPool(
                    db_path=db_path,
                    min_connections=1,
                    max_connections=self.pool_size
                )
                
                # Test bağlantısı
                conn = self.sqlite_pool.getconn()
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                if result and result[0] == 1:
                    logger.info(f"SQLite bağlantı havuzu başarılı. Yol: {db_path}")
                    self.sqlite_pool.putconn(conn)
                    return True
                else:
                    logger.error("SQLite test bağlantısı başarısız")
                    return False
                
        except Exception as e:
            logger.error(f"Veritabanı bağlantı havuzu başlatma hatası: {str(e)}")
            return False
    
    def get_connection(self):
        """
        Veritabanı bağlantısı alır.
        
        Returns:
            connection: PostgreSQL veya SQLite bağlantısı
        """
        if self.db_type == "postgresql":
            if not self.connection_pool:
                raise ValueError("PostgreSQL bağlantı havuzu başlatılmamış")
            return self.connection_pool.getconn()
        else:
            if not self.sqlite_pool:
                raise ValueError("SQLite bağlantı havuzu başlatılmamış")
            return self.sqlite_pool.getconn()
    
    def release_connection(self, conn):
        """
        Bağlantıyı serbest bırakır.
        
        Args:
            conn: Veritabanı bağlantısı
        """
        if self.db_type == "postgresql" and self.connection_pool:
            self.connection_pool.putconn(conn)
        elif self.db_type == "sqlite" and self.sqlite_pool:
            self.sqlite_pool.putconn(conn)
        else:
            try:
                conn.close()
            except:
                pass
    
    async def close(self):
        """Tüm bağlantıları kapatır."""
        if self.db_type == "postgresql" and self.connection_pool:
            self.connection_pool.closeall()
            logger.info("PostgreSQL bağlantı havuzu kapatıldı")
        elif self.db_type == "sqlite" and self.sqlite_pool:
            self.sqlite_pool.closeall()
            logger.info("SQLite bağlantı havuzu kapatıldı")

class Database:
    def __init__(self, connection_string):
        self.connection_string = connection_string
        self.conn = None
        self.cursor = None
        
    def connect(self):
        try:
            self.conn = psycopg2.connect(self.connection_string)
            self.conn.autocommit = False
            self.cursor = self.conn.cursor(cursor_factory=RealDictCursor)
            logger.info("PostgreSQL veritabanına bağlantı başarılı")
            return True
        except Exception as e:
            logger.error(f"Veritabanı bağlantı hatası: {str(e)}")
            return False
    
    def execute(self, query, params=None):
        try:
            self.cursor.execute(query, params or ())
            return True
        except Exception as e:
            logger.error(f"Sorgu hatası: {str(e)}")
            self.conn.rollback()
            return False
    
    def commit(self):
        try:
            self.conn.commit()
            return True
        except:
            self.conn.rollback()
            return False
    
    def close(self):
        if self.conn:
            self.conn.close()