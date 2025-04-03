# Yeni bir dosya oluştur

import os
import sqlite3
import sys

# Ana dizini ekle
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

# Gerekli modülleri import et
import logging

# Log yapılandırması
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger()

def fix_database():
    """Veritabanını düzeltir."""
    db_path = os.path.join(os.path.dirname(__file__), "../../data/users.db")
    
    print(f"Veritabanı düzeltiliyor: {db_path}")
    
    try:
        # Veritabanı bağlantısını oluştur
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Mevcut sütunları kontrol et
        cursor.execute("PRAGMA table_info(users)")
        columns = [row[1] for row in cursor.fetchall()]
        print(f"Mevcut sütunlar: {columns}")
        
        # last_invited sütunu eksikse ekle
        if "last_invited" not in columns:
            print("'last_invited' sütunu ekleniyor...")
            cursor.execute("ALTER TABLE users ADD COLUMN last_invited TIMESTAMP")
            conn.commit()
            print("Sütun eklendi!")
        else:
            print("'last_invited' sütunu zaten var.")
            
        print("Veritabanı düzeltme tamamlandı!")
        
    except sqlite3.Error as e:
        print(f"SQLite hatası: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    fix_database()