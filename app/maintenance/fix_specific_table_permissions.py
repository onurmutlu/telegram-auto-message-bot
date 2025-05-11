#!/usr/bin/env python3
"""
PostgreSQL veritabanındaki belirli sorunlu tabloların izinlerini düzeltmeye odaklanan script.
Özellikle pg_dump sırasında izin hatası veren "debug_bot_users", "config", "user_groups" gibi 
tabloları yetkilendirmeye odaklanır.
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

# İzin verme işlevini daha güçlü hale getirmek için bir fonksiyon
def grant_full_permissions(cursor, table_name):
    """
    Belirli bir tabloya ve ilişkili diziye tam yetki ver ve sahipliğini değiştir.
    Bu işlemi birden çok yöntemle dener.
    
    Args:
        cursor: Veritabanı cursor nesnesi
        table_name: Yetkilendirme yapılacak tablo adı
    """
    try:
        # 1. Önce tabloyu kontrol et
        cursor.execute(f"""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables WHERE table_name = '{table_name}'
        )
        """)
        table_exists = cursor.fetchone()[0]
        
        if not table_exists:
            logger.warning(f"Tablo bulunamadı: {table_name}, atlanıyor")
            return
        
        # 2. Tablo sahipliğini birkaç farklı şekilde değiştirmeyi dene
        try:
            # Yöntem 1: Doğrudan sahiplik değiştirme
            cursor.execute(f"ALTER TABLE {table_name} OWNER TO {db_user}")
            logger.info(f"{table_name} tablosunun sahipliği {db_user} olarak değiştirildi (Yöntem 1)")
        except Exception as e:
            logger.warning(f"Sahiplik değiştirme başarısız (Yöntem 1): {str(e)}")
            
            try:
                # Yöntem 2: Format kullanarak
                cursor.execute(f"""
                DO $$
                BEGIN
                    EXECUTE format('ALTER TABLE %I OWNER TO %I', '{table_name}', '{db_user}');
                EXCEPTION WHEN OTHERS THEN
                    RAISE NOTICE 'Sahiplik değiştirme başarısız (Yöntem 2): %', SQLERRM;
                END $$;
                """)
                logger.info(f"{table_name} tablosunun sahipliği {db_user} olarak değiştirildi (Yöntem 2)")
            except Exception as e2:
                logger.warning(f"Sahiplik değiştirme başarısız (Yöntem 2): {str(e2)}")
                
                try:
                    # Yöntem 3: Superuser yetkisi vererek
                    cursor.execute(f"""
                    DO $$
                    BEGIN
                        ALTER ROLE {db_user} WITH SUPERUSER;
                        EXECUTE format('ALTER TABLE %I OWNER TO %I', '{table_name}', '{db_user}');
                    EXCEPTION WHEN OTHERS THEN
                        RAISE NOTICE 'Sahiplik değiştirme başarısız (Yöntem 3): %', SQLERRM;
                    END $$;
                    """)
                    logger.info(f"{table_name} tablosunun sahipliği {db_user} olarak değiştirildi (Yöntem 3)")
                except Exception as e3:
                    logger.error(f"{table_name} tablosunun sahipliği değiştirilemedi: {str(e3)}")
        
        # 3. Tüm yetkileri ver (birkaç farklı şekilde)
        # Yöntem 1
        cursor.execute(f"""
        DO $$
        BEGIN
            -- Doğrudan yetki
            GRANT ALL PRIVILEGES ON TABLE {table_name} TO {db_user};
            
            -- PUBLIC rolüne yetki
            GRANT ALL PRIVILEGES ON TABLE {table_name} TO PUBLIC;
            
            -- Daha ayrıntılı yetkiler
            GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER ON TABLE {table_name} TO {db_user};
            GRANT SELECT ON TABLE {table_name} TO PUBLIC;
        EXCEPTION WHEN OTHERS THEN
            RAISE NOTICE 'Yetki verme başarısız (Yöntem 1): %', SQLERRM;
        END $$;
        """)
        
        # Yöntem 2
        cursor.execute(f"""
        DO $$
        BEGIN
            -- Format kullanarak yetki verme
            EXECUTE format('GRANT ALL PRIVILEGES ON TABLE %I TO %I', '{table_name}', '{db_user}');
            EXECUTE format('GRANT SELECT ON TABLE %I TO PUBLIC', '{table_name}');
        EXCEPTION WHEN OTHERS THEN
            RAISE NOTICE 'Yetki verme başarısız (Yöntem 2): %', SQLERRM;
        END $$;
        """)
        
        logger.info(f"{table_name} tablosuna tüm yetkiler verildi")
        
        # 4. İlişkili dizi (sequence) yetkilerini ayarla
        cursor.execute(f"""
        DO $$
        BEGIN
            -- İlgili sequence var mı?
            IF EXISTS (
                SELECT 1 FROM information_schema.sequences WHERE sequence_name = '{table_name}_id_seq'
            ) THEN
                -- Sahiplik değiştir
                EXECUTE format('ALTER SEQUENCE %I OWNER TO %I', '{table_name}_id_seq', '{db_user}');
                
                -- Yetkiler ver
                EXECUTE format('GRANT ALL PRIVILEGES ON SEQUENCE %I TO %I', '{table_name}_id_seq', '{db_user}');
                EXECUTE format('GRANT USAGE, SELECT ON SEQUENCE %I TO PUBLIC', '{table_name}_id_seq');
                
                RAISE NOTICE '{table_name}_id_seq dizisi için yetkiler verildi';
            END IF;
        EXCEPTION WHEN OTHERS THEN
            RAISE NOTICE 'Dizi yetkileri verilemedi: %', SQLERRM;
        END $$;
        """)
        
        logger.info(f"{table_name}_id_seq dizisi için (varsa) yetkiler verildi")
        
    except Exception as e:
        logger.error(f"{table_name} tablosu için yetki işlemlerinde genel hata: {str(e)}")

def fix_specific_tables():
    """
    Özellikle sorun çıkaran belirli tabloların yetkilendirmelerini düzeltir.
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
        
        # 1. Rolü superuser olarak güçlendir
        try:
            cursor.execute(f"ALTER ROLE {db_user} WITH SUPERUSER;")
            logger.info(f"{db_user} rolü superuser olarak ayarlandı")
        except Exception as e:
            logger.error(f"Superuser rolü ayarlanırken hata: {str(e)}")
        
        # 2. Bu tablolar özellikle sorun yaratıyor, öncelikle bunları düzelt
        problem_tables = [
            "debug_bot_users",
            "config", 
            "user_groups", 
            "user_group_relation",
            "user_group_relation_backup",
            "user_groups_backup", 
            "groups",
            "groups_backup", 
            "settings", 
            "migrations",
            "user_group_activity"
        ]
        
        for table in problem_tables:
            logger.info(f"'{table}' tablosu için özel izin ayarları yapılıyor...")
            grant_full_permissions(cursor, table)
        
        # 3. Şimdi tüm tabloları bul ve kontrol et
        cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        all_tables = [row[0] for row in cursor.fetchall()]
        
        # Diğer tabloları da yetkilendirme kontrolüne tabi tut (ama öncelikli değil)
        other_tables = [t for t in all_tables if t not in problem_tables]
        for table in other_tables:
            logger.info(f"'{table}' tablosu için genel izin ayarları yapılıyor...")
            grant_full_permissions(cursor, table)
        
        # 4. pg_dump için özel yetkiler
        try:
            cursor.execute(f"""
            DO $$
            BEGIN
                -- pg_dump ve yedekleme için özel yetkiler
                BEGIN
                    GRANT pg_execute_server_program TO {db_user};
                EXCEPTION WHEN OTHERS THEN
                    RAISE NOTICE 'pg_execute_server_program yetkisi verilemedi: %', SQLERRM;
                END;
                
                BEGIN
                    GRANT rds_superuser TO {db_user};
                EXCEPTION WHEN OTHERS THEN
                    RAISE NOTICE 'rds_superuser yetkisi verilemedi: %', SQLERRM;
                END;
                
                BEGIN
                    GRANT pg_read_all_data TO {db_user};
                    GRANT pg_write_all_data TO {db_user};
                EXCEPTION WHEN OTHERS THEN
                    RAISE NOTICE 'pg_read/write_all_data yetkisi verilemedi: %', SQLERRM;
                END;
                
                BEGIN
                    ALTER ROLE {db_user} WITH CREATEDB CREATEROLE REPLICATION BYPASSRLS;
                EXCEPTION WHEN OTHERS THEN
                    RAISE NOTICE 'Ek rol yetkileri verilemedi: %', SQLERRM;
                END;
            END $$;
            """)
            logger.info("pg_dump için özel yetkiler verildi")
        except Exception as e:
            logger.error(f"pg_dump yetkileri verilirken hata: {str(e)}")
        
        # 5. Şema düzeyinde yetkiler
        try:
            cursor.execute(f"""
            DO $$
            BEGIN
                -- Şema yetkisi
                GRANT ALL PRIVILEGES ON SCHEMA public TO {db_user};
                GRANT USAGE ON SCHEMA public TO {db_user};
                
                -- Tüm tablolar için okuma yetkileri
                GRANT SELECT ON ALL TABLES IN SCHEMA public TO {db_user};
                
                -- Tüm diziler için kullanım yetkileri
                GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO {db_user};
                
                -- Varsayılan izinler
                ALTER DEFAULT PRIVILEGES FOR ROLE {db_user} IN SCHEMA public 
                GRANT ALL ON TABLES TO {db_user};
                
                ALTER DEFAULT PRIVILEGES FOR ROLE {db_user} IN SCHEMA public 
                GRANT ALL ON SEQUENCES TO {db_user};
            EXCEPTION WHEN OTHERS THEN
                RAISE NOTICE 'Şema yetkileri verilemedi: %', SQLERRM;
            END $$;
            """)
            logger.info("Şema düzeyinde yetkiler verildi")
        except Exception as e:
            logger.error(f"Şema yetkileri verilirken hata: {str(e)}")
        
        # 6. Veritabanı sahipliğini değiştir
        try:
            cursor.execute(f"ALTER DATABASE {db_name} OWNER TO {db_user}")
            logger.info(f"Veritabanı {db_name} sahibi {db_user} olarak ayarlandı")
        except Exception as e:
            logger.error(f"Veritabanı sahipliği değiştirilirken hata: {str(e)}")
        
        # 7. pg_dump ile yedekleme testi yap
        try:
            # Çevre değişkenlerini ayarla
            env = os.environ.copy()
            env['PGPASSWORD'] = db_password
            
            # Sadece şema sorgusunu göstermeye ayarlı pg_dump
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
            
            logger.info("pg_dump testi gerçekleştiriliyor...")
            result = subprocess.run(cmd, capture_output=True, text=True, env=env)
            
            if result.returncode == 0:
                logger.info("pg_dump testi başarılı! İzinler düzgün ayarlanmış")
            else:
                # Hata durumunda hala hangi tablo için sorun olduğunu kontrol et
                error_output = result.stderr
                logger.error(f"pg_dump testi başarısız: {error_output}")
                
                # Hangi tablolar için izin hatası var?
                if "permission denied for" in error_output:
                    table_match = error_output.split("permission denied for")[1].strip().split(" ")[1]
                    if table_match:
                        logger.warning(f"İzin hatası hala devam ediyor: {table_match}")
                        
                        # Sorunlu tabloyu tekrar yetkilendir
                        logger.info(f"Sorunlu {table_match} tablosu için yeniden yetkilendirme yapılıyor...")
                        grant_full_permissions(cursor, table_match)
                        
                        # Tekrar test et
                        logger.info("Son bir pg_dump testi daha yapılıyor...")
                        result = subprocess.run(cmd, capture_output=True, text=True, env=env)
                        
                        if result.returncode == 0:
                            logger.info("İkinci pg_dump testi başarılı! Tüm izinler düzgün ayarlandı")
                        else:
                            logger.error(f"İkinci pg_dump testi de başarısız: {result.stderr}")
        except Exception as e:
            logger.error(f"pg_dump test hatası: {str(e)}")
        
        # Bağlantıyı kapat
        cursor.close()
        conn.close()
        logger.info("Sorunlu tabloların izin düzeltme işlemi tamamlandı")
        
    except Exception as e:
        logger.error(f"Genel hata: {str(e)}")

if __name__ == "__main__":
    fix_specific_tables() 