#!/usr/bin/env python3
"""
PostgreSQL veritabanı yetki sorunlarını düzelten script.
Bu script, veritabanındaki tüm tablolara ve dizilere erişim yetkisi verir.
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

def fix_permissions():
    """
    Veritabanı yetkilerini düzeltir.
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
        
        # Tablo sahipliğini güncelle (mümkünse)
        try:
            cursor.execute("""
            DO $$
            DECLARE
                tbl text;
            BEGIN
                FOR tbl IN SELECT tablename FROM pg_tables WHERE schemaname = 'public'
                LOOP
                    BEGIN
                        EXECUTE format('ALTER TABLE %I OWNER TO %I', tbl, 'postgres');
                        RAISE NOTICE 'Table % ownership changed', tbl;
                    EXCEPTION WHEN OTHERS THEN
                        RAISE NOTICE 'Cannot change ownership of table %: %', tbl, SQLERRM;
                    END;
                END LOOP;
            END $$;
            """)
            logger.info("Tablo sahipliği güncellendi (mümkün olduğunca)")
        except Exception as e:
            logger.error(f"Tablo sahipliği güncellenirken hata: {str(e)}")
        
        # Tüm tablolara tüm yetkiler
        cursor.execute(f"""
        DO $$
        DECLARE
            tbl text;
        BEGIN
            -- Tüm tablolara yetki ver
            FOR tbl IN SELECT tablename FROM pg_tables WHERE schemaname = 'public'
            LOOP
                EXECUTE format('GRANT ALL PRIVILEGES ON TABLE %I TO %I', tbl, '{db_user}');
                RAISE NOTICE 'Granted privileges on table %', tbl;
            END LOOP;
            
            -- Tüm dizilere yetki ver
            FOR tbl IN SELECT sequence_name FROM information_schema.sequences WHERE sequence_schema = 'public'
            LOOP
                EXECUTE format('GRANT ALL PRIVILEGES ON SEQUENCE %I TO %I', tbl, '{db_user}');
                RAISE NOTICE 'Granted privileges on sequence %', tbl;
            END LOOP;
        END $$;
        """)
        logger.info("Tüm tablolara ve dizilere yetki verildi")
        
        # Özellikle hata veren tablolara ekstra yetki
        problem_tables = [
            "message_templates", "messages", "mining_data", 
            "mining_logs", "user_invites", "debug_bot_users",
            "settings", "groups", "users", "user_groups", 
            "spam_messages", "user_demographics", "user_activity",
            "group_analytics", "user_group_activity", "user_bio_links",
            "user_bio_scan_logs", "category_groups", "user_group_relation",
            "migrations", "config"
        ]
        
        for table in problem_tables:
            try:
                cursor.execute(f"""
                DO $$
                BEGIN
                    -- ALTER TABLE {table} OWNER TO {db_user};
                    GRANT ALL PRIVILEGES ON TABLE {table} TO {db_user};
                    -- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO {db_user};
                END $$;
                """)
                logger.info(f"{table} tablosuna özel yetkiler verildi")
            except Exception as e:
                logger.error(f"{table} tablosuna yetki verilirken hata: {str(e)}")
        
        # Şema üzerinde genel yetkiler
        cursor.execute(f"""
        DO $$
        BEGIN
            -- Şema yetkisi
            GRANT USAGE ON SCHEMA public TO {db_user};
            
            -- Mevcut nesneler üzerinde yetki
            GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO {db_user};
            GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO {db_user};
            GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO {db_user};
            
            -- Bunu değiştiren kullanıcıyı DB sahibi yap
            ALTER ROLE {db_user} WITH CREATEDB CREATEROLE SUPERUSER;
            
            -- Gelecekte oluşturulacak nesneler için varsayılan yetkiler
            ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO {db_user};
            ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO {db_user};
            ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO {db_user};
            
            -- Owner yetkisini kullanıcıya vermek için
            GRANT pg_execute_server_program TO {db_user};
        END $$;
        """)
        logger.info("Şema yetkileri ve varsayılan yetkiler ayarlandı")
        
        # Bağlantıyı kapat
        cursor.close()
        conn.close()
        logger.info("İşlem tamamlandı")
        
    except Exception as e:
        logger.error(f"Genel hata: {str(e)}")

if __name__ == "__main__":
    fix_permissions() 