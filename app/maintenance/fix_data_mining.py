#!/usr/bin/env python3
"""
Data mining tablosundaki eksik kolonları ve özellikle user_id kolonunu düzelten script.
"""
import os
import sys
import logging
import psycopg2
from urllib.parse import urlparse
from dotenv import load_dotenv

# Log formatını ayarla
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# .env dosyasından ayarları yükle
load_dotenv()

# Veritabanı bağlantı bilgilerini al
db_url = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/telegram_bot')

# Bağlantı parametrelerini ayrıştır
url = urlparse(db_url)
db_name = url.path[1:]  # / işaretini kaldır
db_user = url.username or 'postgres'
db_password = url.password or 'postgres'
db_host = url.hostname or 'localhost'
db_port = url.port or 5432

logger.info(f"Veritabanı: {db_host}:{db_port}/{db_name} (Kullanıcı: {db_user})")

def fix_data_mining_table():
    """
    Data mining tablosunu düzeltir
    """
    try:
        # Veritabanına bağlan
        conn = psycopg2.connect(
            dbname=db_name,
            user=db_user,
            password=db_password,
            host=db_host,
            port=db_port
        )
        conn.autocommit = True
        cursor = conn.cursor()
        
        logger.info("Veritabanına bağlandı")
        
        # Superuser yetkisi ver
        try:
            cursor.execute(f"ALTER ROLE {db_user} WITH SUPERUSER")
            logger.info(f"{db_user} kullanıcısı superuser yapıldı")
        except Exception as e:
            logger.warning(f"Superuser yapma hatası: {str(e)}")
        
        # data_mining tablosunu kontrol et
        cursor.execute("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables WHERE table_name = 'data_mining'
        )
        """)
        table_exists = cursor.fetchone()[0]
        
        if not table_exists:
            logger.info("data_mining tablosu bulunamadı, oluşturuluyor...")
            
            # Tabloyu oluştur
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS data_mining (
                mining_id SERIAL PRIMARY KEY,
                user_id BIGINT,
                telegram_id BIGINT,
                type VARCHAR(50),
                source VARCHAR(100),
                data JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)
            logger.info("data_mining tablosu oluşturuldu")
            
            # İndeksleri oluştur
            cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_data_mining_user_id ON data_mining(user_id);
            CREATE INDEX IF NOT EXISTS idx_data_mining_telegram_id ON data_mining(telegram_id);
            CREATE INDEX IF NOT EXISTS idx_data_mining_type ON data_mining(type);
            """)
            logger.info("data_mining indeksleri oluşturuldu")
        else:
            # Kolon varlığını kontrol et
            cursor.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'data_mining' AND column_name = 'user_id'
            )
            """)
            column_exists = cursor.fetchone()[0]
            
            if not column_exists:
                logger.info("data_mining tablosunda user_id kolonu eksik, ekleniyor...")
                
                # Kolon ekle
                cursor.execute("""
                ALTER TABLE data_mining ADD COLUMN user_id BIGINT;
                """)
                logger.info("user_id kolonu eklendi")
                
                # telegram_id değerlerini user_id'ye kopyala
                cursor.execute("""
                UPDATE data_mining SET user_id = telegram_id WHERE user_id IS NULL;
                """)
                logger.info("telegram_id değerleri user_id'ye kopyalandı")
                
                # İndeks oluştur
                cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_data_mining_user_id ON data_mining(user_id);
                """)
                logger.info("user_id için indeks oluşturuldu")
            else:
                logger.info("user_id kolonu zaten mevcut")
        
        # mining_data tablosunu da kontrol et (alternatif tablo adı)
        cursor.execute("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables WHERE table_name = 'mining_data'
        )
        """)
        alt_table_exists = cursor.fetchone()[0]
        
        if alt_table_exists:
            logger.info("mining_data alternatif tablosu bulundu, düzeltiliyor...")
            
            # Kolon varlığını kontrol et
            cursor.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'mining_data' AND column_name = 'user_id'
            )
            """)
            alt_column_exists = cursor.fetchone()[0]
            
            if not alt_column_exists:
                logger.info("mining_data tablosunda user_id kolonu eksik, ekleniyor...")
                
                # Kolon ekle
                cursor.execute("""
                ALTER TABLE mining_data ADD COLUMN user_id BIGINT;
                """)
                logger.info("user_id kolonu eklendi")
                
                # telegram_id değerlerini user_id'ye kopyala
                cursor.execute("""
                UPDATE mining_data SET user_id = telegram_id WHERE user_id IS NULL;
                """)
                logger.info("telegram_id değerleri user_id'ye kopyalandı")
                
                # İndeks oluştur
                cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_mining_data_user_id ON mining_data(user_id);
                """)
                logger.info("user_id için indeks oluşturuldu")
            else:
                logger.info("user_id kolonu zaten mevcut")
        
        logger.info("Data mining tablosu düzeltme işlemi tamamlandı")
        
    except Exception as e:
        logger.error(f"Genel hata: {str(e)}")

if __name__ == "__main__":
    fix_data_mining_table() 