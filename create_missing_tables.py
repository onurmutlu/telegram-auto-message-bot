#!/usr/bin/env python3
"""
PostgreSQL'de eksik tabloları oluşturan ve gerekli yetkileri veren script.
"""
import os
import psycopg2
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

# Oluşturulacak tablolar ve SQL komutları
tables = {
    "groups": """
    CREATE TABLE IF NOT EXISTS groups (
        id SERIAL PRIMARY KEY,
        group_id BIGINT UNIQUE NOT NULL,
        name TEXT,
        join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_message TIMESTAMP,
        message_count INTEGER DEFAULT 0,
        member_count INTEGER DEFAULT 0,
        error_count INTEGER DEFAULT 0,
        last_error TEXT,
        is_active BOOLEAN DEFAULT TRUE,
        permanent_error BOOLEAN DEFAULT FALSE,
        is_target BOOLEAN DEFAULT FALSE,
        retry_after TIMESTAMP,
        is_admin BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_groups_group_id ON groups(group_id);
    CREATE INDEX IF NOT EXISTS idx_groups_is_active ON groups(is_active);
    """,
    
    "settings": """
    CREATE TABLE IF NOT EXISTS settings (
        id SERIAL PRIMARY KEY,
        key TEXT UNIQUE NOT NULL,
        value TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_settings_key ON settings(key);
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
    """,
    
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
    
    "users": """
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        user_id BIGINT UNIQUE NOT NULL,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        is_active BOOLEAN DEFAULT TRUE,
        join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_users_user_id ON users(user_id);
    CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
    CREATE INDEX IF NOT EXISTS idx_users_is_active ON users(is_active);
    """
}

def drop_and_recreate_tables():
    """
    Sorunlu tabloları düşürüp yeniden oluşturur ve yetkilendirir.
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
        
        # Tabloları düşür ve yeniden oluştur
        for table_name, create_sql in tables.items():
            try:
                # Önce tabloyu düşür
                drop_query = f"DROP TABLE IF EXISTS {table_name} CASCADE;"
                cursor.execute(drop_query)
                logger.info(f"{table_name} tablosu düşürüldü (varsa)")
                
                # Sonra yeniden oluştur
                cursor.execute(create_sql)
                logger.info(f"{table_name} tablosu yeniden oluşturuldu")
                
                # Yetkiler ver
                owner_query = f"ALTER TABLE {table_name} OWNER TO {db_user};"
                cursor.execute(owner_query)
                
                # Sequence yetkisi ver
                seq_query = f"ALTER SEQUENCE {table_name}_id_seq OWNER TO {db_user};"
                cursor.execute(seq_query)
                
                permission_query = f"GRANT ALL PRIVILEGES ON TABLE {table_name} TO {db_user};"
                cursor.execute(permission_query)
                
                logger.info(f"{table_name} tablosuna yetkiler verildi")
            except Exception as e:
                logger.error(f"{table_name} tablosu işlenirken hata: {str(e)}")
        
        # Genel yetkiler
        try:
            cursor.execute(f"""
            DO $$
            BEGIN
                -- Şema yetkisi
                EXECUTE format('GRANT ALL PRIVILEGES ON SCHEMA public TO %I', '{db_user}');
                -- Tüm tablolar için yetki
                EXECUTE format('GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO %I', '{db_user}');
                -- Tüm diziler için yetki
                EXECUTE format('GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO %I', '{db_user}');
                -- Varsayılan yetkiler
                EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO %I', '{db_user}');
                EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO %I', '{db_user}');
            END $$;
            """)
            logger.info("Genel şema ve veritabanı yetkileri verildi")
        except Exception as e:
            logger.error(f"Genel yetkiler verilirken hata: {str(e)}")
        
        # groups tablosuna bazı örnek veriler ekle
        try:
            # Önce örnek grup var mı kontrol et
            cursor.execute("SELECT COUNT(*) FROM groups WHERE name = 'Örnek Grup'")
            count = cursor.fetchone()[0]
            
            if count == 0:
                # Örnek grup ekle
                cursor.execute("""
                INSERT INTO groups (group_id, name, is_admin, is_active)
                VALUES (-1, 'Örnek Grup', true, true),
                       (-2, 'Test Grubu', false, true),
                       (-3, 'Duyuru Grubu', true, true)
                """)
                logger.info("Örnek gruplar eklendi")
        except Exception as e:
            logger.error(f"Örnek gruplar eklenirken hata: {str(e)}")
        
        # Bağlantıyı kapat
        cursor.close()
        conn.close()
        logger.info("İşlem tamamlandı")
        
    except Exception as e:
        logger.error(f"Genel hata: {str(e)}")

if __name__ == "__main__":
    drop_and_recreate_tables() 