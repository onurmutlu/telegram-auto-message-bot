import asyncio
import os
import logging
from database.user_db import UserDatabase

# Logging ayarları
logging.basicConfig(level=logging.DEBUG, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def get_user_count():
    """Veritabanındaki kullanıcı sayısını getirir."""
    logger.info("Veritabanı bağlantısı oluşturuluyor...")
    
    # Veritabanı bağlantı URL'sini göster
    db_url = os.getenv("DB_CONNECTION", "postgresql://postgres:postgres@localhost:5432/telegram_bot")
    logger.info(f"Kullanılan veritabanı URL'si: {db_url}")
    
    # Veritabanı bağlantısını oluştur
    db = UserDatabase(db_url)
    
    # Bağlantıyı aç ve tabloları kontrol et
    logger.info("Veritabanı bağlantısı açılıyor...")
    connection_result = await db.connect()
    
    if not connection_result:
        logger.error("Veritabanına bağlanılamadı!")
        return 0
        
    logger.info("Veritabanı bağlantısı başarılı")
    
    # Tabloların varlığını kontrol et
    logger.info("Tablolar kontrol ediliyor...")
    tables_exist = await check_tables_exist(db)
    
    if not tables_exist:
        logger.warning("Gerekli tablolar bulunamadı, oluşturuluyor...")
        await db.create_tables()
    
    try:
        # Kullanıcı sayısını çek
        logger.info("Kullanıcı sayısı çekiliyor...")
        query = "SELECT COUNT(*) FROM users"
        result = await db.fetchone(query)
        
        logger.info(f"Sorgu sonucu: {result}")
        
        # İlk değeri al (tuple veya dict olabilir)
        if isinstance(result, tuple):
            count = result[0]
        elif isinstance(result, dict) and 'count' in result:
            count = result['count']
        else:
            count = result
        
        logger.info(f"Bulunan kullanıcı sayısı: {count}")
        return count
    except Exception as e:
        logger.error(f"Kullanıcı sayısı çekilirken hata: {str(e)}")
        return 0
    finally:
        # Bağlantıyı kapat
        logger.info("Veritabanı bağlantısı kapatılıyor...")
        await db.close()

async def check_tables_exist(db):
    """Gerekli tabloların var olup olmadığını kontrol eder"""
    try:
        # PostgreSQL schema kontrol sorgusu
        query = """
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = 'users'
        )
        """
        result = await db.fetchone(query)
        
        # Sonuç kontrolü
        if result and (result[0] if isinstance(result, tuple) else result):
            logger.info("'users' tablosu mevcut")
            return True
        else:
            logger.warning("'users' tablosu bulunamadı")
            return False
    except Exception as e:
        logger.error(f"Tablo kontrolü sırasında hata: {str(e)}")
        return False

async def check_db_connection():
    """Veritabanı bağlantısını test eder"""
    db = UserDatabase()
    connection_result = await db.connect()
    
    if connection_result:
        logger.info("Veritabanı bağlantısı başarılı")
        
        # Bağlantı detaylarını göster
        if hasattr(db, 'db_host') and hasattr(db, 'db_port') and hasattr(db, 'db_name'):
            logger.info(f"Bağlantı detayları: {db.db_host}:{db.db_port}/{db.db_name}")
            
        # Tablolar var mı kontrol et
        tables_exist = await check_tables_exist(db)
        
        # Bağlantıyı kapat
        await db.close()
        return True
    else:
        logger.error("Veritabanı bağlantısı kurulamadı!")
        return False

# Ana fonksiyon
async def main():
    try:
        # Önce bağlantıyı kontrol et
        logger.info("Veritabanı bağlantısı kontrol ediliyor...")
        connection_ok = await check_db_connection()
        
        if not connection_ok:
            logger.error("Veritabanı bağlantısı sağlanamadı!")
            return
            
        # Kullanıcı sayısını çek
        user_count = await get_user_count()
        print(f"Toplam kullanıcı sayısı: {user_count}")
        
        # Eğer kullanıcı sayısı 0 ise veritabanını oluştur
        if user_count == 0:
            logger.warning("Kullanıcı sayısı 0! Veritabanı tabloları oluşturuluyor...")
            db = UserDatabase()
            await db.connect()
            await db.create_tables()
            await db.close()
            logger.info("Veritabanı tabloları oluşturuldu, program yeniden çalıştırılmalı")
    except Exception as e:
        logger.error(f"Ana fonksiyonda hata: {str(e)}", exc_info=True)

# Programı çalıştır
if __name__ == "__main__":
    asyncio.run(main())
