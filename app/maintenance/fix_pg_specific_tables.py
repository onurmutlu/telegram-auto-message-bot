#!/usr/bin/env python3
"""
PostgreSQL veritabanındaki kritik yetki sorunlarını düzeltmeye odaklanan script.
Özellikle "permission denied" hatalarını veren pg_dump sırasında sorun çıkaran tablolar için.
"""
import os
import sys
import logging
import psycopg2
import subprocess
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

def fix_specific_tables():
    """
    Özel olarak belirtilen sorunlu tabloların yetkilendirmelerini düzeltir
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
        
        # Bu tablolar, hatalardan tespit edildiği üzere özellikle sorun yaratıyor
        problem_tables = [
            "config",
            "settings",
            "user_groups",
            "groups",
            "debug_bot_users",
            "user_group_relation"
        ]
        
        # Superuser yetkisi ver
        try:
            cursor.execute(f"ALTER ROLE {db_user} WITH SUPERUSER")
            logger.info(f"{db_user} rolüne superuser yetkisi verildi")
        except Exception as e:
            logger.error(f"Superuser yetkisi verilirken hata: {str(e)}")
        
        # Şema sahipliğini değiştir
        try:
            cursor.execute(f"ALTER SCHEMA public OWNER TO {db_user}")
            logger.info(f"public şeması sahipliği {db_user} olarak değiştirildi")
        except Exception as e:
            logger.error(f"Şema sahipliği değiştirilirken hata: {str(e)}")
        
        # Tabloların sahipliklerini ve izinlerini güçlü bir şekilde değiştir
        for table in problem_tables:
            logger.info(f"'{table}' tablosu için yetkilendirme yapılıyor...")
            
            # Tablonun varlığını kontrol et
            cursor.execute(f"""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables WHERE table_name = '{table}'
            )
            """)
            table_exists = cursor.fetchone()[0]
            
            if not table_exists:
                logger.warning(f"Tablo bulunamadı: {table}")
                continue
            
            # 1. Tablo sahipliğini değiştir (birden fazla yöntemle)
            try:
                # Yöntem 1: Standart ALTER TABLE
                cursor.execute(f"ALTER TABLE {table} OWNER TO {db_user}")
                logger.info(f"{table} tablosunun sahipliği {db_user} olarak değiştirildi (Yöntem 1)")
            except Exception as e:
                logger.warning(f"Sahiplik değiştirilemedi (Yöntem 1): {str(e)}")
                
                try:
                    # Yöntem 2: DO bloğu içinde
                    cursor.execute(f"""
                    DO $$
                    BEGIN
                        EXECUTE 'ALTER TABLE {table} OWNER TO {db_user}';
                    EXCEPTION WHEN OTHERS THEN
                        RAISE NOTICE 'Sahiplik değiştirilemedi: %', SQLERRM;
                    END $$;
                    """)
                    logger.info(f"{table} tablosunun sahipliği {db_user} olarak değiştirilmeye çalışıldı (Yöntem 2)")
                except Exception as e2:
                    logger.error(f"Sahiplik değiştirilemedi (Yöntem 2): {str(e2)}")
            
            # 2. İlgili sequence sahipliğini değiştir
            try:
                cursor.execute(f"""
                DO $$
                BEGIN
                    IF EXISTS (
                        SELECT 1 FROM information_schema.sequences WHERE sequence_name = '{table}_id_seq'
                    ) THEN
                        EXECUTE 'ALTER SEQUENCE {table}_id_seq OWNER TO {db_user}';
                        RAISE NOTICE 'Sequence sahipliği değiştirildi: {table}_id_seq';
                    END IF;
                EXCEPTION WHEN OTHERS THEN
                    RAISE NOTICE 'Sequence sahipliği değiştirilemedi: %', SQLERRM;
                END $$;
                """)
                logger.info(f"{table}_id_seq dizisi (varsa) sahipliği {db_user} olarak değiştirildi")
            except Exception as e:
                logger.error(f"Sequence sahipliği değiştirilemedi: {str(e)}")
            
            # 3. Tabloya tüm yetkileri ver (farklı yöntemlerle)
            try:
                # a. Doğrudan GRANT komutu
                cursor.execute(f"""
                GRANT ALL PRIVILEGES ON TABLE {table} TO {db_user};
                GRANT ALL PRIVILEGES ON TABLE {table} TO PUBLIC;
                """)
                
                # b. Ayrıntılı yetkiler
                cursor.execute(f"""
                GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER ON TABLE {table} TO {db_user};
                """)
                
                # c. İlgili sequence için yetkiler
                cursor.execute(f"""
                DO $$
                BEGIN
                    IF EXISTS (
                        SELECT 1 FROM information_schema.sequences WHERE sequence_name = '{table}_id_seq'
                    ) THEN
                        EXECUTE 'GRANT ALL PRIVILEGES ON SEQUENCE {table}_id_seq TO {db_user}';
                        EXECUTE 'GRANT USAGE, SELECT ON SEQUENCE {table}_id_seq TO PUBLIC';
                    END IF;
                EXCEPTION WHEN OTHERS THEN
                    RAISE NOTICE 'Sequence izinleri verilemedi: %', SQLERRM;
                END $$;
                """)
                
                logger.info(f"{table} tablosu ve ilişkili nesneleri için tüm yetkiler verildi")
            except Exception as e:
                logger.error(f"Tablo yetkileri verilirken hata: {str(e)}")
        
        # REASSIGN OWNED komutu ile tüm nesnelerin sahipliğini değiştir
        try:
            cursor.execute(f"""
            DO $$
            BEGIN
                -- Güvenli şekilde tüm nesnelerin sahipliğini değiştirmeyi dene
                BEGIN
                    REASSIGN OWNED BY postgres TO {db_user};
                EXCEPTION WHEN OTHERS THEN
                    RAISE NOTICE 'REASSIGN OWNED çalıştırılamadı: %', SQLERRM;
                END;
            END $$;
            """)
            logger.info("REASSIGN OWNED komutu çalıştırıldı")
        except Exception as e:
            logger.error(f"REASSIGN OWNED komutu çalıştırılırken hata: {str(e)}")
        
        # Şema düzeyinde yetkiler
        try:
            cursor.execute(f"""
            -- Şema yetkileri
            GRANT ALL PRIVILEGES ON SCHEMA public TO {db_user};
            GRANT USAGE ON SCHEMA public TO PUBLIC;
            
            -- Tüm tablolar için yetkiler
            GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO {db_user};
            
            -- Tüm sequences için yetkiler
            GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO {db_user};
            
            -- Gelecekteki nesneler için varsayılan yetkiler
            ALTER DEFAULT PRIVILEGES IN SCHEMA public
            GRANT ALL PRIVILEGES ON TABLES TO {db_user};
            
            ALTER DEFAULT PRIVILEGES IN SCHEMA public
            GRANT ALL PRIVILEGES ON SEQUENCES TO {db_user};
            """)
            logger.info("Şema düzeyinde tüm yetkiler verildi")
        except Exception as e:
            logger.error(f"Şema düzeyinde yetkiler verilirken hata: {str(e)}")
        
        # Veritabanı düzeyinde yetkiler
        try:
            cursor.execute(f"""
            -- Veritabanı yetkileri
            GRANT ALL PRIVILEGES ON DATABASE {db_name} TO {db_user};
            
            -- Veritabanı sahipliğini değiştir
            ALTER DATABASE {db_name} OWNER TO {db_user};
            """)
            logger.info(f"Veritabanı düzeyinde tüm yetkiler verildi ve sahiplik {db_user} olarak ayarlandı")
        except Exception as e:
            logger.error(f"Veritabanı yetkileri verilirken hata: {str(e)}")
        
        # pg_dump ile test et
        env = os.environ.copy()
        env['PGPASSWORD'] = db_password
        
        for table in problem_tables:
            try:
                test_cmd = [
                    'pg_dump', f'--host={db_host}', f'--port={db_port}',
                    f'--username={db_user}', f'--table={table}',
                    '--schema-only', db_name
                ]
                
                logger.info(f"{table} tablosu için pg_dump testi yapılıyor...")
                result = subprocess.run(test_cmd, capture_output=True, text=True, env=env)
                
                if result.returncode == 0:
                    logger.info(f"✓ {table} tablosu için pg_dump testi başarılı")
                else:
                    logger.error(f"✗ {table} tablosu için pg_dump testi başarısız: {result.stderr}")
                    
                    # Başarısız olan tablo için agresif yöntem dene
                    try:
                        # Tam sahiplik değiştirme komutu
                        cursor.execute(f"""
                        BEGIN;
                        SET LOCAL ROLE postgres;
                        ALTER TABLE {table} OWNER TO {db_user};
                        GRANT ALL PRIVILEGES ON TABLE {table} TO {db_user};
                        COMMIT;
                        """)
                        logger.info(f"{table} tablosu için agresif sahiplik değiştirme denendi")
                        
                        # Tekrar test et
                        result = subprocess.run(test_cmd, capture_output=True, text=True, env=env)
                        if result.returncode == 0:
                            logger.info(f"✓ {table} tablosu için ikinci pg_dump testi başarılı")
                        else:
                            logger.error(f"✗ {table} tablosu için ikinci pg_dump testi de başarısız")
                    except Exception as e:
                        logger.error(f"Agresif sahiplik değiştirme başarısız: {str(e)}")
            except Exception as e:
                logger.error(f"{table} tablosu için pg_dump testi hatası: {str(e)}")
        
        # Genel pg_dump testi
        try:
            test_cmd = [
                'pg_dump', f'--host={db_host}', f'--port={db_port}', f'--username={db_user}',
                '--schema-only', db_name
            ]
            
            logger.info("Genel pg_dump testi yapılıyor...")
            result = subprocess.run(test_cmd, capture_output=True, text=True, env=env)
            
            if result.returncode == 0:
                logger.info("✓ Genel pg_dump testi başarılı")
            else:
                logger.warning(f"✗ Genel pg_dump testi başarısız: {result.stderr}")
        except Exception as e:
            logger.error(f"Genel pg_dump testi hatası: {str(e)}")
        
        # Bağlantıyı kapat
        cursor.close()
        conn.close()
        logger.info("Tablo yetkilendirme işlemi tamamlandı")
        
    except Exception as e:
        logger.error(f"Genel hata: {str(e)}")

if __name__ == "__main__":
    fix_specific_tables() 