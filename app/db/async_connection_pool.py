"""
# ============================================================================ #
# Dosya: async_connection_pool.py
# Yol: /Users/siyahkare/code/telegram-bot/app/db/async_connection_pool.py
# İşlev: Asyncpg tabanlı asenkron veritabanı bağlantı havuzu
#
# © 2025 SiyahKare Yazılım - Tüm Hakları Saklıdır
# ============================================================================ #
"""

import os
import asyncio
import logging
import asyncpg
from typing import Dict, List, Any, Optional, Callable, Union, Tuple
from functools import wraps
from urllib.parse import urlparse
from contextlib import asynccontextmanager
from datetime import datetime
from enum import Enum

# Log ayarları
logger = logging.getLogger(__name__)

class IsolationLevel(str, Enum):
    """Transaction izolasyon seviyeleri"""
    READ_UNCOMMITTED = "READ UNCOMMITTED"
    READ_COMMITTED = "READ COMMITTED"  # PostgreSQL varsayılanı
    REPEATABLE_READ = "REPEATABLE READ"
    SERIALIZABLE = "SERIALIZABLE"

class AsyncDbConnectionPool:
    """
    Asyncpg tabanlı asenkron PostgreSQL bağlantı havuzu

    Bu sınıf, asyncpg kütüphanesini kullanarak PostgreSQL veritabanına
    asenkron bağlantı sağlar ve bağlantı havuzu yönetimini üstlenir.
    """
    
    _instance = None
    _init_lock = asyncio.Lock()
    
    def __new__(cls, *args, **kwargs):
        """Singleton pattern için __new__ metodu."""
        if cls._instance is None:
            cls._instance = super(AsyncDbConnectionPool, cls).__new__(cls)
            # Sınıf özelliklerini başlat
            cls._instance._is_initialized = False
            cls._instance._stats = {
                "created_at": datetime.now(),
                "total_queries": 0,
                "errors": 0,
                "active_connections": 0,
                "last_error": None,
                "last_query_time": 0,
                "max_query_time": 0
            }
            cls._instance._is_closed = False
            cls._instance._pool_lock = asyncio.Lock()
            cls._instance.pool = None
        return cls._instance

    def __init__(
        self, 
        min_size: int = 5, 
        max_size: int = 20, 
        db_url: Optional[str] = None,
        connection_timeout: float = 10.0,
        statement_timeout: Optional[float] = 30.0,  # 30 saniye
        command_timeout: Optional[float] = 60.0,    # 60 saniye
        **kwargs
    ):
        """
        Bağlantı havuzunu yapılandırır
        
        Args:
            min_size: Minimum bağlantı sayısı
            max_size: Maksimum bağlantı sayısı
            db_url: Veritabanı bağlantı URL'si (None ise çevre değişkenlerinden alınır)
            connection_timeout: Bağlantı zaman aşımı (saniye)
            statement_timeout: Sorgu zaman aşımı (saniye, None ise sınırsız)
            command_timeout: Komut zaman aşımı (saniye, None ise sınırsız)
            **kwargs: Asyncpg pool oluşturma için ek parametreler
        """
        # Parametreleri kaydet
        self.min_size = min_size
        self.max_size = max_size
        self.db_url = db_url
        self.connection_timeout = connection_timeout  
        self.statement_timeout = statement_timeout
        self.command_timeout = command_timeout
        self.pool_kwargs = kwargs

    async def initialize(
        self, 
        min_size: Optional[int] = None, 
        max_size: Optional[int] = None, 
        db_url: Optional[str] = None,
        connection_timeout: Optional[float] = None,
        statement_timeout: Optional[float] = None,
        command_timeout: Optional[float] = None,
        **kwargs
    ):
        """
        Bağlantı havuzunu asenkron olarak başlatır
        
        Args:
            min_size: Minimum bağlantı sayısı
            max_size: Maksimum bağlantı sayısı
            db_url: Veritabanı bağlantı URL'si (None ise çevre değişkenlerinden alınır)
            connection_timeout: Bağlantı zaman aşımı (saniye)
            statement_timeout: Sorgu zaman aşımı (saniye, None ise sınırsız)
            command_timeout: Komut zaman aşımı (saniye, None ise sınırsız)
            **kwargs: Asyncpg pool oluşturma için ek parametreler
        """
        # Eğer instance daha önce başlatıldıysa tekrar yapılandırma
        if self._is_initialized:
            return

        # İlklendirme kilidini al - concurrent __init__ çağrılarına karşı koruma
        async with self._init_lock:
            # Double-check initialization
            if self._is_initialized:
                return
            
            # Parametreleri güncelle (eğer belirtildiyse)
            if min_size is not None:
                self.min_size = min_size
            if max_size is not None:
                self.max_size = max_size
            if db_url is not None:
                self.db_url = db_url
            if connection_timeout is not None:
                self.connection_timeout = connection_timeout
            if statement_timeout is not None:
                self.statement_timeout = statement_timeout
            if command_timeout is not None:
                self.command_timeout = command_timeout
            if kwargs:
                self.pool_kwargs.update(kwargs)
                
            # DB URL'i belirle
            self.db_url = self.db_url or os.getenv("DB_CONNECTION") or os.getenv("DATABASE_URL")
            
            if not self.db_url:
                raise ValueError("Veritabanı bağlantı URL'si belirtilmedi ve çevre değişkenlerinde bulunamadı")
            
            # DB URL'i asyncpg uyumlu formata dönüştür
            if self.db_url.startswith("postgresql://"):
                self.db_url = self.db_url.replace("postgresql://", "postgres://")
            
            # Pool ve durum
            self.pool = None
            self._is_closed = False
            self._stats = {
                "created_at": datetime.now(),
                "total_queries": 0,
                "active_connections": 0,
                "errors": 0,
                "last_error": None,
                "last_query_time": None,
                "max_query_time": 0
            }
            
            # Mutex ve semaphorlar
            self._pool_lock = asyncio.Lock()
            self._connection_semaphore = asyncio.Semaphore(self.max_size)
            
            # Havuzu başlat
            await self._initialize_pool()
            
            self._is_initialized = True
            logger.info(
                f"Asenkron DB havuzu başlatıldı - Min:{self.min_size}, Max:{self.max_size}, "
                f"Timeout:{self.connection_timeout}s, Host:{self._get_db_host()}"
            )
    
    def _get_db_host(self) -> str:
        """Veritabanı sunucu bilgisini döndürür"""
        try:
            parsed = urlparse(self.db_url)
            host = parsed.hostname
            port = parsed.port or "5432"
            db = parsed.path.lstrip('/')
            return f"{host}:{port}/{db}"
        except Exception:
            return "unknown"
    
    async def _initialize_pool(self):
        """Bağlantı havuzunu oluşturur"""
        async with self._pool_lock:
            if self.pool is not None:
                return
                
            try:
                # Pool parametrelerini son haline getir
                self.pool_kwargs.update({
                    "min_size": self.min_size,
                    "max_size": self.max_size,
                    "timeout": self.connection_timeout
                })
                
                # Bağlantı havuzunu oluştur
                self.pool = await asyncpg.create_pool(
                    dsn=self.db_url,
                    **self.pool_kwargs,
                    server_settings={
                        "application_name": "telegram_bot_v3.9",
                        "search_path": "public"
                    },
                    setup=self._setup_connection
                )
                
                # Havuz oluşturma başarısız olursa
                if self.pool is None:
                    raise RuntimeError("Bağlantı havuzu oluşturulamadı")
                    
                # Test bağlantısı
                async with self.pool.acquire() as conn:
                    version = await conn.fetchval("SELECT version()")
                    logger.info(f"PostgreSQL bağlantısı başarılı: {version}")
                
            except Exception as e:
                logger.error(f"Bağlantı havuzu oluşturulurken hata: {str(e)}")
                self._stats["errors"] += 1
                self._stats["last_error"] = str(e)
                raise
    
    async def _setup_connection(self, connection):
        """
        Yeni oluşturulan her bağlantı için çalıştırılacak kurulum fonksiyonu
        
        Args:
            connection: asyncpg bağlantı nesnesi
        """
        # Statement timeout ayarla (varsa)
        if self.statement_timeout is not None:
            await connection.execute(f"SET statement_timeout TO {int(self.statement_timeout * 1000)}")
        
        # Command timeout ayarla (varsayılan olarak açık)
        if self.command_timeout is not None:
            connection.set_type_codec(
                'json',
                encoder=lambda v: v,
                decoder=lambda v: v,
                schema='pg_catalog'
            )
    
    @asynccontextmanager
    async def acquire(self, timeout=None):
        """
        Bağlantı havuzundan bir bağlantı alır
        
        Args:
            timeout: Bağlantı almak için beklenecek maksimum süre (saniye)
            
        Yields:
            asyncpg.Connection: Veritabanı bağlantısı
        """
        if self.pool is None:
            await self._initialize_pool()
            
        # Eğer havuz kapatıldıysa hata fırlat
        if self._is_closed:
            raise RuntimeError("Bağlantı havuzu kapatıldı")
            
        # Aktif bağlantı sayısını sınırla
        try:
            # Bağlantı için semaphore al
            semaphore_timeout = timeout or self.connection_timeout
            acquired = False
            
            try:
                acquired = await asyncio.wait_for(
                    self._connection_semaphore.acquire(),
                    timeout=semaphore_timeout
                )
            except asyncio.TimeoutError:
                raise TimeoutError(f"Bağlantı havuzundan bağlantı alınamadı. Tüm bağlantılar kullanımda ({self.max_size} bağlantı).")
            
            # Bağlantıyı al
            self._stats["active_connections"] += 1
            conn = await self.pool.acquire(timeout=timeout)
            
            try:
                yield conn
            finally:
                # Bağlantıyı iade et
                await self.pool.release(conn)
                self._stats["active_connections"] -= 1
                
                # Semaphore'u serbest bırak
                if acquired:
                    self._connection_semaphore.release()
                    
        except asyncpg.PostgresError as e:
            self._stats["errors"] += 1
            self._stats["last_error"] = str(e)
            logger.error(f"Veritabanı bağlantısı alınırken hata: {str(e)}")
            raise
    
    @asynccontextmanager
    async def transaction(self, isolation_level=IsolationLevel.READ_COMMITTED):
        """
        Transaction başlatır
        
        Args:
            isolation_level: Transaction izolasyon seviyesi
            
        Yields:
            Transaction: Transaction nesnesi 
        """
        async with self.acquire() as connection:
            async with connection.transaction(isolation=isolation_level) as transaction:
                yield transaction
    
    async def execute(self, query: str, *args, timeout: Optional[float] = None) -> str:
        """
        SQL sorgusu çalıştırır
        
        Args:
            query: SQL sorgusu
            *args: Sorgu parametreleri
            timeout: Sorgu zaman aşımı (saniye)
            
        Returns:
            str: Sorgu sonucu
        """
        start_time = datetime.now()
        try:
            async with self.acquire() as connection:
                result = await connection.execute(query, *args, timeout=timeout)
                self._stats["total_queries"] += 1
                
                # İstatistikleri güncelle
                query_time = (datetime.now() - start_time).total_seconds()
                self._stats["last_query_time"] = query_time
                self._stats["max_query_time"] = max(self._stats["max_query_time"], query_time)
                
                return result
        except Exception as e:
            self._stats["errors"] += 1
            self._stats["last_error"] = str(e)
            logger.error(f"Sorgu çalıştırılırken hata: {str(e)}, Sorgu: {query}")
            raise
    
    async def fetch(self, query: str, *args, timeout: Optional[float] = None) -> List[asyncpg.Record]:
        """
        SQL sorgusu çalıştırır ve tüm sonuçları döndürür
        
        Args:
            query: SQL sorgusu
            *args: Sorgu parametreleri
            timeout: Sorgu zaman aşımı (saniye)
            
        Returns:
            List[asyncpg.Record]: Sorgu sonuçları
        """
        start_time = datetime.now()
        try:
            async with self.acquire() as connection:
                result = await connection.fetch(query, *args, timeout=timeout)
                self._stats["total_queries"] += 1
                
                # İstatistikleri güncelle
                query_time = (datetime.now() - start_time).total_seconds()
                self._stats["last_query_time"] = query_time
                self._stats["max_query_time"] = max(self._stats["max_query_time"], query_time)
                
                return result
        except Exception as e:
            self._stats["errors"] += 1
            self._stats["last_error"] = str(e)
            logger.error(f"Sorgu çalıştırılırken hata: {str(e)}, Sorgu: {query}")
            raise
    
    async def fetchrow(self, query: str, *args, timeout: Optional[float] = None) -> Optional[asyncpg.Record]:
        """
        SQL sorgusu çalıştırır ve tek satır sonuç döndürür
        
        Args:
            query: SQL sorgusu
            *args: Sorgu parametreleri
            timeout: Sorgu zaman aşımı (saniye)
            
        Returns:
            Optional[asyncpg.Record]: Sorgu sonucu veya None
        """
        start_time = datetime.now()
        try:
            async with self.acquire() as connection:
                result = await connection.fetchrow(query, *args, timeout=timeout)
                self._stats["total_queries"] += 1
                
                # İstatistikleri güncelle
                query_time = (datetime.now() - start_time).total_seconds()
                self._stats["last_query_time"] = query_time
                self._stats["max_query_time"] = max(self._stats["max_query_time"], query_time)
                
                return result
        except Exception as e:
            self._stats["errors"] += 1
            self._stats["last_error"] = str(e)
            logger.error(f"Sorgu çalıştırılırken hata: {str(e)}, Sorgu: {query}")
            raise
    
    async def fetchval(self, query: str, *args, column: int = 0, timeout: Optional[float] = None) -> Any:
        """
        SQL sorgusu çalıştırır ve tek bir değer döndürür
        
        Args:
            query: SQL sorgusu
            *args: Sorgu parametreleri
            column: Döndürülecek sütun indeksi
            timeout: Sorgu zaman aşımı (saniye)
            
        Returns:
            Any: Sorgu sonucu
        """
        start_time = datetime.now()
        try:
            async with self.acquire() as connection:
                result = await connection.fetchval(query, *args, column=column, timeout=timeout)
                self._stats["total_queries"] += 1
                
                # İstatistikleri güncelle
                query_time = (datetime.now() - start_time).total_seconds()
                self._stats["last_query_time"] = query_time
                self._stats["max_query_time"] = max(self._stats["max_query_time"], query_time)
                
                return result
        except Exception as e:
            self._stats["errors"] += 1
            self._stats["last_error"] = str(e)
            logger.error(f"Sorgu çalıştırılırken hata: {str(e)}, Sorgu: {query}")
            raise
    
    async def execute_many(self, query: str, args: List[Tuple], timeout: Optional[float] = None) -> None:
        """
        Birden çok sorgu parametreleri ile tek bir SQL sorgusu çalıştırır
        
        Args:
            query: SQL sorgusu
            args: Sorgu parametreleri listesi
            timeout: Sorgu zaman aşımı (saniye)
        """
        start_time = datetime.now()
        try:
            async with self.acquire() as connection:
                await connection.executemany(query, args, timeout=timeout)
                self._stats["total_queries"] += 1
                
                # İstatistikleri güncelle
                query_time = (datetime.now() - start_time).total_seconds()
                self._stats["last_query_time"] = query_time
                self._stats["max_query_time"] = max(self._stats["max_query_time"], query_time)
        except Exception as e:
            self._stats["errors"] += 1
            self._stats["last_error"] = str(e)
            logger.error(f"Sorgu çalıştırılırken hata: {str(e)}, Sorgu: {query}")
            raise
    
    async def get_stats(self) -> Dict[str, Any]:
        """
        Bağlantı havuzu istatistiklerini döndürür
        
        Returns:
            Dict[str, Any]: İstatistik değerleri
        """
        pool_stats = {
            "created_at": self._stats["created_at"].isoformat(),
            "total_queries": self._stats["total_queries"],
            "active_connections": self._stats["active_connections"],
            "errors": self._stats["errors"],
            "last_error": self._stats["last_error"],
            "last_query_time": self._stats["last_query_time"],
            "max_query_time": self._stats["max_query_time"]
        }
        
        # Eğer pool varsa daha fazla istatistik ekle
        if self.pool:
            pool_stats.update({
                "min_size": self.min_size,
                "max_size": self.max_size,
                "free_size": self.pool.get_size() - self.pool.get_num_busy(),
                "busy_size": self.pool.get_num_busy(),
                "total_size": self.pool.get_size()
            })
        
        return pool_stats
    
    async def ping(self) -> bool:
        """
        Veritabanı bağlantısını test eder
        
        Returns:
            bool: Bağlantı aktifse True
        """
        try:
            result = await self.fetchval("SELECT 1")
            return result == 1
        except Exception as e:
            logger.error(f"Veritabanı ping hatası: {str(e)}")
            return False
    
    async def close(self):
        """Bağlantı havuzunu kapatır"""
        if self._is_closed:
            return
            
        async with self._pool_lock:
            if self.pool:
                await self.pool.close()
                self.pool = None
                self._is_closed = True
                logger.info("Asenkron bağlantı havuzu kapatıldı")

# Singleton instance
pool = None

async def get_db_pool(
    min_size: int = 5, 
    max_size: int = 20, 
    db_url: Optional[str] = None
) -> AsyncDbConnectionPool:
    """
    Singleton bağlantı havuzu instance'ı döndürür
    
    Args:
        min_size: Minimum bağlantı sayısı
        max_size: Maksimum bağlantı sayısı
        db_url: Veritabanı bağlantı URL'si
        
    Returns:
        AsyncDbConnectionPool: Bağlantı havuzu instance'ı
    """
    global pool
    if pool is None:
        pool = AsyncDbConnectionPool()
        await pool.initialize(
            min_size=min_size,
            max_size=max_size,
            db_url=db_url
        )
    return pool

def transactional(func):
    """
    Fonksiyonu bir transaction içinde çalıştıran decorator
    
    Bu decorator, fonksiyonu bir transaction içinde çalıştırır ve
    herhangi bir hata durumunda transaction'ı geri alır.
    
    Örnek:
        @transactional
        async def add_user(pool, user_data):
            # Bu fonksiyon otomatik olarak bir transaction içinde çalışır
            await pool.execute("INSERT INTO users VALUES ($1, $2)", user_data["id"], user_data["name"])
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        # İlk parametre pool nesnesi olmalı, çünkü diğerleri 'self' parametre olabilir 
        # (bu durumda instance method demektir ve pool parametre olarak verilmeli).
        local_pool = None
        
        if len(args) > 0 and isinstance(args[0], AsyncDbConnectionPool):
            local_pool = args[0]
        elif "pool" in kwargs and isinstance(kwargs["pool"], AsyncDbConnectionPool):
            local_pool = kwargs["pool"]
        else:
            # Fonksiyon imzasını kontrol et ve uygun havuz örneğini bul
            # Bu adımda tanımlama veya çağırma zamanındaki pool parametresi kullanılır
            import inspect
            sig = inspect.signature(func)
            has_pool_param = "pool" in sig.parameters
            
            # Global instance kullan
            global pool
            if pool is None:
                pool = await get_db_pool()
            local_pool = pool
        
        async with local_pool.transaction():
            return await func(*args, **kwargs)
    
    return wrapper 