#!/usr/bin/env python3
"""
PostgreSQL veritabanı sahipliğini ve tablo/dizi sahiplik sorunlarını düzelten script.
Bu script, postgres veritabanına superuser olarak bağlanır ve kullanıcıya tüm yetkileri verir.
"""
import os
import subprocess
import logging
import sys
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

def run_psql_command(command, env=None):
    """
    psql komutu çalıştır
    
    Args:
        command (str): Çalıştırılacak SQL komutları
        env (dict): Çevre değişkenleri (opsiyonel)
        
    Returns:
        tuple: (çıktı, hata)
    """
    # PGPASSWORD çevre değişkeni ile şifre gir
    if env is None:
        env = os.environ.copy()
    env['PGPASSWORD'] = db_password
    
    # psql komutunu oluştur
    cmd = [
        'psql',
        f'--host={db_host}',
        f'--port={db_port}',
        f'--username={db_user}',
        f'--dbname={db_name}',
        '--no-password',  # Şifre çevre değişkeni ile verildiği için şifre sormasın
        '--tuples-only',  # Daha temiz çıktı
        '--command', command
    ]
    
    # Komutu çalıştır
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env
        )
        stdout, stderr = process.communicate()
        
        # Çıktıları decode et
        stdout = stdout.decode('utf-8').strip() if stdout else ""
        stderr = stderr.decode('utf-8').strip() if stderr else ""
        
        # Hata varsa log'a yaz
        if stderr:
            logger.error(f"PSQL Hatası: {stderr}")
        
        return stdout, stderr
    except Exception as e:
        logger.error(f"Komut çalıştırma hatası: {str(e)}")
        return "", str(e)

def fix_db_ownership():
    """
    Veritabanı ve tablo sahipliğini değiştirir ve tüm yetkileri verir
    """
    logger.info("Veritabanı sahipliği ve tablo yetkilerini düzeltme işlemi başlıyor...")
    
    # 1. Kullanıcıyı superuser yap
    cmd1 = f"ALTER ROLE {db_user} WITH SUPERUSER;"
    stdout, stderr = run_psql_command(cmd1)
    if not stderr:
        logger.info(f"Kullanıcı {db_user} superuser yapıldı")
    
    # 2. Tüm tabloların sahipliğini değiştir
    cmd2 = """
    DO $$
    DECLARE
        r record;
    BEGIN
        FOR r IN SELECT tablename FROM pg_tables WHERE schemaname = 'public'
        LOOP
            EXECUTE 'ALTER TABLE public.' || quote_ident(r.tablename) || ' OWNER TO ' || quote_ident('%s');
        END LOOP;
    END $$;
    """ % db_user
    stdout, stderr = run_psql_command(cmd2)
    if not stderr:
        logger.info(f"Tüm tabloların sahipliği {db_user} olarak değiştirildi")
    
    # 3. Tüm dizilerin sahipliğini değiştir
    cmd3 = """
    DO $$
    DECLARE
        r record;
    BEGIN
        FOR r IN SELECT sequence_name FROM information_schema.sequences WHERE sequence_schema = 'public'
        LOOP
            EXECUTE 'ALTER SEQUENCE public.' || quote_ident(r.sequence_name) || ' OWNER TO ' || quote_ident('%s');
        END LOOP;
    END $$;
    """ % db_user
    stdout, stderr = run_psql_command(cmd3)
    if not stderr:
        logger.info(f"Tüm dizilerin sahipliği {db_user} olarak değiştirildi")
    
    # 4. Tüm fonksiyonların sahipliğini değiştir
    cmd4 = """
    DO $$
    DECLARE
        r record;
    BEGIN
        FOR r IN SELECT p.proname, n.nspname
                FROM pg_proc p, pg_namespace n
                WHERE p.pronamespace = n.oid AND n.nspname = 'public'
        LOOP
            BEGIN
                EXECUTE 'ALTER FUNCTION public.' || quote_ident(r.proname) || '() OWNER TO ' || quote_ident('%s');
            EXCEPTION WHEN OTHERS THEN
                -- Fonksiyon sahipliği değiştirilemezse devam et
                RAISE NOTICE 'Function %% ownership could not be changed: %%', r.proname, SQLERRM;
            END;
        END LOOP;
    END $$;
    """ % db_user
    
    stdout, stderr = run_psql_command(cmd4)
    if not stderr:
        logger.info(f"Tüm fonksiyonların sahipliği {db_user} olarak değiştirildi")
    
    # 5. Varsayılan yetkileri ayarla
    cmd5 = f"""
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO {db_user};
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO {db_user};
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO {db_user};
    
    -- Şema yetkilerini daha kapsamlı ver
    GRANT ALL PRIVILEGES ON SCHEMA public TO {db_user};
    GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO {db_user};
    GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO {db_user};
    GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO {db_user};
    """
    
    stdout, stderr = run_psql_command(cmd5)
    if not stderr:
        logger.info("Varsayılan yetkiler ayarlandı")
    
    # 6. Veritabanı sahipliğini değiştir
    cmd6 = f"ALTER DATABASE {db_name} OWNER TO {db_user};"
    stdout, stderr = run_psql_command(cmd6)
    if not stderr:
        logger.info(f"Veritabanı {db_name} sahipliği {db_user} olarak değiştirildi")
    
    # 7. pg_dump yetkisi ver
    cmd7 = f"GRANT pg_execute_server_program TO {db_user};"
    stdout, stderr = run_psql_command(cmd7)
    if not stderr:
        logger.info(f"pg_execute_server_program yetkisi {db_user} kullanıcısına verildi")
    
    # Ek olarak groups ve settings tabloları için özel yetkiler ekle
    cmd8 = f"""
    DO $$
    BEGIN
        -- Özellikle problem olan tabloları sıfırdan oluştur
        -- groups tablosu
        CREATE TABLE IF NOT EXISTS public.groups (
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
        
        -- settings tablosu
        CREATE TABLE IF NOT EXISTS public.settings (
            id SERIAL PRIMARY KEY,
            key TEXT UNIQUE NOT NULL,
            value TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        -- Tablolara tam yetki ver
        EXECUTE format('GRANT ALL PRIVILEGES ON TABLE groups TO %I', '{db_user}');
        EXECUTE format('GRANT ALL PRIVILEGES ON TABLE settings TO %I', '{db_user}');
        EXECUTE format('GRANT ALL PRIVILEGES ON SEQUENCE groups_id_seq TO %I', '{db_user}');
        EXECUTE format('GRANT ALL PRIVILEGES ON SEQUENCE settings_id_seq TO %I', '{db_user}');
        
        -- Sahiplikleri değiştir
        EXECUTE format('ALTER TABLE groups OWNER TO %I', '{db_user}');
        EXECUTE format('ALTER TABLE settings OWNER TO %I', '{db_user}');
        EXECUTE format('ALTER SEQUENCE groups_id_seq OWNER TO %I', '{db_user}');
        EXECUTE format('ALTER SEQUENCE settings_id_seq OWNER TO %I', '{db_user}');
    END $$;
    """
    
    stdout, stderr = run_psql_command(cmd8)
    if not stderr:
        logger.info(f"groups ve settings tabloları için özel yetkiler verildi")
    else:
        logger.error(f"groups ve settings tabloları için özel yetki verirken hata: {stderr}")
    
    logger.info("Veritabanı sahipliği ve tablo yetkilerini düzeltme işlemi tamamlandı")

if __name__ == "__main__":
    fix_db_ownership() 