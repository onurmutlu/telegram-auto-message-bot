"""
Database CLI komutları
"""
import logging
import sys
import os
from pathlib import Path
import asyncio

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import get_session

logger = logging.getLogger(__name__)

async def fix_schema():
    """Veritabanı şema sorunlarını düzeltir"""
    try:
        db = next(get_session())
        logger.info("Veritabanı şema düzeltme işlemi başlatılıyor...")
        
        # Tablo varlık kontrolleri ve gerekli alan eklemeleri
        
        # Users tablosuna last_activity_at alanını ekleyelim
        try:
            db.execute(text("""
                ALTER TABLE users 
                ADD COLUMN IF NOT EXISTS last_activity_at TIMESTAMP DEFAULT NOW();
            """))
            db.commit()
            logger.info("users tablosuna last_activity_at alanı eklendi.")
        except SQLAlchemyError as e:
            logger.error(f"users tablosuna last_activity_at alanı eklenirken hata: {e}")
            db.rollback()
        
        # messages tablosuna type alanını ekleyelim
        try:
            db.execute(text("""
                ALTER TABLE messages 
                ADD COLUMN IF NOT EXISTS type VARCHAR(50) DEFAULT 'text';
            """))
            db.commit()
            logger.info("messages tablosuna type alanı eklendi.")
        except SQLAlchemyError as e:
            logger.error(f"messages tablosuna type alanı eklenirken hata: {e}")
            db.rollback()
        
        # message_templates tablosunda engagement_rate alanını kontrol edelim
        try:
            db.execute(text("""
                ALTER TABLE message_templates 
                ADD COLUMN IF NOT EXISTS engagement_rate FLOAT DEFAULT 0.5;
            """))
            db.commit()
            logger.info("message_templates tablosuna engagement_rate alanı eklendi.")
        except SQLAlchemyError as e:
            logger.error(f"message_templates tablosuna engagement_rate alanı eklenirken hata: {e}")
            db.rollback()
        
        # Groups tablosunun yapısını kontrol et
        try:
            # Tablo sütunlarını kontrol et
            columns_query = text("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'groups';
            """)
            
            result = db.execute(columns_query)
            columns = result.fetchall()
            
            logger.info("Groups tablosu sütunları:")
            for column in columns:
                logger.info(f"  - {column.column_name} ({column.data_type})")
            
            # Name sütununu kontrol et ve gerekirse ekle
            name_exists = any(col.column_name == 'name' for col in columns)
            if not name_exists:
                # Grup adı olabilecek title veya name benzeri bir sütun var mı kontrol et
                title_exists = any(col.column_name == 'title' for col in columns)
                group_name_exists = any(col.column_name == 'group_name' for col in columns)
                
                if title_exists:
                    # title -> name adına takma ad ekle
                    db.execute(text("""
                        ALTER TABLE groups 
                        ADD COLUMN IF NOT EXISTS name VARCHAR(255);
                        
                        UPDATE groups SET name = title WHERE name IS NULL;
                    """))
                    db.commit()
                    logger.info("groups tablosuna name sütunu title verisinden eklendi.")
                elif group_name_exists:
                    # group_name -> name adına takma ad ekle
                    db.execute(text("""
                        ALTER TABLE groups 
                        ADD COLUMN IF NOT EXISTS name VARCHAR(255);
                        
                        UPDATE groups SET name = group_name WHERE name IS NULL;
                    """))
                    db.commit()
                    logger.info("groups tablosuna name sütunu group_name verisinden eklendi.")
                else:
                    # name sütunu ekle
                    db.execute(text("""
                        ALTER TABLE groups 
                        ADD COLUMN IF NOT EXISTS name VARCHAR(255) DEFAULT 'Adsız Grup';
                    """))
                    db.commit()
                    logger.info("groups tablosuna name sütunu eklendi.")
        except SQLAlchemyError as e:
            logger.error(f"groups tablosu kontrolü sırasında hata: {e}")
            db.rollback()
        
        logger.info("Şema düzeltme işlemi tamamlandı.")
        return True
    except Exception as e:
        logger.error(f"Şema düzeltme işlemi sırasında hata: {e}")
        return False

def run_fix_schema():
    """CLI için şema düzeltme çalıştırıcı"""
    logger.info("Veritabanı şema düzeltme işlemi başlatılıyor...")
    result = asyncio.run(fix_schema())
    if result:
        logger.info("Veritabanı şema düzeltme işlemi başarıyla tamamlandı.")
    else:
        logger.error("Veritabanı şema düzeltme işlemi başarısız oldu.")
    return result 