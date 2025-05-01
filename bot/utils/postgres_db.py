import logging
import os
import psycopg2
from datetime import datetime

# Loglama yapılandırması
logger = logging.getLogger(__name__)

def setup_postgres_db():
    """PostgreSQL veritabanı bağlantısını kurar ve gerekli tabloları oluşturur."""
    try:
        # PostgreSQL bağlantı bilgileri
        host = os.getenv("DB_HOST", "localhost")
        port = os.getenv("DB_PORT", "5432")
        database = os.getenv("DB_NAME", "microbot")
        user = os.getenv("DB_USER", "postgres")
        password = os.getenv("DB_PASSWORD", "")

        # Bağlantı kur
        conn = psycopg2.connect(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password
        )
        
        # Otomatik commit etkinleştir
        conn.autocommit = True
        
        # Tabloları oluştur
        with conn.cursor() as cursor:
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username VARCHAR(255),
                first_name VARCHAR(255),
                last_name VARCHAR(255),
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
            """)
            
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_activity (
                id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(user_id),
                action_type VARCHAR(50) NOT NULL,
                action_data JSONB,
                created_at TIMESTAMP DEFAULT NOW()
            )
            """)
            
            # İndeksler oluştur
            cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_activity_timestamp ON user_activity (created_at)
            """)
            
            cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_activity_user_id ON user_activity (user_id)
            """)
        
        logger.info("PostgreSQL veritabanı başarıyla kuruldu ve tablolar oluşturuldu.")
        return conn
    except Exception as e:
        logger.error(f"Veritabanı kurulumunda hata: {str(e)}")
        return None 