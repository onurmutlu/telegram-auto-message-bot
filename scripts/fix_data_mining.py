#!/usr/bin/env python3
"""
Data mining tablosundaki user_id kolonunu düzeltir.
Bu script, veritabanındaki eksik user_id değerlerini telegram_id'den alarak doldurur.

Kullanım:
    python fix_data_mining.py
"""

import os
import sys
import logging
import asyncio
import asyncpg
from dotenv import load_dotenv

# Log ayarları
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# .env dosyasından çevre değişkenlerini yükle
load_dotenv()

# Veritabanı bağlantı bilgileri
def get_db_url():
    """Veritabanı bağlantı URL'sini oluşturur"""
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        user = os.getenv('DB_USER', 'postgres')
        password = os.getenv('DB_PASSWORD', 'postgres')
        host = os.getenv('DB_HOST', 'localhost')
        port = os.getenv('DB_PORT', '5432')
        db_name = os.getenv('DB_NAME', 'telegram_bot')
        db_url = f"postgresql://{user}:{password}@{host}:{port}/{db_name}"
    
    return db_url

async def fix_data_mining_user_ids():
    """Data mining tablosundaki user_id değerlerini düzeltir"""
    logger.info("Data mining tablosundaki user_id değerleri düzeltiliyor...")
    
    try:
        # Veritabanına bağlan
        conn = await asyncpg.connect(get_db_url())
        
        # Tablo varlığını kontrol et
        check_table = await conn.fetchval(
            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'data_mining')"
        )
        
        if not check_table:
            logger.error("data_mining tablosu bulunamadı!")
            await conn.close()
            return False
        
        # Kolon varlığını kontrol et
        check_column = await conn.fetchval(
            "SELECT EXISTS (SELECT FROM information_schema.columns WHERE table_name = 'data_mining' AND column_name = 'user_id')"
        )
        
        if not check_column:
            logger.warning("data_mining tablosunda user_id kolonu bulunamadı, ekleniyor...")
            await conn.execute("ALTER TABLE data_mining ADD COLUMN user_id INTEGER")
        
        # Telegram_id değeri olan ama user_id değeri boş olan kayıtları bul
        rows = await conn.fetch(
            """
            SELECT mining_id, telegram_id 
            FROM data_mining 
            WHERE telegram_id IS NOT NULL 
            AND (user_id IS NULL OR user_id = 0)
            AND type = 'user'
            """
        )
        
        logger.info(f"{len(rows)} adet düzeltilecek kayıt bulundu")
        
        # Her kayıt için user_id değerini güncelle
        updated_count = 0
        for row in rows:
            try:
                mining_id = row['mining_id']
                telegram_id = row['telegram_id']
                
                # Kullanıcı telegram_users tablosunda var mı kontrol et
                user_exists = await conn.fetchval(
                    "SELECT user_id FROM telegram_users WHERE user_id = $1",
                    telegram_id
                )
                
                if user_exists:
                    # User_id değerini güncelle
                    await conn.execute(
                        "UPDATE data_mining SET user_id = $1 WHERE mining_id = $2",
                        telegram_id, mining_id
                    )
                    updated_count += 1
                else:
                    # Kullanıcı yoksa, telegram_id'yi kullanarak ekle
                    await conn.execute(
                        "UPDATE data_mining SET user_id = $1 WHERE mining_id = $2",
                        telegram_id, mining_id
                    )
                    updated_count += 1
                    
                    # İsterseniz, telegram_users tablosuna da ekleyebilirsiniz:
                    # await conn.execute(
                    #     """
                    #     INSERT INTO telegram_users (user_id, created_at, updated_at) 
                    #     VALUES ($1, NOW(), NOW())
                    #     ON CONFLICT (user_id) DO NOTHING
                    #     """,
                    #     telegram_id
                    # )
            except Exception as e:
                logger.error(f"Kayıt güncellenirken hata (ID: {row['mining_id']}): {str(e)}")
        
        logger.info(f"{updated_count} adet kayıt güncellendi")
        
        # Bağlantıyı kapat
        await conn.close()
        
        return True
        
    except Exception as e:
        logger.error(f"Veritabanı işlemi sırasında hata: {str(e)}")
        return False

async def main():
    """Ana fonksiyon"""
    logger.info("Data mining düzeltme aracı başlatılıyor...")
    
    # Data mining user_id değerlerini düzelt
    success = await fix_data_mining_user_ids()
    
    if success:
        logger.info("İşlem başarıyla tamamlandı")
    else:
        logger.error("İşlem sırasında hatalar oluştu")

if __name__ == "__main__":
    asyncio.run(main()) 