import psycopg2
import os
from urllib.parse import urlparse

# .env'den bağlantı bilgilerini al
from dotenv import load_dotenv
load_dotenv()

def fix_database(verbose=False):
    """
    Veritabanındaki sorunlu tabloları düzeltir.
    
    Args:
        verbose: Ayrıntılı çıktı gösterme
        
    Returns:
        bool: İşlem başarılı ise True
    """
    db_url = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/telegram_bot')

    # Bağlantı parametrelerini ayrıştır
    url = urlparse(db_url)
    db_name = url.path[1:]  # / işaretini kaldır
    db_user = url.username
    db_password = url.password
    db_host = url.hostname
    db_port = url.port or 5432

    if verbose:
        print(f'Bağlantı parametreleri: {db_host}:{db_port}/{db_name}')

    # Bağlantı kur
    try:
        conn = psycopg2.connect(
            dbname=db_name,
            user=db_user,
            password=db_password,
            host=db_host,
            port=db_port
        )
    except Exception as e:
        print(f"Veritabanına bağlanırken hata: {str(e)}")
        return False

    cursor = conn.cursor()

    # Sorunlu tablolar
    tables_to_fix = [
        {
            "name": "messages",
            "create_sql": """
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
            """
        },
        {
            "name": "mining_data",
            "create_sql": """
            CREATE TABLE IF NOT EXISTS mining_data (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                group_id BIGINT,
                group_name TEXT,
                message_count INTEGER DEFAULT 0,
                first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_mining_data_user_id ON mining_data(user_id);
            CREATE INDEX IF NOT EXISTS idx_mining_data_group_id ON mining_data(group_id);
            """
        },
        {
            "name": "mining_logs",
            "create_sql": """
            CREATE TABLE IF NOT EXISTS mining_logs (
                id SERIAL PRIMARY KEY,
                mining_id BIGINT,
                action_type TEXT,
                details TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                success BOOLEAN,
                error TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_mining_logs_mining_id ON mining_logs(mining_id);
            """
        }
    ]

    if verbose:
        print("Veritabanı tabloları düzeltiliyor...")

    for table in tables_to_fix:
        table_name = table["name"]
        create_sql = table["create_sql"]
        
        if verbose:
            print(f"\n-- {table_name} tablosu düzeltiliyor --")
        
        # İlgili tabloyu sil (varsa)
        try:
            cursor.execute(f"DROP TABLE IF EXISTS {table_name} CASCADE")
            conn.commit()
            if verbose:
                print(f"{table_name} tablosu silindi")
        except Exception as e:
            if verbose:
                print(f"{table_name} tablosu silinirken hata: {str(e)}")
            conn.rollback()
        
        # Tabloyu yeniden oluştur
        try:
            cursor.execute(create_sql)
            conn.commit()
            if verbose:
                print(f"{table_name} tablosu oluşturuldu")
        except Exception as e:
            if verbose:
                print(f"{table_name} tablosu oluşturulurken hata: {str(e)}")
            conn.rollback()
        
        # Sequence'ı düzelt
        try:
            cursor.execute(f"ALTER SEQUENCE {table_name}_id_seq OWNER TO {db_user}")
            conn.commit()
            if verbose:
                print(f"{table_name}_id_seq sahipliği düzeltildi")
        except Exception as e:
            if verbose:
                print(f"{table_name}_id_seq sahipliği düzeltilirken hata: {str(e)}")
            conn.rollback()
        
        # Yetkilendirmeleri ayarla
        try:
            cursor.execute(f"GRANT ALL PRIVILEGES ON TABLE {table_name} TO {db_user}")
            cursor.execute(f"GRANT USAGE, SELECT ON SEQUENCE {table_name}_id_seq TO {db_user}")
            conn.commit()
            if verbose:
                print(f"{table_name} tablosu için yetkiler verildi")
        except Exception as e:
            if verbose:
                print(f"{table_name} tablosu için yetkilendirme hatası: {str(e)}")
            conn.rollback()

    # Diğer tüm tablolara yetki ver
    cursor.execute("""
    SELECT tablename FROM pg_tables
    WHERE schemaname = 'public'
    """)
    tables = [row[0] for row in cursor.fetchall()]

    if verbose:
        print("\n-- Tüm tablolara yetki veriliyor --")
    for table in tables:
        try:
            cursor.execute(f"GRANT ALL PRIVILEGES ON TABLE {table} TO {db_user}")
            conn.commit()
            if verbose:
                print(f"{table} tablosu için yetkiler verildi")
        except Exception as e:
            if verbose:
                print(f"{table} tablosu için yetkilendirme hatası: {str(e)}")
            conn.rollback()

    # Tüm sequence'lara yetki ver
    cursor.execute("""
    SELECT sequence_name FROM information_schema.sequences
    WHERE sequence_schema = 'public'
    """)
    sequences = [row[0] for row in cursor.fetchall()]

    if verbose:
        print("\n-- Tüm sequence'lara yetki veriliyor --")
    for sequence in sequences:
        try:
            cursor.execute(f"GRANT USAGE, SELECT ON SEQUENCE {sequence} TO {db_user}")
            conn.commit()
            if verbose:
                print(f"{sequence} için yetkiler verildi")
        except Exception as e:
            if verbose:
                print(f"{sequence} için yetkilendirme hatası: {str(e)}")
            conn.rollback()

    # Bağlantıyı kapat
    cursor.close()
    conn.close()

    if verbose:
        print("\nVeritabanı düzeltme işlemi tamamlandı.")
    
    return True


# Doğrudan çalıştırıldığında
if __name__ == "__main__":
    print(f'Bağlantı parametreleri: {urlparse(os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/telegram_bot")).hostname}:{urlparse(os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/telegram_bot")).port or 5432}/{urlparse(os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/telegram_bot")).path[1:]}')
    fix_database(verbose=True) 