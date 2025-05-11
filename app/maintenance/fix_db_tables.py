#!/usr/bin/env python3
"""
Veritabanı tablolarını düzelten ve yetkileri ayarlayan script.
"""
import psycopg2
import os
from urllib.parse import urlparse
from dotenv import load_dotenv
import logging
import sys

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

# Tablolar ve SQL tanımları
tables = {
    "messages": """
    CREATE TABLE IF NOT EXISTS messages (
        id SERIAL PRIMARY KEY,
        group_id BIGINT,
        content TEXT,
        sent_at TIMESTAMP,
        status TEXT,
        error TEXT,
        is_active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_messages_group_id ON messages(group_id);
    """,
    
    "mining_data": """
    CREATE TABLE IF NOT EXISTS mining_data (
        id SERIAL PRIMARY KEY,
        user_id BIGINT NOT NULL,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        group_id BIGINT,
        group_name TEXT,
        message_count INTEGER DEFAULT 0,
        first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_mining_data_user_id ON mining_data(user_id);
    CREATE INDEX IF NOT EXISTS idx_mining_data_group_id ON mining_data(group_id);
    """,
    
    "mining_logs": """
    CREATE TABLE IF NOT EXISTS mining_logs (
        id SERIAL PRIMARY KEY,
        mining_id BIGINT,
        action_type TEXT,
        details TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        success BOOLEAN,
        error TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_mining_logs_mining_id ON mining_logs(mining_id);
    """,
    
    "user_invites": """
    CREATE TABLE IF NOT EXISTS user_invites (
        id SERIAL PRIMARY KEY,
        user_id BIGINT,
        username TEXT,
        invite_link TEXT NOT NULL,
        group_id BIGINT,
        status TEXT DEFAULT 'pending',
        invited_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        joined_at TIMESTAMP,
        last_invite_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_user_invites_user_id ON user_invites(user_id);
    CREATE INDEX IF NOT EXISTS idx_user_invites_group_id ON user_invites(group_id);
    """,
    
    "message_templates": """
    CREATE TABLE IF NOT EXISTS message_templates (
        id SERIAL PRIMARY KEY,
        content TEXT NOT NULL,
        category TEXT,
        language TEXT DEFAULT 'tr',
        type TEXT DEFAULT 'general',
        is_active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_message_templates_category ON message_templates(category);
    CREATE INDEX IF NOT EXISTS idx_message_templates_type ON message_templates(type);
    """
}

def fix_db_tables():
    """
    Eksik tabloları oluşturur ve yetkileri ayarlar.
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
        
        # Tabloları kontrol et ve oluştur
        for table_name, create_sql in tables.items():
            try:
                check_query = f"""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = '{table_name}'
                );
                """
                cursor.execute(check_query)
                result = cursor.fetchone()
                
                if not result or not result[0]:
                    logger.info(f"{table_name} tablosu oluşturuluyor...")
                    cursor.execute(create_sql)
                    logger.info(f"{table_name} tablosu başarıyla oluşturuldu")
                else:
                    logger.info(f"{table_name} tablosu zaten mevcut")
            except Exception as e:
                logger.error(f"{table_name} tablosu oluşturulurken hata: {str(e)}")
        
        # Sequence sahipliğini düzelt
        try:
            logger.info("Sequence sahipliğini düzeltme...")
            
            # Tüm sequence'ları bul
            cursor.execute("SELECT sequence_name FROM information_schema.sequences WHERE sequence_schema = 'public'")
            sequences = [row[0] for row in cursor.fetchall()]
            
            for seq in sequences:
                try:
                    cursor.execute(f"ALTER SEQUENCE {seq} OWNER TO {db_user}")
                    logger.info(f"{seq} sequence sahipliği değiştirildi")
                except Exception as e:
                    logger.error(f"{seq} sequence sahipliği değiştirilirken hata: {str(e)}")
        except Exception as e:
            logger.error(f"Sequence sorgusu çalıştırılırken hata: {str(e)}")
        
        # Tüm tablolara yetki ver
        try:
            logger.info("Tablo yetkilerini düzeltme...")
            
            # Tüm tabloları bul
            cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
            all_tables = [row[0] for row in cursor.fetchall()]
            
            for table in all_tables:
                try:
                    cursor.execute(f"GRANT ALL PRIVILEGES ON TABLE {table} TO {db_user}")
                    logger.info(f"{table} tablosuna {db_user} için yetki verildi")
                except Exception as e:
                    logger.error(f"{table} tablosu için yetki hatası: {str(e)}")
                    
            # Sequence yetkilerini düzelt
            for seq in sequences:
                try:
                    cursor.execute(f"GRANT USAGE, SELECT ON SEQUENCE {seq} TO {db_user}")
                    logger.info(f"{seq} sequence için yetki verildi")
                except Exception as e:
                    logger.error(f"{seq} sequence için yetki hatası: {str(e)}")
        except Exception as e:
            logger.error(f"Tablo yetkilerini düzeltirken hata: {str(e)}")
        
        # Özel yetki düzeltmeleri - hatada geçen tablolara özellikle dikkat et
        try:
            cursor.execute(f"""
            DO $$
            BEGIN
                EXECUTE format('GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO %I', '{db_user}');
                EXECUTE format('GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO %I', '{db_user}');
                
                -- Özellikle sorunlu tablolara yetki ver
                EXECUTE format('GRANT ALL PRIVILEGES ON TABLE messages TO %I', '{db_user}');
                EXECUTE format('GRANT ALL PRIVILEGES ON TABLE mining_data TO %I', '{db_user}');
                EXECUTE format('GRANT ALL PRIVILEGES ON TABLE mining_logs TO %I', '{db_user}');
                EXECUTE format('GRANT ALL PRIVILEGES ON TABLE message_templates TO %I', '{db_user}');
                EXECUTE format('GRANT ALL PRIVILEGES ON TABLE user_invites TO %I', '{db_user}');
            END $$;
            """)
            logger.info("Özel tablo ve sequence yetkileri verildi")
        except Exception as e:
            logger.error(f"Özel yetki hatası: {str(e)}")
        
        # Bağlantıyı kapat
        cursor.close()
        conn.close()
        logger.info("İşlem tamamlandı")
        
    except Exception as e:
        logger.error(f"Genel hata: {str(e)}")

if __name__ == "__main__":
    fix_db_tables() 