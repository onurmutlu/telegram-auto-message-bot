"""
# ============================================================================ #
# Dosya: migrate_db.py
# Yol: /Users/siyahkare/code/telegram-bot/database/migrate_db.py
# İşlev: users.db veritabanından bot.db veritabanına veri taşıma
#
# © 2025 SiyahKare Yazılım - Tüm Hakları Saklıdır
# ============================================================================ #
"""

import sqlite3
import os
import shutil
from datetime import datetime
import logging

# Logging ayarları
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Yollar
OLD_DB_PATH = 'data/users.db'
NEW_DB_PATH = 'data/bot.db'
BACKUP_DIR = 'data/backups'

def migrate_database():
    """
    users.db veritabanından bot.db veritabanına veri taşır.
    """
    # Yedek dizini oluştur
    os.makedirs(BACKUP_DIR, exist_ok=True)
    
    # Eğer eski veritabanı yoksa işlemi sonlandır
    if not os.path.exists(OLD_DB_PATH):
        logger.error(f"Eski veritabanı bulunamadı: {OLD_DB_PATH}")
        return False
    
    # Eğer yeni veritabanı varsa yedekle
    if os.path.exists(NEW_DB_PATH):
        backup_file = f"{BACKUP_DIR}/bot_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        shutil.copy2(NEW_DB_PATH, backup_file)
        logger.info(f"Mevcut bot.db yedeklendi: {backup_file}")
    
    try:
        # Eski veritabanına bağlan
        old_conn = sqlite3.connect(OLD_DB_PATH)
        old_conn.row_factory = sqlite3.Row
        old_cursor = old_conn.cursor()
        
        # Yeni veritabanına bağlan
        new_conn = sqlite3.connect(NEW_DB_PATH)
        new_conn.row_factory = sqlite3.Row
        new_cursor = new_conn.cursor()
        
        # Yeni tablolar oluştur (UserDatabase sınıfının _create_tables metoduna benzer şekilde)
        new_cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            message_count INTEGER DEFAULT 0,
            last_invited TIMESTAMP,
            invite_count INTEGER DEFAULT 0,
            source_group TEXT,
            is_active BOOLEAN DEFAULT 1,
            blocked INTEGER DEFAULT 0,
            invited INTEGER DEFAULT 0,
            first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_admin INTEGER DEFAULT 0,
            is_bot BOOLEAN DEFAULT 0
        )
        ''')
        
        new_cursor.execute('''
        CREATE TABLE IF NOT EXISTS group_stats (
            group_id INTEGER PRIMARY KEY,
            group_name TEXT,
            message_count INTEGER DEFAULT 0,
            last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            avg_messages_per_hour REAL DEFAULT 0,
            last_message_sent TIMESTAMP,
            optimal_interval INTEGER DEFAULT 60,
            is_active BOOLEAN DEFAULT 1
        )
        ''')
        
        new_cursor.execute('''
        CREATE TABLE IF NOT EXISTS error_groups (
            group_id INTEGER PRIMARY KEY,
            group_title TEXT,
            error_reason TEXT,
            last_error_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            retry_after TIMESTAMP
        )
        ''')

        # Yeni ve eski şema arasındaki farkları ele al
        
        # Tablo listesini al
        old_cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        old_tables = [table[0] for table in old_cursor.fetchall()]
        
        # Her tablo için işlem yap
        for table in old_tables:
            if table in ['sqlite_sequence', 'sqlite_stat1']:
                continue  # Sistem tablolarını atla
                
            logger.info(f"{table} tablosu veri taşıma işlemi başladı")
            
            # Tablo var mı kontrol et
            old_cursor.execute(f"PRAGMA table_info({table})")
            old_columns = {col[1]: col[2] for col in old_cursor.fetchall()}
            
            # Eğer yeni veritabanında bu tablo yoksa, oluştur
            new_cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
            if not new_cursor.fetchone() and table not in ['users', 'group_stats', 'error_groups']:
                # Tablo oluştur
                column_defs = [f"{name} {type_}" for name, type_ in old_columns.items()]
                create_sql = f"CREATE TABLE IF NOT EXISTS {table} ({', '.join(column_defs)})"
                new_cursor.execute(create_sql)
                logger.info(f"Yeni tablo oluşturuldu: {table}")
            
            # Yeni veritabanında tablonun yapısını al
            new_cursor.execute(f"PRAGMA table_info({table})")
            new_columns = {col[1]: col[2] for col in new_cursor.fetchall()}
            
            # Verileri taşı
            old_cursor.execute(f"SELECT * FROM {table}")
            records = old_cursor.fetchall()
            
            for record in records:
                # Eski sütun isimlerini al
                old_col_names = [col[0] for col in old_cursor.description]
                
                # Eski ve yeni veritabanında ortak olan sütunları bul
                common_columns = [col for col in old_col_names if col in new_columns]
                
                # Ortak sütunlardaki verileri al
                common_values = [record[old_col_names.index(col)] for col in common_columns]
                
                # INSERT sorgusu oluştur
                if common_columns:
                    sql = f"INSERT OR REPLACE INTO {table} ({', '.join(common_columns)}) VALUES ({', '.join(['?' for _ in common_columns])})"
                    try:
                        new_cursor.execute(sql, common_values)
                    except sqlite3.Error as e:
                        logger.error(f"Veri taşıma hatası ({table}): {str(e)}")
            
            logger.info(f"{len(records)} kayıt {table} tablosuna taşındı")
        
        # Değişiklikleri kaydet
        new_conn.commit()
        
        # Bağlantıları kapat
        old_conn.close()
        new_conn.close()
        
        logger.info("Veritabanı taşıma işlemi başarıyla tamamlandı.")
        return True
        
    except Exception as e:
        logger.error(f"Veritabanı taşıma hatası: {str(e)}")
        return False

if __name__ == "__main__":
    migrate_database()