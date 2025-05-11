import os
import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor
import logging

load_dotenv()

logger = logging.getLogger(__name__)

# Bağlantı bilgilerini al
db_connection = os.getenv("DB_CONNECTION")
print(f"Bağlantı bilgisi: {db_connection}")

class Database:
    def __init__(self, db_path):
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        
    def connect(self):
        try:
            # PostgreSQL bağlantısı oluştur
            self.conn = psycopg2.connect(self.db_path)
            self.conn.autocommit = True  # Otomatik commit
            self.cursor = self.conn.cursor(cursor_factory=RealDictCursor)
            
            # Test sorgusu
            self.cursor.execute("SELECT 1")
            logger.info("PostgreSQL bağlantısı başarılı")
            return True
        except Exception as e:
            logger.error(f"Veritabanı bağlantı hatası: {str(e)}")
            return False
    
    async def get_target_groups(self):
        try:
            self.cursor.execute('''
                SELECT * FROM groups WHERE is_target = TRUE
            ''')
            groups = self.cursor.fetchall()
            return groups
        except Exception as e:
            logger.error(f"Grupları getirme hatası: {str(e)}")
            return []

try:
    # Bağlantı kur
    conn = psycopg2.connect(db_connection)
    cursor = conn.cursor()
    
    # Test sorgusu
    cursor.execute("SELECT 1")
    result = cursor.fetchone()
    print(f"Bağlantı başarılı, sonuç: {result}")
    
    # Tabloları oluştur
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS groups (
        group_id BIGINT PRIMARY KEY,
        name TEXT,
        join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_message TIMESTAMP,
        message_count INTEGER DEFAULT 0,
        member_count INTEGER DEFAULT 0,
        error_count INTEGER DEFAULT 0,
        last_error TEXT,
        is_active BOOLEAN DEFAULT TRUE,
        permanent_error BOOLEAN DEFAULT FALSE,
        is_target BOOLEAN DEFAULT TRUE,
        retry_after TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    conn.commit()
    print("Tablolar oluşturuldu")
    
    # Bağlantıyı kapat
    conn.close()
    
except Exception as e:
    print(f"Hata: {str(e)}")
