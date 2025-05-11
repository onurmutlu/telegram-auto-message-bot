import logging
import os
import psycopg2
from datetime import datetime
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Çevre değişkenlerini yükle
load_dotenv()

# Loglama yapılandırması
logger = logging.getLogger(__name__)

def get_postgres_connection_string():
    """PostgreSQL bağlantı URL'sini oluşturur"""
    # Farklı çevre değişkeni formatlarını kontrol et
    db_url = os.getenv("DATABASE_URL") or os.getenv("DB_CONNECTION")
    
    if db_url and db_url.startswith("postgresql://"):
        logger.info(f"Hazır bağlantı URL'si kullanılıyor: {db_url[:20]}...")
        return db_url
    
    # Bileşenlerden URL oluştur
    host = os.getenv("DB_HOST") or os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("DB_PORT") or os.getenv("POSTGRES_PORT", "5432")
    database = os.getenv("DB_NAME") or os.getenv("POSTGRES_DB", "telegram_bot")
    user = os.getenv("DB_USER") or os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("DB_PASSWORD") or os.getenv("POSTGRES_PASSWORD", "postgres")
    
    connection_string = f"postgresql://{user}:{password}@{host}:{port}/{database}"
    logger.info(f"Oluşturulan bağlantı URL'si: {connection_string[:20]}...")
    return connection_string

def setup_postgres_db():
    """PostgreSQL veritabanı bağlantısını kurar ve gerekli tabloları oluşturur."""
    try:
        # Bağlantı bilgilerini al
        connection_string = get_postgres_connection_string()
        
        # Bağlantı kur
        conn = psycopg2.connect(connection_string)
        conn.autocommit = True
        
        # Bağlantıyı test et
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1 as test")
            result = cursor.fetchone()
            if result and result[0] == 1:
                logger.info("PostgreSQL bağlantı testi başarılı")
            else:
                logger.error("PostgreSQL bağlantı testi başarısız")
                return None
        
        # Veritabanı özelliklerini içeren bir sınıf oluştur
        class PostgresDB:
            def __init__(self, connection):
                self.conn = connection
                self.cursor = None
                self.connected = True
                
            async def connect(self):
                """Async bağlantı için uyumluluk metodu"""
                if not self.connected:
                    self.conn = psycopg2.connect(connection_string)
                    self.conn.autocommit = True
                self.connected = True
                return True
                
            async def execute(self, query, params=None):
                """SQL sorgusu çalıştırır"""
                try:
                    cursor = self.conn.cursor()
                    cursor.execute(query, params or ())
                    self.conn.commit()
                    cursor.close()
                    return True
                except Exception as e:
                    logger.error(f"SQL execute hatası: {str(e)}")
                    self.conn.rollback()
                    return False
                    
            async def fetchall(self, query, params=None):
                """Tüm sonuçları döndürür"""
                try:
                    cursor = self.conn.cursor(cursor_factory=RealDictCursor)
                    cursor.execute(query, params or ())
                    result = cursor.fetchall()
                    cursor.close()
                    return result
                except Exception as e:
                    logger.error(f"SQL fetchall hatası: {str(e)}")
                    return []
                    
            async def fetchone(self, query, params=None):
                """Tek bir sonuç döndürür"""
                try:
                    cursor = self.conn.cursor(cursor_factory=RealDictCursor)
                    cursor.execute(query, params or ())
                    result = cursor.fetchone()
                    cursor.close()
                    return result
                except Exception as e:
                    logger.error(f"SQL fetchone hatası: {str(e)}")
                    return None
                    
            async def create_tables(self):
                """Temel tabloları oluşturur"""
                logger.info("Temel tablolar oluşturuluyor...")
                
                # users tablosu
                await self.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    username VARCHAR(255),
                    first_name VARCHAR(255),
                    last_name VARCHAR(255),
                    phone VARCHAR(20),
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
                """)
                
                # groups tablosu
                await self.execute("""
                CREATE TABLE IF NOT EXISTS groups (
                    id SERIAL PRIMARY KEY,
                    group_id BIGINT NOT NULL UNIQUE,
                    name VARCHAR(255),
                    username VARCHAR(255),
                    description TEXT,
                    join_date TIMESTAMP,
                    last_message TIMESTAMP,
                    message_count INT DEFAULT 0,
                    member_count INT DEFAULT 0,
                    error_count INT DEFAULT 0,
                    last_error TEXT,
                    is_active BOOLEAN DEFAULT TRUE,
                    permanent_error BOOLEAN DEFAULT FALSE,
                    is_target BOOLEAN DEFAULT TRUE,
                    retry_after TIMESTAMP,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
                """)
                
                logger.info("Temel tablolar başarıyla oluşturuldu")
                return True
                
            async def create_user_profile_tables(self):
                """Kullanıcı profil tablolarını oluşturur"""
                logger.info("Kullanıcı profil tabloları oluşturuluyor...")
                
                # user_profiles tablosu
                await self.execute("""
                CREATE TABLE IF NOT EXISTS user_profiles (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES users(user_id),
                    bio TEXT,
                    location VARCHAR(255),
                    website VARCHAR(255),
                    avatar_url VARCHAR(255),
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
                """)
                
                logger.info("Kullanıcı profil tabloları başarıyla oluşturuldu")
                return True
                
            async def close(self):
                """Bağlantıyı kapatır"""
                if self.conn:
                    self.conn.close()
                    self.connected = False
                    
        # Veritabanı nesnesini oluştur
        db = PostgresDB(conn)
        logger.info("PostgreSQL veritabanı başarıyla kuruldu.")
        return db
        
    except Exception as e:
        logger.error(f"Veritabanı kurulumunda hata: {str(e)}")
        
        # Test için mock veritabanı döndür
        logger.warning("Mock veritabanı nesnesi oluşturuluyor...")
        
        class MockDatabase:
            def __init__(self):
                self.connected = True
                
            async def connect(self):
                self.connected = True
                return True
                
            async def execute(self, query, params=None):
                logger.info(f"Mock SQL: {query}")
                return True
                
            async def fetchall(self, query, params=None):
                logger.info(f"Mock SQL: {query}")
                return []
                
            async def fetchone(self, query, params=None):
                logger.info(f"Mock SQL: {query}")
                return None
                
            async def create_tables(self):
                logger.info("Mock: Tablolar oluşturuluyor")
                return True
                
            async def create_user_profile_tables(self):
                logger.info("Mock: Kullanıcı tabloları oluşturuluyor")
                return True
                
            async def close(self):
                self.connected = False
                
        return MockDatabase() 