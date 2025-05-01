#!/usr/bin/env python3
"""
SQLite veritabanından PostgreSQL'e veri taşıma aracı.
Bu script, mevcut SQLite veritabanını PostgreSQL'e aktarır.
"""

import os
import sys
import logging
import json
import sqlite3
import psycopg2
import psycopg2.extras
from datetime import datetime
from dotenv import load_dotenv

# .env dosyasını yükle
load_dotenv()

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("sqlite_to_postgres_migration.log")
    ]
)
logger = logging.getLogger("SQLiteToPostgres")

# PostgreSQL bağlantı bilgileri
DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")
DB_NAME = os.getenv("POSTGRES_DB", "telegram_bot")
DB_USER = os.getenv("POSTGRES_USER", "postgres")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")

# SQLite veritabanı
SQLITE_PATH = os.getenv("SQLITE_PATH", os.path.join("data", "users.db"))

def get_pg_connection():
    """PostgreSQL veritabanına bağlantı oluşturur"""
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            cursor_factory=psycopg2.extras.DictCursor
        )
        logger.info("PostgreSQL veritabanına bağlantı başarılı")
        return conn
    except Exception as e:
        logger.error(f"PostgreSQL bağlantı hatası: {e}")
        return None

def get_sqlite_connection():
    """SQLite veritabanına bağlantı oluşturur"""
    try:
        conn = sqlite3.connect(SQLITE_PATH)
        conn.row_factory = sqlite3.Row
        logger.info(f"SQLite veritabanına bağlantı başarılı: {SQLITE_PATH}")
        return conn
    except Exception as e:
        logger.error(f"SQLite bağlantı hatası: {e}")
        return None

def create_pg_tables(pg_conn):
    """PostgreSQL'de gerekli tabloları oluşturur"""
    try:
        cursor = pg_conn.cursor()
        
        # Kullanıcılar tablosu
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id BIGINT PRIMARY KEY,
            username VARCHAR(255),
            first_name VARCHAR(255),
            last_name VARCHAR(255),
            is_active BOOLEAN DEFAULT TRUE,
            last_active TIMESTAMP,
            join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_admin BOOLEAN DEFAULT FALSE,
            is_bot BOOLEAN DEFAULT FALSE,
            is_premium BOOLEAN DEFAULT FALSE,
            language_code VARCHAR(10),
            activity_count INTEGER DEFAULT 0,
            status VARCHAR(20) DEFAULT 'active'
        );
        """)
        
        # Gruplar tablosu
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS groups (
            id BIGINT PRIMARY KEY,
            title VARCHAR(255),
            username VARCHAR(255),
            join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            member_count INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT TRUE,
            last_activity TIMESTAMP,
            error_count INTEGER DEFAULT 0,
            last_error TIMESTAMP,
            permanent_error BOOLEAN DEFAULT FALSE
        );
        """)
        
        # Kullanıcı aktivite log tablosu
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_activity_log (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            activity_type VARCHAR(50) NOT NULL,
            activity_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            details JSONB
        );
        """)
        
        # İndeksleri oluştur
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_active ON users (is_active)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_last_active ON users (last_active)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_groups_active ON groups (is_active)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_activity_user ON user_activity_log (user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_activity_type ON user_activity_log (activity_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_activity_time ON user_activity_log (activity_time)")
        
        pg_conn.commit()
        logger.info("PostgreSQL tabloları başarıyla oluşturuldu")
        return True
    except Exception as e:
        logger.error(f"PostgreSQL tablo oluşturma hatası: {e}")
        pg_conn.rollback()
        return False

def migrate_users(sqlite_conn, pg_conn):
    """Kullanıcıları SQLite'dan PostgreSQL'e taşır"""
    try:
        sqlite_cursor = sqlite_conn.cursor()
        pg_cursor = pg_conn.cursor()
        
        sqlite_cursor.execute("SELECT * FROM users")
        users = sqlite_cursor.fetchall()
        
        migrated_count = 0
        for user in users:
            user_dict = dict(user)
            
            # Tarih alanlarını kontrol et
            for date_field in ['last_active', 'join_date']:
                if date_field in user_dict and user_dict[date_field]:
                    try:
                        # SQLite'daki tarih formatını kontrol et
                        if isinstance(user_dict[date_field], str):
                            user_dict[date_field] = datetime.fromisoformat(user_dict[date_field].replace('Z', '+00:00'))
                    except Exception as e:
                        logger.warning(f"Tarih alanı dönüştürme hatası ({date_field}): {e}")
                        user_dict[date_field] = None
            
            # Boolean alanları kontrol et
            for bool_field in ['is_active', 'is_admin', 'is_bot', 'is_premium']:
                if bool_field in user_dict:
                    user_dict[bool_field] = bool(user_dict[bool_field])
            
            # Kullanıcıyı PostgreSQL'e ekle veya güncelle
            pg_cursor.execute("""
            INSERT INTO users (
                id, username, first_name, last_name, is_active, last_active, join_date, 
                is_admin, is_bot, is_premium, language_code, activity_count, status
            ) VALUES (
                %(id)s, %(username)s, %(first_name)s, %(last_name)s, %(is_active)s, 
                %(last_active)s, %(join_date)s, %(is_admin)s, %(is_bot)s, %(is_premium)s, 
                %(language_code)s, %(activity_count)s, %(status)s
            ) ON CONFLICT (id) DO UPDATE SET
                username = EXCLUDED.username,
                first_name = EXCLUDED.first_name,
                last_name = EXCLUDED.last_name,
                is_active = EXCLUDED.is_active,
                last_active = EXCLUDED.last_active,
                is_admin = EXCLUDED.is_admin,
                is_bot = EXCLUDED.is_bot,
                is_premium = EXCLUDED.is_premium,
                language_code = EXCLUDED.language_code,
                activity_count = EXCLUDED.activity_count,
                status = EXCLUDED.status
            """, user_dict)
            
            migrated_count += 1
            if migrated_count % 100 == 0:
                pg_conn.commit()
                logger.info(f"{migrated_count} kullanıcı taşındı...")
        
        pg_conn.commit()
        logger.info(f"Toplam {migrated_count} kullanıcı başarıyla taşındı")
        return migrated_count
    except Exception as e:
        logger.error(f"Kullanıcı taşıma hatası: {e}")
        pg_conn.rollback()
        return 0

def migrate_groups(sqlite_conn, pg_conn):
    """Grupları SQLite'dan PostgreSQL'e taşır"""
    try:
        sqlite_cursor = sqlite_conn.cursor()
        pg_cursor = pg_conn.cursor()
        
        sqlite_cursor.execute("SELECT * FROM groups")
        groups = sqlite_cursor.fetchall()
        
        migrated_count = 0
        for group in groups:
            group_dict = dict(group)
            
            # Tarih alanlarını kontrol et
            for date_field in ['join_date', 'last_activity', 'last_error']:
                if date_field in group_dict and group_dict[date_field]:
                    try:
                        if isinstance(group_dict[date_field], str):
                            group_dict[date_field] = datetime.fromisoformat(group_dict[date_field].replace('Z', '+00:00'))
                    except Exception as e:
                        logger.warning(f"Tarih alanı dönüştürme hatası ({date_field}): {e}")
                        group_dict[date_field] = None
            
            # Boolean alanları kontrol et
            for bool_field in ['is_active', 'permanent_error']:
                if bool_field in group_dict:
                    group_dict[bool_field] = bool(group_dict[bool_field])
            
            # Grubu PostgreSQL'e ekle veya güncelle
            pg_cursor.execute("""
            INSERT INTO groups (
                id, title, username, join_date, member_count, is_active, 
                last_activity, error_count, last_error, permanent_error
            ) VALUES (
                %(id)s, %(title)s, %(username)s, %(join_date)s, %(member_count)s, 
                %(is_active)s, %(last_activity)s, %(error_count)s, %(last_error)s, %(permanent_error)s
            ) ON CONFLICT (id) DO UPDATE SET
                title = EXCLUDED.title,
                username = EXCLUDED.username,
                member_count = EXCLUDED.member_count,
                is_active = EXCLUDED.is_active,
                last_activity = EXCLUDED.last_activity,
                error_count = EXCLUDED.error_count,
                last_error = EXCLUDED.last_error,
                permanent_error = EXCLUDED.permanent_error
            """, group_dict)
            
            migrated_count += 1
            if migrated_count % 100 == 0:
                pg_conn.commit()
                logger.info(f"{migrated_count} grup taşındı...")
        
        pg_conn.commit()
        logger.info(f"Toplam {migrated_count} grup başarıyla taşındı")
        return migrated_count
    except Exception as e:
        logger.error(f"Grup taşıma hatası: {e}")
        pg_conn.rollback()
        return 0

def migrate_activity_logs(sqlite_conn, pg_conn):
    """Kullanıcı aktivite loglarını SQLite'dan PostgreSQL'e taşır"""
    try:
        sqlite_cursor = sqlite_conn.cursor()
        pg_cursor = pg_conn.cursor()
        
        # Tablo var mı kontrol et
        sqlite_cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_activity_log'")
        if not sqlite_cursor.fetchone():
            logger.warning("SQLite'da user_activity_log tablosu bulunamadı.")
            return 0
        
        sqlite_cursor.execute("SELECT * FROM user_activity_log")
        logs = sqlite_cursor.fetchall()
        
        migrated_count = 0
        for log in logs:
            log_dict = dict(log)
            
            # Tarih alanını kontrol et
            if 'activity_time' in log_dict and log_dict['activity_time']:
                try:
                    if isinstance(log_dict['activity_time'], str):
                        log_dict['activity_time'] = datetime.fromisoformat(log_dict['activity_time'].replace('Z', '+00:00'))
                except Exception as e:
                    logger.warning(f"Tarih alanı dönüştürme hatası: {e}")
                    log_dict['activity_time'] = datetime.now()
            
            # JSON alanını kontrol et
            details = log_dict.get('details')
            if details:
                try:
                    if isinstance(details, str):
                        details_json = json.loads(details)
                    else:
                        details_json = details
                    log_dict['details'] = json.dumps(details_json)
                except Exception as e:
                    logger.warning(f"JSON alanı dönüştürme hatası: {e}")
                    log_dict['details'] = None
            
            # Aktivite logunu PostgreSQL'e ekle
            pg_cursor.execute("""
            INSERT INTO user_activity_log (
                user_id, activity_type, activity_time, details
            ) VALUES (
                %(user_id)s, %(activity_type)s, %(activity_time)s, %(details)s
            )
            """, {
                'user_id': log_dict.get('user_id'),
                'activity_type': log_dict.get('activity_type'),
                'activity_time': log_dict.get('activity_time'),
                'details': log_dict.get('details')
            })
            
            migrated_count += 1
            if migrated_count % 1000 == 0:
                pg_conn.commit()
                logger.info(f"{migrated_count} aktivite logu taşındı...")
        
        pg_conn.commit()
        logger.info(f"Toplam {migrated_count} aktivite logu başarıyla taşındı")
        return migrated_count
    except Exception as e:
        logger.error(f"Aktivite logu taşıma hatası: {e}")
        pg_conn.rollback()
        return 0

def main():
    """Ana fonksiyon"""
    # SQLite bağlantısı
    sqlite_conn = get_sqlite_connection()
    if not sqlite_conn:
        logger.error("SQLite veritabanına bağlanılamadı!")
        sys.exit(1)
    
    # PostgreSQL bağlantısı
    pg_conn = get_pg_connection()
    if not pg_conn:
        logger.error("PostgreSQL veritabanına bağlanılamadı!")
        sqlite_conn.close()
        sys.exit(1)
    
    try:
        logger.info("Veri taşıma işlemi başlatılıyor...")
        
        # PostgreSQL tablolarını oluştur
        if not create_pg_tables(pg_conn):
            raise Exception("PostgreSQL tabloları oluşturulamadı!")
        
        # Kullanıcıları taşı
        user_count = migrate_users(sqlite_conn, pg_conn)
        logger.info(f"Kullanıcılar taşındı: {user_count}")
        
        # Grupları taşı
        group_count = migrate_groups(sqlite_conn, pg_conn)
        logger.info(f"Gruplar taşındı: {group_count}")
        
        # Aktivite loglarını taşı
        log_count = migrate_activity_logs(sqlite_conn, pg_conn)
        logger.info(f"Aktivite logları taşındı: {log_count}")
        
        logger.info("Veri taşıma işlemi başarıyla tamamlandı!")
        
    except Exception as e:
        logger.error(f"Veri taşıma işlemi hatası: {e}")
        pg_conn.rollback()
    finally:
        sqlite_conn.close()
        pg_conn.close()
        logger.info("Veritabanı bağlantıları kapatıldı")

if __name__ == "__main__":
    main()
