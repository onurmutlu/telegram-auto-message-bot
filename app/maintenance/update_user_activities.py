#!/usr/bin/env python3
"""
Kullanıcı etkinlik tablosunu güncellemek için yardımcı script.
Bu betik veritabanındaki tüm kullanıcıların aktivite kayıtlarını günceller.
"""

import os
import sys
import logging
import time
import traceback
from datetime import datetime, timedelta
import json
import random
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

# .env dosyasını yükle
load_dotenv()

# Log yapılandırması
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("update_user_activities.log")
    ]
)
logger = logging.getLogger("UpdateUserActivities")

# PostgreSQL bağlantı bilgileri
DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")
DB_NAME = os.getenv("POSTGRES_DB", "telegram_bot")
DB_USER = os.getenv("POSTGRES_USER", "postgres")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")

def get_db_connection():
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
        logger.error(f"Veritabanı bağlantı hatası: {e}")
        return None

def create_activity_log_table(conn):
    """Kullanıcı aktivite logları için tablo oluşturur"""
    try:
        cursor = conn.cursor()
        
        # PostgreSQL için uyumlu tablo oluşturma
        query = """
        CREATE TABLE IF NOT EXISTS user_activity_log (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            action VARCHAR(50) NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            data JSONB
        );
        """
        cursor.execute(query)
        
        # İndeksleri oluştur
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_activity_user ON user_activity_log (user_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_activity_action ON user_activity_log (action);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_activity_timestamp ON user_activity_log (timestamp);")
        
        conn.commit()
        logger.info("Kullanıcı aktivite log tablosu oluşturuldu veya zaten var")
        
        # Kullanıcı sütunlarını güncelle
        update_user_columns(conn)
        
    except Exception as e:
        logger.error(f"Tablo oluşturma hatası: {str(e)}")
        conn.rollback()

def update_user_columns(conn):
    """Kullanıcı tablosunda eksik sütunları kontrol eder ve ekler"""
    try:
        cursor = conn.cursor()
        
        # PostgreSQL'de sütunları kontrol etmek için information_schema kullanılır
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'users' 
            AND table_schema = 'public'
        """)
        
        existing_columns = [row["column_name"].lower() for row in cursor.fetchall()]
        
        # Eklenmesi gereken sütunlar
        required_columns = {
            "last_activity": "TIMESTAMP DEFAULT NULL",
            "activity_count": "INTEGER DEFAULT 0",
            "status": "VARCHAR(20) DEFAULT 'active'",
            "is_bot": "BOOLEAN DEFAULT FALSE",
            "is_premium": "BOOLEAN DEFAULT FALSE",
            "language_code": "VARCHAR(10) DEFAULT NULL",
            "joined_date": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
        }
        
        # Her sütun için kontrol et ve ekle
        for column, data_type in required_columns.items():
            if column.lower() not in existing_columns:
                try:
                    cursor.execute(f"ALTER TABLE users ADD COLUMN {column} {data_type}")
                    conn.commit()
                    logger.info(f"'{column}' sütunu users tablosuna eklendi")
                except Exception as e:
                    logger.error(f"'{column}' sütunu eklenirken hata: {str(e)}")
                    conn.rollback()
        
    except Exception as e:
        logger.error(f"Kullanıcı tablosu sütunları güncellenirken hata: {str(e)}")
        conn.rollback()

def generate_random_activities(conn):
    """Test için rastgele kullanıcı aktiviteleri oluşturur"""
    try:
        cursor = conn.cursor()
        
        # Kullanıcıları getir
        cursor.execute("SELECT id FROM users LIMIT 10")
        users = cursor.fetchall()
        
        if not users:
            logger.warning("Aktivite oluşturmak için kullanıcı bulunamadı")
            return
        
        activity_types = ["login", "message", "join_group", "update_profile", "view_content"]
        current_time = datetime.now()
        
        for user in users:
            user_id = user["id"]
            
            # Her kullanıcı için 1-5 arasında rastgele sayıda aktivite oluştur
            num_activities = random.randint(1, 5)
            
            for _ in range(num_activities):
                activity_type = random.choice(activity_types)
                # Son 7 gün içinde rastgele bir zaman
                random_days = random.randint(0, 7)
                random_hours = random.randint(0, 23)
                random_minutes = random.randint(0, 59)
                activity_date = current_time - timedelta(
                    days=random_days, 
                    hours=random_hours, 
                    minutes=random_minutes
                )
                
                # JSON veri oluştur
                data = {
                    "ip": f"192.168.1.{random.randint(1, 255)}",
                    "device": random.choice(["mobile", "desktop", "tablet"]),
                    "details": f"Rastgele oluşturulan {activity_type} aktivitesi"
                }
                
                # Parametre soru işaretlerini PostgreSQL formatına çevir
                cursor.execute("""
                INSERT INTO user_activity_log 
                (user_id, action, timestamp, data) 
                VALUES (%s, %s, %s, %s)
                """, (
                    user_id, 
                    activity_type, 
                    activity_date, 
                    json.dumps(data)
                ))
                
                # Son aktivite zamanını güncelle
                cursor.execute("""
                UPDATE users SET 
                    last_activity = %s,
                    status = 'active',
                    activity_count = COALESCE(activity_count, 0) + 1
                WHERE id = %s
                """, (activity_date, user_id))
        
        conn.commit()
        logger.info(f"Toplam {len(users)} kullanıcı için rastgele aktiviteler oluşturuldu")
        return True
        
    except Exception as e:
        logger.error(f"Aktivite oluşturma hatası: {str(e)}")
        conn.rollback()
        return False

def log_user_activity(conn, user_id, action, data=None):
    """Kullanıcı aktivitesini kaydeder"""
    try:
        if not conn:
            logger.error("Veritabanı bağlantısı bulunamadı")
            return False
            
        cursor = conn.cursor()
        timestamp = datetime.now()
        
        # Veriyi JSON'a dönüştür
        json_data = json.dumps(data) if data else None
        
        # PostgreSQL parametre formatı
        cursor.execute("""
        INSERT INTO user_activity_log 
        (user_id, action, timestamp, data) 
        VALUES (%s, %s, %s, %s)
        """, (user_id, action, timestamp, json_data))
        
        # Kullanıcı son aktivite bilgisini güncelle
        cursor.execute("""
        UPDATE users SET 
            last_activity = %s,
            status = 'active',
            activity_count = COALESCE(activity_count, 0) + 1
        WHERE id = %s
        """, (timestamp, user_id))
        
        conn.commit()
        logger.debug(f"Kullanıcı {user_id} için '{action}' aktivitesi kaydedildi")
        return True
        
    except Exception as e:
        logger.error(f"Aktivite kaydetme hatası: {str(e)}")
        if conn:
            conn.rollback()
        return False

def main():
    """Ana fonksiyon"""
    conn = get_db_connection()
    
    if not conn:
        logger.error("Veritabanı bağlantısı kurulamadı!")
        sys.exit(1)
        
    try:
        # Aktivite log tablosunu oluştur
        create_activity_log_table(conn)
        
        # Kullanıcı tablosundaki eksik sütunları ekle
        update_user_columns(conn)
        
        # Test için rastgele aktiviteler oluştur
        generate_random_activities(conn)
        
        logger.info("İşlem başarıyla tamamlandı")
        
    except Exception as e:
        logger.error(f"İşlem hatası: {str(e)}")
    finally:
        conn.close()
        logger.info("Veritabanı bağlantısı kapatıldı")

if __name__ == "__main__":
    main() 