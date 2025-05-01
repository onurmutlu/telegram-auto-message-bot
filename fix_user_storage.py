#!/usr/bin/env python3
"""
Fix User Storage Script - Kullanıcı Depolama Düzeltme Betiği

Bu betik, veritabanı şemasını kontrol eder ve kullanıcı depolama sorunlarını düzeltir.
Eksik sütunları ekler ve test verilerini oluşturur.
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

async def check_users_table():
    """Users tablosunu kontrol eder ve eksik sütunları ekler"""
    db = UserDatabase()
    await db.connect()
    
    try:
        # Önce sütunları al
        query = """
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'users' 
        AND table_schema = 'public'
        """
        
        results = await db.fetchall(query)
        
        if not results:
            logger.error("Users tablosu bulunamadı veya sütun bilgileri alınamadı!")
            return False
        
        # Mevcut sütunları düzenli bir biçimde göster
        logger.info("Mevcut sütunlar:")
        columns = {}
        for row in results:
            # Sonuç tipini kontrol et ve doğru şekilde erişim sağla
            if isinstance(row, tuple):
                column_name = row[0]  # Tuple indeksi ile erişim
                data_type = row[1]
            elif isinstance(row, dict):
                column_name = row.get('column_name')  # Dictionary key ile erişim
                data_type = row.get('data_type')
            else:
                logger.warning(f"Beklenmeyen veri tipi: {type(row)}")
                continue
                
            if column_name and data_type:
                columns[column_name] = data_type
                logger.info(f"  - {column_name}: {data_type}")
        
        # Gerekli sütunlar ve tipleri
        required_columns = {
            'user_id': 'bigint',
            'first_name': 'text',
            'last_name': 'text',
            'username': 'text',
            'is_active': 'boolean',
            'is_bot': 'boolean',
            'created_at': 'timestamp',
            'updated_at': 'timestamp',
            'last_active_at': 'timestamp'
        }
        
        # Eksik sütunları tespit et
        missing_columns = {}
        for col_name, col_type in required_columns.items():
            if col_name not in columns:
                missing_columns[col_name] = col_type
                logger.warning(f"Eksik sütun: {col_name} ({col_type})")
        
        # Eksik sütunları ekle
        if missing_columns:
            logger.info(f"{len(missing_columns)} eksik sütun bulundu, ekleniyor...")
            
            for col_name, col_type in missing_columns.items():
                query = f"""
                ALTER TABLE users 
                ADD COLUMN IF NOT EXISTS {col_name} {col_type}
                """
                
                try:
                    await db.execute(query)
                    logger.info(f"✅ '{col_name}' sütunu eklendi ({col_type})")
                except Exception as e:
                    logger.error(f"❌ '{col_name}' sütunu eklenirken hata: {str(e)}")
            
            logger.info("Sütun ekleme işlemleri tamamlandı.")
        else:
            logger.info("Tüm gerekli sütunlar mevcut.")
        
        return True
    except Exception as e:
        logger.error(f"Users tablosu kontrol edilirken hata: {str(e)}")
        return False
    finally:
        await db.close()

async def add_test_users():
    """Test kullanıcıları ekler"""
    db = UserDatabase()
    await db.connect()
    
    try:
        # Mevcut kullanıcı sayısını kontrol et
        query = "SELECT COUNT(*) FROM users"
        result = await db.fetchone(query)
        user_count = result[0] if result and isinstance(result, tuple) else 0
        
        logger.info(f"Mevcut kullanıcı sayısı: {user_count}")
        
        # Zaten kullanıcı varsa ekleme yapma
        if user_count > 0:
            logger.info("Veritabanında zaten kullanıcılar mevcut, test kullanıcıları eklenmeyecek.")
            return
        
        # Test kullanıcıları ekle
        test_users = [
            (1001, 'Ali', 'Yılmaz', 'aliyilmaz', True, False, datetime.now(), datetime.now()),
            (1002, 'Ayşe', 'Demir', 'aysedemir', True, False, datetime.now(), datetime.now()),
            (1003, 'Mehmet', 'Kaya', 'mehmetkaya', True, False, datetime.now(), datetime.now()),
            (1004, 'Fatma', 'Çelik', 'fatmacelik', True, False, datetime.now(), datetime.now()),
            (1005, 'Ahmet', 'Şahin', 'ahmetsahin', True, False, datetime.now(), datetime.now())
        ]
        
        logger.info(f"{len(test_users)} test kullanıcısı ekleniyor...")
        
        for user in test_users:
            query = """
            INSERT INTO users 
            (user_id, first_name, last_name, username, is_active, is_bot, created_at, updated_at) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (user_id) DO NOTHING
            """
            
            try:
                await db.execute(query, user)
                logger.info(f"✅ Test kullanıcısı eklendi: {user[1]} {user[2]} (ID: {user[0]})")
            except Exception as e:
                logger.error(f"❌ Test kullanıcısı eklenirken hata: {str(e)}")
        
        # Kullanıcı sayısını tekrar kontrol et
        query = "SELECT COUNT(*) FROM users"
        result = await db.fetchone(query)
        new_user_count = result[0] if result and isinstance(result, tuple) else 0
        
        logger.info(f"İşlem sonrası kullanıcı sayısı: {new_user_count}")
        logger.info(f"{new_user_count - user_count} yeni kullanıcı eklendi.")
        
        return True
    except Exception as e:
        logger.error(f"Test kullanıcıları eklenirken hata: {str(e)}")
        return False
    finally:
        await db.close()

async def fix_datamining_service():
    """DataMining servisinin kullanıcı depolama sorunlarını düzeltir"""
    # Bu kısımda datamining_service.py dosyasını inceleyip, hataları düzeltebiliriz
    # Şu an için sadece kontrol ediyoruz
    
    logger.info("DataMining servisi kontrol ediliyor...")
    
    # Servis kodunu kontrol et
    datamining_path = os.path.join('bot', 'services', 'data_mining_service.py')
    if not os.path.exists(datamining_path):
        logger.warning(f"DataMining servisi bulunamadı: {datamining_path}")
        return False
    
    logger.info("DataMining servisi mevcut.")
    
    # Burada daha ayrıntılı inceleme ve düzeltme işlemleri yapılabilir
    
    return True

async def main():
    """Ana fonksiyon"""
    logger.info("🔍 Kullanıcı depolama sorunları düzeltiliyor...")
    
    # Veritabanı bağlantısını kontrol et
    db = UserDatabase()
    connection_ok = await db.connect()
    
    if not connection_ok:
        logger.error("❌ Veritabanı bağlantısı kurulamadı! İşlem sonlandırılıyor.")
        return
    
    await db.close()
    
    # Users tablosunu kontrol et ve düzelt
    users_fixed = await check_users_table()
    
    if not users_fixed:
        logger.error("❌ Users tablosu kontrol edilemedi veya düzeltilemedi!")
        return
    
    # Test kullanıcılarını ekle
    users_added = await add_test_users()
    
    # DataMining servisini kontrol et
    dm_fixed = await fix_datamining_service()
    
    logger.info("\n📋 ÖZET:")
    logger.info(f"Users tablo kontrolü: {'✅ Başarılı' if users_fixed else '❌ Başarısız'}")
    logger.info(f"Test kullanıcıları ekleme: {'✅ Başarılı' if users_added else '❌ Başarısız'}")
    logger.info(f"DataMining servisi kontrolü: {'✅ Başarılı' if dm_fixed else '❌ Başarısız'}")
    
    logger.info("\n🔍 Sonraki adımlar:")
    logger.info("1. Programı tekrar çalıştırın ve kullanıcı verilerinin kalıcı olduğunu doğrulayın.")
    logger.info("2. Telegram servislerini çalıştırarak yeni kullanıcı ve grup verilerinin kaydedildiğini kontrol edin.")
    logger.info("3. Hala sorun yaşıyorsanız, `check_database.py` betiğini kullanarak daha ayrıntılı hata ayıklama yapın.")

# Programı çalıştır
if __name__ == "__main__":
    asyncio.run(main()) 