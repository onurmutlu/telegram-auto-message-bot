#!/usr/bin/env python3
"""
Özel olarak user_group_relation ve user_groups tablolarını düzeltecek script.
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
    "user_groups": """
    CREATE TABLE IF NOT EXISTS user_groups (
        id SERIAL PRIMARY KEY,
        user_id BIGINT,
        group_id BIGINT,
        join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_admin BOOLEAN DEFAULT FALSE,
        rank INTEGER DEFAULT 0,
        message_count INTEGER DEFAULT 0,
        last_message TIMESTAMP,
        is_active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_user_groups_user_id ON user_groups(user_id);
    CREATE INDEX IF NOT EXISTS idx_user_groups_group_id ON user_groups(group_id);
    """,
    
    "user_group_relation": """
    CREATE TABLE IF NOT EXISTS user_group_relation (
        id SERIAL PRIMARY KEY,
        user_id BIGINT,
        group_id BIGINT,
        is_admin BOOLEAN DEFAULT FALSE,
        join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        message_count INTEGER DEFAULT 0,
        last_activity TIMESTAMP,
        is_active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_user_group_relation_user_id ON user_group_relation(user_id);
    CREATE INDEX IF NOT EXISTS idx_user_group_relation_group_id ON user_group_relation(group_id);
    """
}

def fix_group_tables():
    """
    Grup tablolarını düzeltir
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
        
        # 1. Superuser yetkisi kontrol et
        try:
            cursor.execute(f"ALTER ROLE {db_user} WITH SUPERUSER;")
            logger.info(f"{db_user} kullanıcısı superuser yapıldı")
        except Exception as e:
            logger.error(f"Superuser yapılırken hata: {str(e)}")
        
        # 2. Mevcut tabloları yedekle
        try:
            for table_name in tables.keys():
                cursor.execute(f"SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = '{table_name}')")
                if cursor.fetchone()[0]:
                    try:
                        backup_table = f"{table_name}_backup"
                        # Önce eski yedeği sil (varsa)
                        cursor.execute(f"DROP TABLE IF EXISTS {backup_table}")
                        # Yeni yedek oluştur
                        cursor.execute(f"CREATE TABLE {backup_table} AS SELECT * FROM {table_name}")
                        logger.info(f"{table_name} tablosu yedeklendi: {backup_table}")
                    except Exception as e:
                        logger.error(f"{table_name} tablosu yedeği oluşturulurken hata: {str(e)}")
        except Exception as e:
            logger.error(f"Tablolar yedeklenirken genel hata: {str(e)}")
        
        # 3. Mevcut tabloları sil
        for table_name in tables.keys():
            try:
                cursor.execute(f"DROP TABLE IF EXISTS {table_name} CASCADE")
                logger.info(f"{table_name} tablosu silindi (CASCADE)")
            except Exception as e:
                logger.error(f"{table_name} tablosu silinirken hata: {str(e)}")
        
        # 4. Tabloları yeniden oluştur
        for table_name, create_sql in tables.items():
            try:
                cursor.execute(create_sql)
                logger.info(f"{table_name} tablosu yeniden oluşturuldu")
                
                # Sahiplik değiştir
                cursor.execute(f"ALTER TABLE {table_name} OWNER TO {db_user}")
                # Sequence sahipliğini değiştir
                cursor.execute(f"ALTER SEQUENCE {table_name}_id_seq OWNER TO {db_user}")
                # Yetkiler
                cursor.execute(f"GRANT ALL PRIVILEGES ON TABLE {table_name} TO {db_user}")
                cursor.execute(f"GRANT ALL PRIVILEGES ON SEQUENCE {table_name}_id_seq TO {db_user}")
                
                logger.info(f"{table_name} tablosu için sahiplik ve yetkiler ayarlandı")
            except Exception as e:
                logger.error(f"{table_name} tablosu oluşturulurken hata: {str(e)}")
        
        # 5. Yedeklenen verileri geri yükle
        for table_name in tables.keys():
            try:
                backup_table = f"{table_name}_backup"
                # Yedek tablo var mı kontrol et
                cursor.execute(f"SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = '{backup_table}')")
                if cursor.fetchone()[0]:
                    try:
                        # Verileri geri yükle
                        cursor.execute(f"""
                        INSERT INTO {table_name} 
                        SELECT * FROM {backup_table}
                        ON CONFLICT DO NOTHING
                        """)
                        logger.info(f"{table_name} tablosuna veriler geri yüklendi")
                        
                        # Yedek tabloyu sil (opsiyonel)
                        # cursor.execute(f"DROP TABLE IF EXISTS {backup_table}")
                        # logger.info(f"{backup_table} yedek tablosu silindi")
                    except Exception as e:
                        logger.error(f"{table_name} tablosuna veriler geri yüklenirken hata: {str(e)}")
            except Exception as e:
                logger.error(f"Veri geri yüklemede genel hata: {str(e)}")
        
        # 6. Genel şema yetkilerini ayarla
        try:
            cursor.execute(f"""
            GRANT ALL PRIVILEGES ON SCHEMA public TO {db_user};
            GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO {db_user};
            GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO {db_user};
            
            ALTER DEFAULT PRIVILEGES IN SCHEMA public 
            GRANT ALL ON TABLES TO {db_user};
            
            ALTER DEFAULT PRIVILEGES IN SCHEMA public 
            GRANT ALL ON SEQUENCES TO {db_user};
            """)
            logger.info("Genel şema yetkileri verildi")
        except Exception as e:
            logger.error(f"Genel şema yetkileri verilirken hata: {str(e)}")
        
        logger.info("Grup tabloları düzeltme işlemi tamamlandı")
        
    except Exception as e:
        logger.error(f"Genel hata: {str(e)}")

if __name__ == "__main__":
    fix_group_tables() 