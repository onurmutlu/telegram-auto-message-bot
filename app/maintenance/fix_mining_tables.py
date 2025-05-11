#!/usr/bin/env python3
"""
Veri madenciliği tablolarını düzelten script.
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

def fix_mining_tables():
    """
    Veri madenciliği tablolarını düzeltir.
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
        
        # mining_logs tablosunu kontrol et ve eksik kolonları ekle
        cursor.execute("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables WHERE table_name = 'mining_logs'
        )
        """)
        logs_exists = cursor.fetchone()[0]
        
        if logs_exists:
            logger.info("mining_logs tablosu mevcut, kontrol ediliyor...")
            
            # user_id sütununu kontrol et ve ekle
            cursor.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'mining_logs' AND column_name = 'user_id'
            )
            """)
            user_id_exists = cursor.fetchone()[0]
            
            if not user_id_exists:
                logger.info("mining_logs tablosuna user_id kolonu ekleniyor...")
                cursor.execute("ALTER TABLE mining_logs ADD COLUMN user_id BIGINT")
                logger.info("user_id kolonu eklendi")
            else:
                logger.info("user_id kolonu zaten mevcut")
            
            # telegram_id sütununu kontrol et ve ekle
            cursor.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'mining_logs' AND column_name = 'telegram_id'
            )
            """)
            telegram_id_exists = cursor.fetchone()[0]
            
            if not telegram_id_exists:
                logger.info("mining_logs tablosuna telegram_id kolonu ekleniyor...")
                cursor.execute("ALTER TABLE mining_logs ADD COLUMN telegram_id BIGINT")
                logger.info("telegram_id kolonu eklendi")
            else:
                logger.info("telegram_id kolonu zaten mevcut")
                
            # İndeksleri oluştur
            cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_mining_logs_user_id ON mining_logs(user_id);
            CREATE INDEX IF NOT EXISTS idx_mining_logs_telegram_id ON mining_logs(telegram_id);
            CREATE INDEX IF NOT EXISTS idx_mining_logs_mining_id ON mining_logs(mining_id);
            """)
            logger.info("mining_logs indeksleri oluşturuldu")
            
            # Tablo sahipliğini değiştir
            cursor.execute(f"""
            ALTER TABLE mining_logs OWNER TO {db_user};
            GRANT ALL PRIVILEGES ON TABLE mining_logs TO {db_user};
            """)
            logger.info(f"mining_logs tablosu sahipliği {db_user} olarak değiştirildi")
            
        else:
            logger.info("mining_logs tablosu bulunamadı, oluşturuluyor...")
            
            # Tabloyu oluştur
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS mining_logs (
                id SERIAL PRIMARY KEY,
                mining_id INTEGER NOT NULL,
                user_id BIGINT,
                telegram_id BIGINT,
                action_type VARCHAR(50),
                details JSONB,
                error TEXT,
                success BOOLEAN DEFAULT TRUE,
                timestamp TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)
            logger.info("mining_logs tablosu oluşturuldu")
            
            # İndeksleri oluştur
            cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_mining_logs_user_id ON mining_logs(user_id);
            CREATE INDEX IF NOT EXISTS idx_mining_logs_telegram_id ON mining_logs(telegram_id);
            CREATE INDEX IF NOT EXISTS idx_mining_logs_mining_id ON mining_logs(mining_id);
            """)
            logger.info("mining_logs indeksleri oluşturuldu")
            
            # Tablo sahipliğini değiştir
            cursor.execute(f"""
            ALTER TABLE mining_logs OWNER TO {db_user};
            GRANT ALL PRIVILEGES ON TABLE mining_logs TO {db_user};
            """)
            logger.info(f"mining_logs tablosu sahipliği {db_user} olarak değiştirildi")
        
        # DataMiningService içindeki sorguyu düzeltmek için datamining_service.py dosyasında şu sorguyu kullan:
        logger.info("""
        DataMiningService sorgu düzeltmesi:
        Şu satırı değiştirin:
        
        stats = await self.db.fetchall(\"\"\"
            SELECT mining_id, COUNT(*) as total_records,
                   COUNT(DISTINCT telegram_id) as unique_users,
                   MAX(created_at) as last_record
            FROM mining_logs
            GROUP BY mining_id
        \"\"\")        
        """)
        
        logger.info("Mining tabloları düzeltme işlemi tamamlandı")
        
    except Exception as e:
        logger.error(f"Genel hata: {str(e)}")

if __name__ == "__main__":
    fix_mining_tables() 