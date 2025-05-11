#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
# ============================================================================ #
# Dosya: test_postgres.py
# Yol: /Users/siyahkare/code/telegram-bot/test_postgres.py
# İşlev: PostgreSQL bağlantısını test etmek için basit betik
# ============================================================================ #
"""

import os
import sys
import logging
import asyncio
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Çevre değişkenlerini yükle
load_dotenv()

# Logging yapılandırması
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_connection_string():
    """PostgreSQL bağlantı URL'sini döndürür"""
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

def test_pg_connection():
    """PostgreSQL bağlantısını test eder"""
    try:
        connection_string = get_connection_string()
        logger.info(f"PostgreSQL bağlantısı test ediliyor...")
        
        # Bağlantı parametrelerini ayrıştır
        db_params = {}
        if "postgresql://" in connection_string:
            # URL formatı: postgresql://user:password@host:port/dbname
            url_parts = connection_string.replace("postgresql://", "").split("@")
            user_pass = url_parts[0].split(":")
            host_port_db = url_parts[1].split("/")
            host_port = host_port_db[0].split(":")
            
            db_params["user"] = user_pass[0]
            db_params["password"] = user_pass[1] if len(user_pass) > 1 else ""
            db_params["host"] = host_port[0]
            db_params["port"] = host_port[1] if len(host_port) > 1 else "5432"
            db_params["dbname"] = host_port_db[1]
        else:
            logger.error(f"Geçersiz PostgreSQL bağlantı URL'si: {connection_string}")
            return False
        
        # Parametreleri göster (şifre hariç)
        safe_params = {k: v for k, v in db_params.items() if k != 'password'}
        logger.info(f"Bağlantı parametreleri: {safe_params}")
        
        # Bağlantı kur
        conn = psycopg2.connect(**db_params)
        
        # Bağlantıyı test et
        with conn.cursor() as cursor:
            cursor.execute("SELECT version()")
            version = cursor.fetchone()[0]
            logger.info(f"✅ PostgreSQL bağlantısı başarılı: {version}")
            
            # Mevcut tabloları listele
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            """)
            tables = [row[0] for row in cursor.fetchall()]
            
            if tables:
                logger.info(f"Mevcut tablolar: {', '.join(tables)}")
            else:
                logger.warning("Veritabanında tablo bulunamadı")
                
            # Users tablosunu oluştur (eğer yoksa)
            logger.info("Users tablosunu kontrol ediyorum...")
            if 'users' not in tables:
                cursor.execute("""
                CREATE TABLE users (
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
                conn.commit()
                logger.info("✅ Users tablosu oluşturuldu")
            else:
                logger.info("✅ Users tablosu zaten mevcut")
                
            # Groups tablosunu oluştur (eğer yoksa)
            logger.info("Groups tablosunu kontrol ediyorum...")
            if 'groups' not in tables:
                cursor.execute("""
                CREATE TABLE groups (
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
                conn.commit()
                logger.info("✅ Groups tablosu oluşturuldu")
            else:
                logger.info("✅ Groups tablosu zaten mevcut")
        
        conn.close()
        logger.info("Bağlantı kapatıldı")
        return True
        
    except Exception as e:
        logger.error(f"❌ PostgreSQL bağlantı hatası: {str(e)}")
        return False

def main():
    """Ana fonksiyon"""
    try:
        success = test_pg_connection()
        if success:
            logger.info("PostgreSQL test başarılı!")
            sys.exit(0)
        else:
            logger.error("PostgreSQL test başarısız!")
            sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Test kullanıcı tarafından kesildi")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Test çalıştırılırken hata: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 