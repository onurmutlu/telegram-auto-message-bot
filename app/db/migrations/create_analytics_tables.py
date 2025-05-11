#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Analitik veri tabloları için migrasyon betiği.
Bu script, analitik veri yapılarını veritabanına ekler.
"""

import os
import sys
import psycopg2
import logging
from datetime import datetime
from dotenv import load_dotenv

# Loglama yapılandırması
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("db_migration")

# .env dosyasını yükle
load_dotenv()

def create_tables():
    """Analitik tablolarını oluşturur"""
    try:
        # Veritabanı bağlantı parametreleri
        db_host = os.getenv("POSTGRES_HOST", "localhost")
        db_port = os.getenv("POSTGRES_PORT", "5432")
        db_name = os.getenv("POSTGRES_DB", "telegram_bot")
        db_user = os.getenv("POSTGRES_USER", "postgres")
        db_password = os.getenv("POSTGRES_PASSWORD", "")
        
        # Veritabanı bağlantısı
        conn = psycopg2.connect(
            host=db_host,
            port=db_port,
            dbname=db_name,
            user=db_user,
            password=db_password
        )
        
        # Otomatik commit'i kapat
        conn.autocommit = False
        
        # Cursor oluştur
        cur = conn.cursor()
        
        logger.info(f"Veritabanına bağlandı: {db_host}:{db_port}/{db_name}")

        # Users tablosunu kontrol et ve last_active sütununu ekle
        cur.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = 'users'
        );
        """)
        
        users_table_exists = cur.fetchone()[0]
        
        if users_table_exists:
            # last_active sütununu kontrol et
            cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_name = 'users' AND column_name = 'last_active'
            );
            """)
            
            last_active_exists = cur.fetchone()[0]
            
            if not last_active_exists:
                logger.info("Users tablosuna last_active sütunu ekleniyor...")
                cur.execute("""
                ALTER TABLE users 
                ADD COLUMN IF NOT EXISTS last_active TIMESTAMP DEFAULT NOW()
                """)
                logger.info("Users tablosuna last_active sütunu eklendi")
        else:
            logger.info("Users tablosu bulunamadı, oluşturuluyor...")
            cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                user_id BIGINT UNIQUE NOT NULL,
                first_name TEXT,
                last_name TEXT,
                username TEXT,
                is_bot BOOLEAN DEFAULT FALSE,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),
                last_active TIMESTAMP DEFAULT NOW()
            )
            """)
            logger.info("Users tablosu oluşturuldu")
        
        # Message effectiveness tablosunu oluştur
        logger.info("Message effectiveness tablosu oluşturuluyor...")
        cur.execute("""
        CREATE TABLE IF NOT EXISTS message_effectiveness (
            id SERIAL PRIMARY KEY,
            message_id BIGINT NOT NULL,
            group_id BIGINT NOT NULL,
            content TEXT NOT NULL,
            category VARCHAR(50) NOT NULL DEFAULT 'regular',
            sent_at TIMESTAMP NOT NULL DEFAULT NOW(),
            views INT NOT NULL DEFAULT 0,
            reactions INT NOT NULL DEFAULT 0,
            replies INT NOT NULL DEFAULT 0,
            forwards INT NOT NULL DEFAULT 0,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
        """)
        
        # DM dönüşümleri tablosunu oluştur
        logger.info("DM dönüşümleri tablosu oluşturuluyor...")
        cur.execute("""
        CREATE TABLE IF NOT EXISTS dm_conversions (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            source_message_id BIGINT,
            group_id BIGINT NOT NULL,
            conversion_type VARCHAR(50) NOT NULL DEFAULT 'direct',
            converted_at TIMESTAMP NOT NULL DEFAULT NOW(),
            is_successful BOOLEAN DEFAULT FALSE,
            message_count INT DEFAULT 0,
            updated_at TIMESTAMP DEFAULT NOW()
        )
        """)
        
        # İndeksler oluştur
        logger.info("İndeksler oluşturuluyor...")
        cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_message_effectiveness_message_id ON message_effectiveness(message_id);
        CREATE INDEX IF NOT EXISTS idx_message_effectiveness_group_id ON message_effectiveness(group_id);
        CREATE INDEX IF NOT EXISTS idx_message_effectiveness_category ON message_effectiveness(category);
        CREATE INDEX IF NOT EXISTS idx_dm_conversions_user_id ON dm_conversions(user_id);
        CREATE INDEX IF NOT EXISTS idx_dm_conversions_source_message_id ON dm_conversions(source_message_id);
        """)
        
        # Değişiklikleri kaydet
        conn.commit()
        logger.info("Veritabanı tabloları başarıyla oluşturuldu")
        
    except Exception as e:
        logger.error(f"Veritabanı işlemi sırasında hata oluştu: {str(e)}", exc_info=True)
        if 'conn' in locals():
            conn.rollback()
            logger.info("Değişiklikler geri alındı")
    finally:
        # Bağlantıyı kapat
        if 'conn' in locals():
            conn.close()
            logger.info("Veritabanı bağlantısı kapatıldı")

if __name__ == "__main__":
    create_tables() 