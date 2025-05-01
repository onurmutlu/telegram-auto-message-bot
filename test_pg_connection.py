#!/usr/bin/env python3
"""
PostgreSQL bağlantısı ve veritabanı işlevlerini test etmek için script.
"""

import os
import sys
import logging
import asyncio
from datetime import datetime
from dotenv import load_dotenv

# Proje klasörünü Python yoluna ekle
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Uygulama modüllerini içe aktar
from database.db_connection import DatabaseConnectionManager
from database.user_db import UserDatabase

# .env dosyasını yükle
load_dotenv()

# Loglama yapılandırması
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("postgres_test.log")
    ]
)

logger = logging.getLogger("PostgreSQLTest")

async def test_connection():
    """PostgreSQL bağlantısını test eder"""
    try:
        # Bağlantı yöneticisini oluştur
        db_manager = DatabaseConnectionManager()
        
        # Bağlantı başlatma
        if await db_manager.initialize():
            logger.info("Veritabanı bağlantısı başarıyla başlatıldı")
        else:
            logger.error("Veritabanı bağlantısı başlatılamadı!")
            return False
        
        # UserDatabase oluştur
        user_db = UserDatabase(db_manager)
        
        # Bağlantı oluştur
        await user_db.connect()
        logger.info(f"Kullanılan veritabanı tipi: {user_db.db_type}")
        
        # Tabloları oluştur
        await user_db.create_tables()
        await user_db.create_user_profile_tables()
        
        # Basit bir sorgu çalıştır
        test_query = "SELECT 1"
        result = await user_db.fetchone(test_query)
        logger.info(f"Test sorgusu sonucu: {result}")
        
        # Bağlantıyı kapat
        await user_db.close()
        await db_manager.close()
        
        return True
    except Exception as e:
        logger.error(f"Bağlantı testi sırasında hata: {str(e)}")
        return False

async def test_crud_operations():
    """Temel CRUD işlemlerini test eder"""
    try:
        # Bağlantı yöneticisini oluştur
        db_manager = DatabaseConnectionManager()
        await db_manager.initialize()
        
        # UserDatabase oluştur
        user_db = UserDatabase(db_manager)
        await user_db.connect()
        
        # Test grubu oluştur
        test_group_id = 123456789
        test_title = "Test Grubu"
        current_time = datetime.now()
        
        # Grubu ekle/güncelle
        group_id = await user_db.add_group(
            group_id=test_group_id,
            title=test_title, 
            join_date=current_time,
            member_count=100,
            is_active=True,
            last_activity=current_time,
            username="test_group"
        )
        
        logger.info(f"Eklenen/güncellenen grup ID: {group_id}")
        
        # Grup var mı kontrol et
        exists = await user_db.group_exists(test_group_id)
        logger.info(f"Grup var mı: {exists}")
        
        # Grubu al
        group = await user_db.get_group(test_group_id)
        logger.info(f"Grup bilgileri: {group}")
        
        # Grubu güncelle
        update_result = await user_db.update_group(
            test_group_id, 
            title="Güncellenmiş Test Grubu",
            member_count=150
        )
        logger.info(f"Grup güncelleme sonucu: {update_result}")
        
        # Grubu devre dışı bırak
        inactive_result = await user_db.mark_group_inactive(
            test_group_id,
            error_message="Test amaçlı devre dışı bırakıldı",
            permanent=False
        )
        logger.info(f"Grup devre dışı bırakma sonucu: {inactive_result}")
        
        # Aktif grupları listele
        active_groups = await user_db.get_active_groups(limit=10)
        logger.info(f"Aktif grup sayısı: {len(active_groups)}")
        
        # Kullanıcı aktivitesi logla
        activity_result = user_db.log_user_activity(
            user_id=1001,
            activity_type="login",
            details={"ip": "127.0.0.1", "device": "test"}
        )
        logger.info(f"Aktivite loglama sonucu: {activity_result}")
        
        # Bağlantıyı kapat
        await user_db.close()
        await db_manager.close()
        
        return True
    except Exception as e:
        logger.error(f"CRUD testi sırasında hata: {str(e)}")
        return False

async def main():
    """Ana fonksiyon"""
    try:
        logger.info("PostgreSQL bağlantı testi başlatılıyor...")
        
        # Bağlantı testi
        connection_result = await test_connection()
        if connection_result:
            logger.info("PostgreSQL bağlantı testi başarılı!")
        else:
            logger.error("PostgreSQL bağlantı testi başarısız!")
            return
        
        # CRUD işlemleri testi
        crud_result = await test_crud_operations()
        if crud_result:
            logger.info("PostgreSQL CRUD işlemleri testi başarılı!")
        else:
            logger.error("PostgreSQL CRUD işlemleri testi başarısız!")
            return
        
        logger.info("Tüm testler başarıyla tamamlandı!")
        
    except Exception as e:
        logger.error(f"Test sırasında hata: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main()) 