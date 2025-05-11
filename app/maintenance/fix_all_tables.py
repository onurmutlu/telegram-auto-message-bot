#!/usr/bin/env python3
"""
PostgreSQL veritabanındaki tüm tabloları düzelten ve yetkileri veren script.
Özellikle veritabanında bulunan ancak düzeltmediğimiz tabloları da bulup düzeltir.
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

def fix_all_tables():
    """
    Veritabanındaki tüm tabloları ve dizileri bulup sahipliğini değiştirir ve yetki verir.
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
        
        # Önce PostgreSQL kullanıcısını superuser yap
        try:
            cursor.execute(f"ALTER ROLE {db_user} WITH SUPERUSER;")
            logger.info(f"{db_user} kullanıcısı superuser yapıldı")
        except Exception as e:
            logger.error(f"Superuser yapılırken hata: {str(e)}")
        
        # 1. Tüm tabloları bul
        cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        tables = [row[0] for row in cursor.fetchall()]
        logger.info(f"Toplam {len(tables)} tablo bulundu: {', '.join(tables)}")
        
        # 2. Tüm tabloların sahipliğini değiştir ve yetki ver
        for table in tables:
            try:
                # Sahipliği değiştir
                cursor.execute(f"ALTER TABLE {table} OWNER TO {db_user};")
                
                # Yetkileri ver
                cursor.execute(f"GRANT ALL PRIVILEGES ON TABLE {table} TO {db_user};")
                
                logger.info(f"{table} tablosunun sahipliği değiştirildi ve yetkiler verildi")
            except Exception as e:
                logger.error(f"{table} tablosu için hata: {str(e)}")
        
        # 3. Tüm dizileri (sequences) bul
        cursor.execute("SELECT sequence_name FROM information_schema.sequences WHERE sequence_schema = 'public'")
        sequences = [row[0] for row in cursor.fetchall()]
        logger.info(f"Toplam {len(sequences)} dizi bulundu: {', '.join(sequences)}")
        
        # 4. Tüm dizilerin sahipliğini değiştir ve yetki ver
        for seq in sequences:
            try:
                # Sahipliği değiştir
                cursor.execute(f"ALTER SEQUENCE {seq} OWNER TO {db_user};")
                
                # Yetkileri ver
                cursor.execute(f"GRANT ALL PRIVILEGES ON SEQUENCE {seq} TO {db_user};")
                
                logger.info(f"{seq} dizisinin sahipliği değiştirildi ve yetkiler verildi")
            except Exception as e:
                logger.error(f"{seq} dizisi için hata: {str(e)}")
        
        # 5. Eksik olabilecek dizileri tespit et ve oluştur
        for table in tables:
            try:
                # ID alanı olan tablolara otomatik dizi ekle
                cursor.execute(f"""
                DO $$
                BEGIN
                    IF EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name = '{table}' AND column_name = 'id'
                    ) AND NOT EXISTS (
                        SELECT 1 FROM information_schema.sequences 
                        WHERE sequence_name = '{table}_id_seq'
                    ) THEN
                        EXECUTE 'CREATE SEQUENCE IF NOT EXISTS {table}_id_seq OWNED BY {table}.id;';
                        EXECUTE 'ALTER TABLE {table} ALTER COLUMN id SET DEFAULT nextval(''{table}_id_seq''::regclass);';
                        EXECUTE 'ALTER SEQUENCE {table}_id_seq OWNER TO {db_user};';
                        EXECUTE 'GRANT ALL PRIVILEGES ON SEQUENCE {table}_id_seq TO {db_user};';
                    END IF;
                END $$;
                """)
                logger.info(f"{table} tablosu için diziler kontrol edildi")
            except Exception as e:
                logger.error(f"{table} tablosu için dizi kontrolü hatası: {str(e)}")
        
        # 6. user_group_relation tablosu için özel düzeltme
        try:
            # Tabloyu kontrol et
            cursor.execute("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'user_group_relation')")
            if cursor.fetchone()[0]:
                # Tablo varsa indeksleri düzelt
                cursor.execute("""
                DO $$
                BEGIN
                    -- Varsa indeks kaldır
                    IF EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_user_group_relation_user_id') THEN
                        DROP INDEX idx_user_group_relation_user_id;
                    END IF;
                    IF EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_user_group_relation_group_id') THEN
                        DROP INDEX idx_user_group_relation_group_id;
                    END IF;
                    
                    -- Yeniden oluştur
                    CREATE INDEX IF NOT EXISTS idx_user_group_relation_user_id ON user_group_relation(user_id);
                    CREATE INDEX IF NOT EXISTS idx_user_group_relation_group_id ON user_group_relation(group_id);
                    
                EXCEPTION WHEN OTHERS THEN
                    RAISE NOTICE 'Error fixing user_group_relation: %', SQLERRM;
                END $$;
                """)
                logger.info("user_group_relation tablosu için indeksler düzeltildi")
            else:
                logger.info("user_group_relation tablosu bulunamadı, atlanıyor")
        except Exception as e:
            logger.error(f"user_group_relation tablosu için özel düzeltme hatası: {str(e)}")
        
        # 7. user_groups tablosu için özel düzeltme
        try:
            # Tabloyu kontrol et
            cursor.execute("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'user_groups')")
            if cursor.fetchone()[0]:
                # Tablo sahipliğini ve yetkilerini değiştir
                cursor.execute("""
                ALTER TABLE user_groups OWNER TO postgres;
                GRANT ALL PRIVILEGES ON TABLE user_groups TO postgres;
                """)
                logger.info("user_groups tablosu düzeltildi")
            else:
                logger.info("user_groups tablosu bulunamadı, atlanıyor")
        except Exception as e:
            logger.error(f"user_groups tablosu için özel düzeltme hatası: {str(e)}")
        
        # 8. Genel şema yetkileri
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
                EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO %I', '{db_user}');
                
                -- Superuser spesifik yetkiler
                EXECUTE format('GRANT pg_execute_server_program TO %I', '{db_user}');
                EXECUTE format('GRANT rds_superuser TO %I', '{db_user}');
                
            EXCEPTION WHEN OTHERS THEN
                RAISE NOTICE 'Error granting schema privileges: %', SQLERRM;
            END $$;
            """)
            logger.info("Genel şema yetkileri verildi")
        except Exception as e:
            logger.error(f"Genel şema yetkileri verilirken hata: {str(e)}")
        
        # 9. Veritabanı yedekleme yetkisi
        try:
            cursor.execute(f"""
            SELECT 'pg_dump'::regproc;
            """)
            logger.info("pg_dump yetkisi kontrol edildi")
        except Exception as e:
            logger.error(f"pg_dump yetkisi kontrol edilirken hata: {str(e)}")
        
        # 10. Özel olarak settings tablosunu düzelt
        try:
            cursor.execute("""
            DROP TABLE IF EXISTS settings CASCADE;
            CREATE TABLE settings (
                id SERIAL PRIMARY KEY,
                key TEXT UNIQUE NOT NULL,
                value TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            GRANT ALL PRIVILEGES ON TABLE settings TO postgres;
            GRANT ALL PRIVILEGES ON SEQUENCE settings_id_seq TO postgres;
            ALTER TABLE settings OWNER TO postgres;
            ALTER SEQUENCE settings_id_seq OWNER TO postgres;
            """)
            logger.info("settings tablosu yeniden oluşturuldu ve düzeltildi")
        except Exception as e:
            logger.error(f"settings tablosu düzeltilirken hata: {str(e)}")
        
        # Bağlantıyı kapat
        cursor.close()
        conn.close()
        logger.info("İşlem başarıyla tamamlandı")
        
    except Exception as e:
        logger.error(f"Genel hata: {str(e)}")

if __name__ == "__main__":
    fix_all_tables() 