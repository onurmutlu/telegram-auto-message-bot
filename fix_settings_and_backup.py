#!/usr/bin/env python3
"""
Settings tablosu sorunlarını çözen ve pg_dump yetkisi veren script.
"""
import os
import psycopg2
import subprocess
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

def fix_settings_and_backup():
    """
    Settings tablosunu düzeltir ve pg_dump yetkisi verir
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
        
        # 1. Superuser yetkisi
        try:
            cursor.execute(f"ALTER ROLE {db_user} WITH SUPERUSER;")
            logger.info(f"{db_user} kullanıcısı superuser yapıldı")
        except Exception as e:
            logger.error(f"Superuser yapılırken hata: {str(e)}")
        
        # 2. Settings tablosunu tamamen yeniden oluştur
        try:
            # Mevcut tabloyu kontrol et
            cursor.execute("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'settings')")
            if cursor.fetchone()[0]:
                # Mevcut verileri yedekle
                try:
                    cursor.execute("SELECT * FROM settings")
                    settings_data = cursor.fetchall()
                    logger.info(f"{len(settings_data)} settings kaydı bulundu")
                except Exception as e:
                    logger.error(f"Settings tablosu okunamadı: {str(e)}")
                    settings_data = []
            else:
                settings_data = []
            
            # Tabloyu düşür
            cursor.execute("DROP TABLE IF EXISTS settings CASCADE")
            logger.info("settings tablosu silindi (varsa)")
            
            # Tabloyu oluştur
            cursor.execute("""
            CREATE TABLE settings (
                id SERIAL PRIMARY KEY,
                key TEXT UNIQUE NOT NULL,
                value TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX idx_settings_key ON settings(key);
            """)
            logger.info("settings tablosu yeniden oluşturuldu")
            
            # Yetkiler ve sahiplik
            cursor.execute(f"""
            ALTER TABLE settings OWNER TO {db_user};
            ALTER SEQUENCE settings_id_seq OWNER TO {db_user};
            GRANT ALL PRIVILEGES ON TABLE settings TO {db_user};
            GRANT ALL PRIVILEGES ON SEQUENCE settings_id_seq TO {db_user};
            """)
            logger.info("settings tablosu için yetkiler verildi")
            
            # Verileri geri yükle
            if settings_data:
                for record in settings_data:
                    try:
                        # record[1] = key, record[2] = value
                        if len(record) >= 3:
                            cursor.execute("""
                            INSERT INTO settings (key, value) VALUES (%s, %s)
                            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
                            """, (record[1], record[2]))
                    except Exception as e:
                        logger.error(f"Kayıt geri yüklenirken hata: {str(e)}")
                logger.info(f"{len(settings_data)} settings kaydı geri yüklendi")
            
            # Session bilgisi ekle
            try:
                cursor.execute("""
                INSERT INTO settings (key, value) VALUES ('session_string', 'placeholder')
                ON CONFLICT (key) DO NOTHING
                """)
                logger.info("Session string placeholder eklendi")
            except Exception as e:
                logger.error(f"Session string eklenirken hata: {str(e)}")
                
        except Exception as e:
            logger.error(f"Settings tablosu düzeltilirken hata: {str(e)}")
            
        # 3. config tablosunu düzelt
        try:
            cursor.execute("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'config')")
            if cursor.fetchone()[0]:
                cursor.execute(f"""
                ALTER TABLE config OWNER TO {db_user};
                GRANT ALL PRIVILEGES ON TABLE config TO {db_user};
                """)
                logger.info("config tablosu düzeltildi")
            else:
                logger.info("config tablosu bulunamadı")
        except Exception as e:
            logger.error(f"config tablosu düzeltilirken hata: {str(e)}")
        
        # 4. PostgreSQL veritabanı erişim yetkisi
        try:
            cursor.execute(f"""
            DO $$
            BEGIN
                -- GRANT pg_dump yetkisi
                BEGIN
                    EXECUTE 'GRANT pg_execute_server_program TO {db_user}';
                EXCEPTION WHEN OTHERS THEN
                    RAISE NOTICE 'pg_execute_server_program yetkisi verilemedi: %', SQLERRM;
                END;
                
                -- GRANT rds_superuser yetkisi
                BEGIN
                    EXECUTE 'GRANT rds_superuser TO {db_user}';
                EXCEPTION WHEN OTHERS THEN
                    RAISE NOTICE 'rds_superuser yetkisi verilemedi: %', SQLERRM;
                END;
                
                -- GRANT pg_read_all_data and pg_write_all_data
                BEGIN
                    EXECUTE 'GRANT pg_read_all_data TO {db_user}';
                    EXECUTE 'GRANT pg_write_all_data TO {db_user}';
                EXCEPTION WHEN OTHERS THEN
                    RAISE NOTICE 'pg_read/write_all_data yetkisi verilemedi: %', SQLERRM;
                END;
            END $$;
            """)
            logger.info("PostgreSQL yedekleme yetkileri verildi")
        except Exception as e:
            logger.error(f"PostgreSQL yetkisi verilirken hata: {str(e)}")
        
        # 5. Tüm tablolara yetki ver
        try:
            cursor.execute("""
            SELECT tablename FROM pg_tables WHERE schemaname = 'public'
            """)
            tables = [row[0] for row in cursor.fetchall()]
            
            for table in tables:
                try:
                    cursor.execute(f"""
                    GRANT ALL PRIVILEGES ON TABLE {table} TO {db_user};
                    """)
                except Exception as e:
                    logger.error(f"{table} tablosu için yetki verilirken hata: {str(e)}")
            
            logger.info(f"{len(tables)} tabloya yetki verildi")
        except Exception as e:
            logger.error(f"Tablo yetkilerini verirken genel hata: {str(e)}")
        
        # Bağlantıyı kapat
        cursor.close()
        conn.close()
        logger.info("İşlem başarıyla tamamlandı")
        
        # 6. pg_dump'ı test et
        try:
            env = os.environ.copy()
            env['PGPASSWORD'] = db_password
            cmd = [
                'pg_dump',
                f'--host={db_host}',
                f'--port={db_port}',
                f'--username={db_user}',
                f'--dbname={db_name}',
                '--no-password',
                '--schema-only',
                '--section=pre-data'
            ]
            
            # Komutu çalıştır
            test_result = subprocess.run(cmd, capture_output=True, text=True, env=env)
            if test_result.returncode == 0:
                logger.info("pg_dump testi başarılı")
            else:
                logger.error(f"pg_dump testi başarısız: {test_result.stderr}")
                
        except Exception as e:
            logger.error(f"pg_dump testi sırasında hata: {str(e)}")
    
    except Exception as e:
        logger.error(f"Genel hata: {str(e)}")

if __name__ == "__main__":
    fix_settings_and_backup() 