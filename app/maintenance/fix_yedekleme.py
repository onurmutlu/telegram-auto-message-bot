#!/usr/bin/env python3
"""
PostgreSQL yedekleme işlemleri için özel yetkilendirme scripti.
Bu script pg_dump ve ilgili yedekleme sorunlarını çözer.
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

def fix_backup_permissions():
    """
    Yedekleme/dump izinleri için özel yetkileri ayarlar
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
        
        # 1. Rolü superuser yaparak başla
        try:
            cursor.execute(f"""
            DO $$
            BEGIN
                ALTER ROLE {db_user} WITH SUPERUSER;
            EXCEPTION WHEN OTHERS THEN
                RAISE NOTICE 'Superuser rolü verilemedi: %', SQLERRM;
            END $$;
            """)
            logger.info(f"{db_user} superuser yapıldı")
        except Exception as e:
            logger.error(f"Superuser rolü verilirken hata: {str(e)}")
        
        # 2. Yedekleme ile ilgili özel yetkiler ver
        try:
            cursor.execute(f"""
            DO $$
            BEGIN
                -- pg_execute_server_program yetkisi
                BEGIN
                    GRANT pg_execute_server_program TO {db_user};
                EXCEPTION WHEN OTHERS THEN
                    RAISE NOTICE 'pg_execute_server_program yetkisi verilemedi: %', SQLERRM;
                END;
                
                -- RDS özel yetkisi (RDS kullanılıyorsa)
                BEGIN
                    GRANT rds_superuser TO {db_user};
                EXCEPTION WHEN OTHERS THEN
                    RAISE NOTICE 'rds_superuser yetkisi verilemedi: %', SQLERRM;
                END;
                
                -- PostgreSQL 10+ özel yetkileri
                BEGIN
                    GRANT pg_read_all_data TO {db_user};
                    GRANT pg_write_all_data TO {db_user};
                EXCEPTION WHEN OTHERS THEN
                    RAISE NOTICE 'pg_read/write_all_data yetkileri verilemedi: %', SQLERRM;
                END;
                
                -- Monitor yetkisi
                BEGIN
                    GRANT pg_monitor TO {db_user};
                EXCEPTION WHEN OTHERS THEN
                    RAISE NOTICE 'pg_monitor yetkisi verilemedi: %', SQLERRM;
                END;
                
                -- Diğer yetkiler
                BEGIN
                    ALTER ROLE {db_user} WITH CREATEDB CREATEROLE;
                EXCEPTION WHEN OTHERS THEN
                    RAISE NOTICE 'Createdb/Createrole yetkileri verilemedi: %', SQLERRM;
                END;
            END $$;
            """)
            logger.info("Yedekleme yetkileri verildi")
        except Exception as e:
            logger.error(f"Yedekleme yetkileri verilirken hata: {str(e)}")
            
        # 3. Yedekleme için gerekli olan tüm tablo ve dizileri kontrol et
        problem_tables = ['config', 'settings', 'groups', 'debug_bot_users', 'user_groups', 'user_group_relation', 'migrations']
        
        for table in problem_tables:
            try:
                # Tabloların izinlerini kontrol et ve ayarla
                cursor.execute(f"""
                DO $$
                BEGIN
                    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = '{table}') THEN
                        -- Sahiplik ayarla
                        EXECUTE format('ALTER TABLE %I OWNER TO %I', '{table}', '{db_user}');
                        
                        -- İzinleri ver
                        EXECUTE format('GRANT ALL PRIVILEGES ON TABLE %I TO %I', '{table}', '{db_user}');
                        EXECUTE format('GRANT ALL PRIVILEGES ON TABLE %I TO PUBLIC', '{table}');
                        
                        -- Yedek izinleri
                        EXECUTE format('GRANT SELECT ON TABLE %I TO %I', '{table}', '{db_user}');
                        
                        RAISE NOTICE '{table} tablosunun yedekleme izinleri ayarlandı';
                    ELSE
                        RAISE NOTICE '{table} tablosu bulunamadı, atlanıyor';
                    END IF;
                END $$;
                """)
                
                # İlgili dizilerin izinlerini de ayarla
                cursor.execute(f"""
                DO $$
                BEGIN
                    IF EXISTS (SELECT 1 FROM information_schema.sequences WHERE sequence_name = '{table}_id_seq') THEN
                        -- Sahiplik ayarla
                        EXECUTE format('ALTER SEQUENCE %I OWNER TO %I', '{table}_id_seq', '{db_user}');
                        
                        -- İzinleri ver
                        EXECUTE format('GRANT ALL PRIVILEGES ON SEQUENCE %I TO %I', '{table}_id_seq', '{db_user}');
                        EXECUTE format('GRANT USAGE, SELECT ON SEQUENCE %I TO PUBLIC', '{table}_id_seq');
                        
                        RAISE NOTICE '{table}_id_seq dizisinin yedekleme izinleri ayarlandı';
                    END IF;
                END $$;
                """)
                
                logger.info(f"{table} tablosu ve dizisinin yedekleme izinleri ayarlandı")
            except Exception as e:
                logger.error(f"{table} tablosu için yedekleme izinleri ayarlanırken hata: {str(e)}")
        
        # 4. Doğrudan pg_dump testi yap
        try:
            # Çevre değişkenlerini ayarla
            env = os.environ.copy()
            env['PGPASSWORD'] = db_password
            
            # pg_dump komutunu oluştur (sadece şema)
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
            logger.info("pg_dump test ediliyor...")
            result = subprocess.run(cmd, capture_output=True, text=True, env=env)
            
            if result.returncode == 0:
                logger.info("pg_dump testi başarılı! Yedekleme izinleri düzgün çalışıyor.")
            else:
                logger.error(f"pg_dump testi başarısız! Hata: {result.stderr}")
                
                # Yedek izin stratejisi
                if 'permission denied' in result.stderr:
                    logger.info("İzin hatası algılandı. Alternatif yetkilendirme uygulanıyor...")
                    
                    cursor.execute(f"""
                    DO $$
                    BEGIN
                        -- Tüm tablolar için okuma izni
                        EXECUTE format('GRANT SELECT ON ALL TABLES IN SCHEMA public TO %I', '{db_user}');
                        
                        -- Tüm diziler için kullanım izni
                        EXECUTE format('GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO %I', '{db_user}');
                    END $$;
                    """)
                    
                    logger.info("Alternatif yetkilendirme uygulandı. Tekrar test ediliyor...")
                    
                    # Yeniden test et
                    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
                    
                    if result.returncode == 0:
                        logger.info("İkinci pg_dump testi başarılı! Alternatif izinler çalışıyor.")
                    else:
                        logger.error(f"İkinci pg_dump testi de başarısız! Hata: {result.stderr}")
        except Exception as e:
            logger.error(f"pg_dump testi sırasında hata: {str(e)}")
        
        # Bağlantıyı kapat
        cursor.close()
        conn.close()
        logger.info("Yedekleme izinleri düzeltme işlemi tamamlandı")
        
    except Exception as e:
        logger.error(f"Genel hata: {str(e)}")

if __name__ == "__main__":
    fix_backup_permissions() 