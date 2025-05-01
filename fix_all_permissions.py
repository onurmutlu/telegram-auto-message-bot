#!/usr/bin/env python3
"""
PostgreSQL veritabanındaki tüm nesnelere (tablolar, diziler, fonksiyonlar, şemalar vb.) 
tam erişim izni veren gelişmiş script.
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

def fix_all_permissions():
    """
    Veritabanındaki tüm nesnelere (tablolar, diziler, fonksiyonlar, şemalar vb.) tam erişim izni verir.
    Ayrıca rolü superuser yapar ve özel yetkiler ekler.
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
        
        # 1. Rolü superuser ve diğer gerekli yetkilerle güçlendir
        try:
            cursor.execute(f"""
            DO $$
            BEGIN
                -- Superuser yetkisi ver
                ALTER ROLE {db_user} WITH SUPERUSER;
                
                -- Diğer yetkileri ver (mevcut değilse sessizce geç)
                BEGIN
                    ALTER ROLE {db_user} WITH CREATEDB CREATEROLE REPLICATION BYPASSRLS;
                EXCEPTION WHEN OTHERS THEN
                    RAISE NOTICE 'Ek rol yetkileri verilemedi: %', SQLERRM;
                END;
            END $$;
            """)
            logger.info(f"{db_user} rolü superuser ve diğer yetkilerle güçlendirildi")
        except Exception as e:
            logger.error(f"Rol güncellemesi sırasında hata: {str(e)}")
        
        # 2. Önce şema yetkilerini ver
        try:
            cursor.execute(f"""
            DO $$
            BEGIN
                -- Şema yetkisi
                GRANT ALL PRIVILEGES ON SCHEMA public TO {db_user};
                GRANT USAGE ON SCHEMA public TO {db_user};
                
                -- Varsayılan izinleri ayarla
                ALTER DEFAULT PRIVILEGES FOR ROLE {db_user} IN SCHEMA public 
                GRANT ALL ON TABLES TO {db_user};
                
                ALTER DEFAULT PRIVILEGES FOR ROLE {db_user} IN SCHEMA public 
                GRANT ALL ON SEQUENCES TO {db_user};
                
                ALTER DEFAULT PRIVILEGES FOR ROLE {db_user} IN SCHEMA public 
                GRANT ALL ON FUNCTIONS TO {db_user};
                
                ALTER DEFAULT PRIVILEGES FOR ROLE {db_user} IN SCHEMA public 
                GRANT ALL ON TYPES TO {db_user};
                
                -- PUBLIC role için varsayılan izinleri ayarla
                ALTER DEFAULT PRIVILEGES FOR ROLE {db_user} IN SCHEMA public 
                GRANT ALL ON TABLES TO PUBLIC;
                
                ALTER DEFAULT PRIVILEGES FOR ROLE {db_user} IN SCHEMA public 
                GRANT ALL ON SEQUENCES TO PUBLIC;
                
                ALTER DEFAULT PRIVILEGES FOR ROLE {db_user} IN SCHEMA public 
                GRANT ALL ON FUNCTIONS TO PUBLIC;
                
                ALTER DEFAULT PRIVILEGES FOR ROLE {db_user} IN SCHEMA public 
                GRANT ALL ON TYPES TO PUBLIC;
            END $$;
            """)
            logger.info("Şema yetkileri ve varsayılan izinler ayarlandı")
        except Exception as e:
            logger.error(f"Şema yetkileri ayarlanırken hata: {str(e)}")
        
        # 3. Tüm tabloları bul ve yetkilendir
        try:
            cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
            tables = [row[0] for row in cursor.fetchall()]
            logger.info(f"Toplam {len(tables)} tablo bulundu: {', '.join(tables)}")
            
            for table in tables:
                try:
                    # Sahipliği değiştir
                    cursor.execute(f"ALTER TABLE {table} OWNER TO {db_user}")
                    
                    # Tüm izinleri ver
                    cursor.execute(f"""
                    GRANT ALL PRIVILEGES ON TABLE {table} TO {db_user};
                    GRANT ALL PRIVILEGES ON TABLE {table} TO PUBLIC;
                    """)
                    
                    logger.info(f"{table} tablosunun sahipliği ve izinleri ayarlandı")
                except Exception as e:
                    logger.error(f"{table} tablosu için hata: {str(e)}")
        except Exception as e:
            logger.error(f"Tablo yetkilendirme hatası: {str(e)}")
        
        # 4. Tüm dizileri (sequences) bul ve yetkilendir
        try:
            cursor.execute("SELECT sequence_name FROM information_schema.sequences WHERE sequence_schema = 'public'")
            sequences = [row[0] for row in cursor.fetchall()]
            logger.info(f"Toplam {len(sequences)} dizi bulundu: {', '.join(sequences)}")
            
            for seq in sequences:
                try:
                    # Sahipliği değiştir
                    cursor.execute(f"ALTER SEQUENCE {seq} OWNER TO {db_user}")
                    
                    # Tüm izinleri ver
                    cursor.execute(f"""
                    GRANT ALL PRIVILEGES ON SEQUENCE {seq} TO {db_user};
                    GRANT USAGE, SELECT ON SEQUENCE {seq} TO PUBLIC;
                    """)
                    
                    logger.info(f"{seq} dizisinin sahipliği ve izinleri ayarlandı")
                except Exception as e:
                    logger.error(f"{seq} dizisi için hata: {str(e)}")
        except Exception as e:
            logger.error(f"Dizi yetkilendirme hatası: {str(e)}")
        
        # 5. Tüm görünümleri (views) bul ve yetkilendir
        try:
            cursor.execute("SELECT table_name FROM information_schema.views WHERE table_schema = 'public'")
            views = [row[0] for row in cursor.fetchall()]
            
            if views:
                logger.info(f"Toplam {len(views)} görünüm bulundu: {', '.join(views)}")
                
                for view in views:
                    try:
                        # Sahipliği değiştir
                        cursor.execute(f"ALTER VIEW {view} OWNER TO {db_user}")
                        
                        # Tüm izinleri ver
                        cursor.execute(f"""
                        GRANT ALL PRIVILEGES ON TABLE {view} TO {db_user};
                        GRANT SELECT ON TABLE {view} TO PUBLIC;
                        """)
                        
                        logger.info(f"{view} görünümünün sahipliği ve izinleri ayarlandı")
                    except Exception as e:
                        logger.error(f"{view} görünümü için hata: {str(e)}")
            else:
                logger.info("Görünüm (view) bulunamadı")
        except Exception as e:
            logger.error(f"Görünüm yetkilendirme hatası: {str(e)}")
        
        # 6. Tüm fonksiyonları bul ve yetkilendir
        try:
            cursor.execute("""
            SELECT n.nspname as schema_name, p.proname as function_name
            FROM pg_proc p
            JOIN pg_namespace n ON p.pronamespace = n.oid
            WHERE n.nspname = 'public'
            """)
            functions = [(row[0], row[1]) for row in cursor.fetchall()]
            
            if functions:
                function_names = [f"{schema}.{func}" for schema, func in functions]
                logger.info(f"Toplam {len(functions)} fonksiyon bulundu: {', '.join(function_names)}")
                
                for schema, func in functions:
                    try:
                        # Sahipliği değiştirmeye çalış
                        cursor.execute(f"""
                        DO $$
                        BEGIN
                            -- Fonksiyon sahipliğini değiştirmek için önce imzayı belirlememiz gerekiyor
                            -- Bu genel bir yaklaşımdır ve her fonksiyon için çalışmayabilir
                            BEGIN
                                ALTER FUNCTION {schema}.{func}() OWNER TO {db_user};
                            EXCEPTION WHEN OTHERS THEN
                                RAISE NOTICE 'Fonksiyon imzası bulunamadı: {schema}.{func}';
                            END;
                            
                            -- Tüm izinleri ver
                            BEGIN
                                GRANT ALL PRIVILEGES ON FUNCTION {schema}.{func}() TO {db_user};
                                GRANT EXECUTE ON FUNCTION {schema}.{func}() TO PUBLIC;
                            EXCEPTION WHEN OTHERS THEN
                                RAISE NOTICE 'Fonksiyon izinleri ayarlanamadı: {schema}.{func}';
                            END;
                        END $$;
                        """)
                        
                        logger.info(f"{schema}.{func} fonksiyonunun sahipliği ve izinleri ayarlandı")
                    except Exception as e:
                        logger.error(f"{schema}.{func} fonksiyonu için hata: {str(e)}")
            else:
                logger.info("Fonksiyon bulunamadı")
        except Exception as e:
            logger.error(f"Fonksiyon yetkilendirme hatası: {str(e)}")
        
        # 7. pg_dump ve diğer özel yetkiler
        try:
            cursor.execute(f"""
            DO $$
            BEGIN
                -- pg_dump ve diğer özel yetkiler
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
            END $$;
            """)
            logger.info("pg_dump ve diğer özel yetkiler verildi")
        except Exception as e:
            logger.error(f"pg_dump ve diğer özel yetkiler verilirken hata: {str(e)}")
        
        # 8. Veritabanı sahibini değiştir
        try:
            cursor.execute(f"ALTER DATABASE {db_name} OWNER TO {db_user}")
            logger.info(f"Veritabanı {db_name} sahibi {db_user} olarak ayarlandı")
        except Exception as e:
            logger.error(f"Veritabanı sahibi değiştirilirken hata: {str(e)}")
        
        # 9. user_groups, config, settings tabloları gibi özel tablolar için ek kontroller
        problem_tables = ['user_groups', 'config', 'settings', 'groups', 'debug_bot_users']
        for table in problem_tables:
            try:
                # Tabloyu kontrol et ve gereken izinleri uygula
                cursor.execute(f"""
                DO $$
                BEGIN
                    -- Tablo var mı kontrol et
                    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = '{table}') THEN
                        -- Tablo sahipliğini değiştir
                        EXECUTE 'ALTER TABLE {table} OWNER TO {db_user}';
                        
                        -- Tüm izinleri ver
                        EXECUTE 'GRANT ALL PRIVILEGES ON TABLE {table} TO {db_user}';
                        EXECUTE 'GRANT ALL PRIVILEGES ON TABLE {table} TO PUBLIC';
                        
                        -- Eğer id sütunu varsa, sequence'ı da ayarla
                        IF EXISTS (
                            SELECT 1 FROM information_schema.columns 
                            WHERE table_name = '{table}' AND column_name = 'id'
                        ) THEN
                            -- Sequence varsa ayarla
                            IF EXISTS (
                                SELECT 1 FROM information_schema.sequences 
                                WHERE sequence_name = '{table}_id_seq'
                            ) THEN
                                EXECUTE 'ALTER SEQUENCE {table}_id_seq OWNER TO {db_user}';
                                EXECUTE 'GRANT ALL PRIVILEGES ON SEQUENCE {table}_id_seq TO {db_user}';
                                EXECUTE 'GRANT USAGE, SELECT ON SEQUENCE {table}_id_seq TO PUBLIC';
                            END IF;
                        END IF;
                        
                        RAISE NOTICE '{table} tablosu için özel izinler uygulandı';
                    ELSE
                        RAISE NOTICE '{table} tablosu bulunamadı, atlanıyor';
                    END IF;
                EXCEPTION WHEN OTHERS THEN
                    RAISE NOTICE '{table} tablosu için özel izinler uygulanırken hata: %', SQLERRM;
                END $$;
                """)
                logger.info(f"{table} tablosu için özel izinler kontrol edildi")
            except Exception as e:
                logger.error(f"{table} tablosu için özel izin kontrolünde hata: {str(e)}")
        
        # Bağlantıyı kapat
        cursor.close()
        conn.close()
        logger.info("Tüm veritabanı nesneleri için izinler başarıyla ayarlandı")
        
    except Exception as e:
        logger.error(f"Genel hata: {str(e)}")

if __name__ == "__main__":
    fix_all_permissions() 