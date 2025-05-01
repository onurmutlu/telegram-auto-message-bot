#!/usr/bin/env python3
"""
PostgreSQL veritabanı tablolarında eksik kolonları ve özellikle user_id kolonunu
düzeltmeye odaklanan script.
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

def fix_missing_columns():
    """
    Eksik kolonları tespit edip düzelten fonksiyon
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
        
        # Veri madenciliği tablosunu kontrol et ve düzelt
        # "column user_id does not exist" hatası için
        cursor.execute("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables WHERE table_name = 'data_mining'
        )
        """)
        data_mining_exists = cursor.fetchone()[0]
        
        if data_mining_exists:
            # Tablo mevcut, user_id kolonunu kontrol et
            cursor.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'data_mining' AND column_name = 'user_id'
            )
            """)
            user_id_exists = cursor.fetchone()[0]
            
            if not user_id_exists:
                logger.info("data_mining tablosunda user_id kolonu eksik, ekleniyor...")
                try:
                    # user_id kolonu ekle
                    cursor.execute("""
                    ALTER TABLE data_mining ADD COLUMN user_id BIGINT;
                    """)
                    logger.info("data_mining tablosuna user_id kolonu eklendi")
                    
                    # Varolan kayıtları düzelt - telegram_id değerlerini user_id'ye kopyala
                    cursor.execute("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name = 'data_mining' AND column_name = 'telegram_id'
                    )
                    """)
                    telegram_id_exists = cursor.fetchone()[0]
                    
                    if telegram_id_exists:
                        logger.info("telegram_id değerleri user_id kolonuna kopyalanıyor...")
                        cursor.execute("""
                        UPDATE data_mining SET user_id = telegram_id WHERE user_id IS NULL;
                        """)
                        logger.info("Mevcut telegram_id değerleri user_id kolonuna kopyalandı")
                except Exception as e:
                    logger.error(f"data_mining tablosu düzenlenirken hata: {str(e)}")
            else:
                logger.info("data_mining tablosunda user_id kolonu zaten mevcut")
        else:
            logger.info("data_mining tablosu bulunamadı, yeni tablo oluşturuluyor...")
            try:
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
            except Exception as e:
                logger.error(f"data_mining tablosu oluşturulurken hata: {str(e)}")
        
        # message tablosu için kontrol ve düzeltme yap
        # Eğer message tablosundaki user_id ile ilgili sorun varsa
        cursor.execute("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables WHERE table_name = 'messages'
        )
        """)
        messages_exists = cursor.fetchone()[0]
        
        if messages_exists:
            # Tablo mevcut, user_id kolonunu kontrol et
            cursor.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'messages' AND column_name = 'user_id'
            )
            """)
            user_id_exists = cursor.fetchone()[0]
            
            if not user_id_exists:
                logger.info("messages tablosunda user_id kolonu eksik, ekleniyor...")
                try:
                    # user_id kolonu ekle
                    cursor.execute("""
                    ALTER TABLE messages ADD COLUMN user_id BIGINT;
                    """)
                    logger.info("messages tablosuna user_id kolonu eklendi")
                    
                    # Varolan kayıtları düzelt - from_id/to_id değerlerini user_id'ye kopyala
                    cursor.execute("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name = 'messages' AND column_name = 'from_id'
                    )
                    """)
                    from_id_exists = cursor.fetchone()[0]
                    
                    if from_id_exists:
                        logger.info("from_id değerleri user_id kolonuna kopyalanıyor...")
                        cursor.execute("""
                        UPDATE messages SET user_id = from_id WHERE user_id IS NULL;
                        """)
                        logger.info("Mevcut from_id değerleri user_id kolonuna kopyalandı")
                except Exception as e:
                    logger.error(f"messages tablosu düzenlenirken hata: {str(e)}")
            else:
                logger.info("messages tablosunda user_id kolonu zaten mevcut")
        else:
            logger.info("messages tablosu bulunamadı, sorun ilgili bir tablo olmayabilir")
        
        # İndeksleri oluştur, eksik indeksler de hatalara neden olabilir
        try:
            # data_mining tablosu için indeks
            cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_data_mining_user_id ON data_mining(user_id);
            """)
            logger.info("data_mining tablosu için user_id indeksi oluşturuldu")
            
            # messages tablosu için indeks (varsa)
            if messages_exists and user_id_exists:
                cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_user_id ON messages(user_id);
                """)
                logger.info("messages tablosu için user_id indeksi oluşturuldu")
        except Exception as e:
            logger.error(f"İndeksler oluşturulurken hata: {str(e)}")
        
        # user_group_relation tablosunu kontrol et
        cursor.execute("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables WHERE table_name = 'user_group_relation'
        )
        """)
        relation_exists = cursor.fetchone()[0]
        
        if relation_exists:
            # İndeksleri kontrol et ve düzelt
            try:
                # Eksik indeksler oluştur
                cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_user_group_relation_user_id ON user_group_relation(user_id);
                """)
                logger.info("user_group_relation tablosu için user_id indeksi oluşturuldu")
                
                cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_user_group_relation_group_id ON user_group_relation(group_id);
                """)
                logger.info("user_group_relation tablosu için group_id indeksi oluşturuldu")
            except Exception as e:
                logger.error(f"user_group_relation indeksleri oluşturulurken hata: {str(e)}")
            
            # Sahiplik sorununu düzelt
            try:
                cursor.execute(f"""
                ALTER TABLE user_group_relation OWNER TO {db_user};
                GRANT ALL PRIVILEGES ON TABLE user_group_relation TO {db_user};
                """)
                logger.info(f"user_group_relation tablosu sahipliği {db_user} olarak düzeltildi")
            except Exception as e:
                logger.error(f"user_group_relation sahipliği düzeltilirken hata: {str(e)}")
        
        # Bağlantıyı kapat
        cursor.close()
        conn.close()
        logger.info("Eksik kolon düzeltme işlemi tamamlandı")
        
    except Exception as e:
        logger.error(f"Genel hata: {str(e)}")

if __name__ == "__main__":
    fix_missing_columns() 