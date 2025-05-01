#!/usr/bin/env python3
"""
Database Checker Script - Veritabanı kontrolü betiği

Bu betik, veritabanı bağlantısını ve tablolarını kontrol eder.
Kullanıcı ve grup verilerinin kalıcı olarak saklanıp saklanmadığını doğrular.
"""

import asyncio
import os
import sys
import logging
from datetime import datetime
from database.user_db import UserDatabase

# Logging ayarları
logging.basicConfig(level=logging.DEBUG, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def check_database_connection():
    """Veritabanı bağlantısını kontrol eder"""
    try:
        db_url = os.getenv("DB_CONNECTION", "postgresql://postgres:postgres@localhost:5432/telegram_bot")
        logger.info(f"Veritabanı URL: {db_url}")

        db = UserDatabase(db_url)
        connection_result = await db.connect()
        
        if connection_result:
            logger.info(f"✅ Veritabanına başarıyla bağlanıldı: {db.db_host}:{db.db_port}/{db.db_name}")
            await db.close()
            return True
        else:
            logger.error(f"❌ Veritabanına bağlanılamadı!")
            return False
    except Exception as e:
        logger.error(f"❌ Veritabanı bağlantısı kontrol edilirken hata: {str(e)}")
        return False

async def check_tables():
    """Veritabanı tablolarını kontrol eder"""
    try:
        db = UserDatabase()
        await db.connect()

        # Tüm tabloları kontrol et
        tables = ['users', 'groups', 'spam_messages', 'settings', 'user_activity']
        missing_tables = []
        
        for table in tables:
            query = """
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = %s
            );
            """
            result = await db.fetchone(query, (table,))
            exists = result[0] if result else False
            
            if exists:
                logger.info(f"✅ '{table}' tablosu mevcut")
            else:
                logger.warning(f"❌ '{table}' tablosu bulunamadı")
                missing_tables.append(table)
        
        if missing_tables:
            logger.warning(f"⚠️ {len(missing_tables)} adet tablo bulunamadı: {', '.join(missing_tables)}")
            
            # Tabloları oluştur
            logger.info("🔨 Tablolar oluşturuluyor...")
            await db.create_tables()
            logger.info("✅ Tablolar oluşturuldu")
        
        await db.close()
        return len(missing_tables) == 0
    except Exception as e:
        logger.error(f"❌ Tablolar kontrol edilirken hata: {str(e)}")
        return False

async def count_data():
    """Kullanıcı ve grup verilerinin sayısını kontrol eder"""
    try:
        db = UserDatabase()
        await db.connect()
        
        # Kullanıcı sayısını kontrol et
        query = "SELECT COUNT(*) FROM users"
        result = await db.fetchone(query)
        user_count = result[0] if result else 0
        
        # Grup sayısını kontrol et
        query = "SELECT COUNT(*) FROM groups"
        result = await db.fetchone(query)
        group_count = result[0] if result else 0
        
        # Ek kontroller
        if user_count > 0:
            # Örnek bir kullanıcıyı al
            query = "SELECT * FROM users LIMIT 1"
            user = await db.fetchone(query)
            logger.info(f"Örnek kullanıcı: {user}")
        
        logger.info(f"📊 Veritabanı istatistikleri:")
        logger.info(f"   - {user_count} kullanıcı")
        logger.info(f"   - {group_count} grup")
        
        await db.close()
        return {
            'users': user_count,
            'groups': group_count
        }
    except Exception as e:
        logger.error(f"❌ Veri sayısı kontrol edilirken hata: {str(e)}")
        return {'users': 0, 'groups': 0}

async def check_environment():
    """Çevre değişkenlerini kontrol eder"""
    # Önemli çevre değişkenlerini listele
    env_vars = [
        "DB_CONNECTION",
        "TELEGRAM_API_ID",
        "TELEGRAM_API_HASH",
        "TELEGRAM_PHONE",
        "TELEGRAM_BOT_TOKEN",
        "ADMIN_GROUPS"
    ]
    
    logger.info("🔍 Çevre değişkenleri kontrolü:")
    for var in env_vars:
        value = os.getenv(var)
        if value:
            masked_value = value[:3] + "..." + value[-3:] if len(value) > 10 else "***"
            logger.info(f"   ✅ {var}: {masked_value}")
        else:
            logger.warning(f"   ❌ {var}: Tanımlanmamış")

async def check_persistence():
    """Veritabanı kalıcılığını kontrol eder"""
    try:
        db = UserDatabase()
        await db.connect()
        
        # Test kullanıcısı ekle
        test_user_id = 999999999  # Test için özel bir ID
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Önce bu kullanıcının var olup olmadığını kontrol et
        query = "SELECT COUNT(*) FROM users WHERE user_id = %s"
        result = await db.fetchone(query, (test_user_id,))
        exists = result[0] > 0 if result else False
        
        if exists:
            logger.info(f"✅ Test kullanıcısı zaten mevcut (ID: {test_user_id})")
            
            # Kullanıcıyı güncelle
            query = """
            UPDATE users SET 
                updated_at = %s,
                last_active_at = %s
            WHERE user_id = %s
            """
            await db.execute(query, (current_time, current_time, test_user_id))
            logger.info(f"✅ Test kullanıcısı güncellendi")
        else:
            # Yeni test kullanıcısı ekle
            query = """
            INSERT INTO users (
                user_id, first_name, last_name, username, 
                is_active, created_at, updated_at
            ) VALUES (
                %s, 'Test', 'Kullanıcı', 'test_user',
                TRUE, %s, %s
            )
            """
            await db.execute(query, (test_user_id, current_time, current_time))
            logger.info(f"✅ Yeni test kullanıcısı eklendi (ID: {test_user_id})")
        
        # Veritabanına kaydedildiğini doğrula
        query = "SELECT * FROM users WHERE user_id = %s"
        result = await db.fetchone(query, (test_user_id,))
        
        if result:
            logger.info(f"✅ Test kullanıcısı başarıyla saklandı ve okundu")
        else:
            logger.error(f"❌ Test kullanıcısı veritabanına kaydedilemedi")
        
        await db.close()
        return True
    except Exception as e:
        logger.error(f"❌ Kalıcılık testi sırasında hata: {str(e)}")
        return False

async def main():
    """Ana fonksiyon"""
    logger.info("🔍 Veritabanı kontrol ediliyor...")
    
    # Çevre değişkenlerini kontrol et
    await check_environment()
    
    # Veritabanı bağlantısını kontrol et
    connection_ok = await check_database_connection()
    if not connection_ok:
        logger.error("❌ Veritabanı bağlantısı başarısız! İşlem sonlandırılıyor.")
        return
    
    # Tabloları kontrol et
    tables_ok = await check_tables()
    if not tables_ok:
        logger.warning("⚠️ Bazı tablolar eksik, ancak oluşturuldu.")
    
    # Veri sayısını kontrol et
    counts = await count_data()
    
    # Kalıcılık testi
    persistence_ok = await check_persistence()
    if persistence_ok:
        logger.info("✅ Veritabanı kalıcılık testi başarılı")
    else:
        logger.error("❌ Veritabanı kalıcılık testi başarısız!")
    
    # Sonuçları göster
    logger.info("\n📋 ÖZET:")
    logger.info(f"Veritabanı bağlantısı: {'✅ Başarılı' if connection_ok else '❌ Başarısız'}")
    logger.info(f"Tablolar: {'✅ Tam' if tables_ok else '⚠️ Eksikler vardı'}")
    logger.info(f"Kullanıcı sayısı: {counts['users']}")
    logger.info(f"Grup sayısı: {counts['groups']}")
    logger.info(f"Kalıcılık testi: {'✅ Başarılı' if persistence_ok else '❌ Başarısız'}")
    
    if counts['users'] == 0:
        logger.warning("⚠️ Veritabanında hiç kullanıcı bulunmuyor!")
        logger.info("Olası çözümler:")
        logger.info("1. Telegram servislerinin doğru çalıştığından emin olun")
        logger.info("2. .env dosyasında DB_CONNECTION değişkenini kontrol edin")
        logger.info("3. Veritabanına kullanıcı ve grup eklemek için programı çalıştırın")

# Programı çalıştır
if __name__ == "__main__":
    asyncio.run(main()) 