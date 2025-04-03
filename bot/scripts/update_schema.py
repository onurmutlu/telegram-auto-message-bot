#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import sqlite3
import logging

# Ana dizini ekle
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

# Log yapılandırması
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

def update_database_schema():
    """Veritabanı şemasını günceller"""
    
    db_path = os.path.join(os.path.dirname(__file__), "../../data/users.db")
    
    print(f"Veritabanı güncelleniyor: {db_path}")
    
    try:
        # Veritabanı bağlantısı
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Mevcut sütunları kontrol et - users tablosu
        cursor.execute("PRAGMA table_info(users)")
        user_columns = {row[1] for row in cursor.fetchall()}
        
        changes_made = False
        
        # Eksik sütunları users tablosuna ekle
        required_columns = {
            "last_invited": "TIMESTAMP",
            "invite_count": "INTEGER DEFAULT 0", 
            "source_group": "TEXT",
            "is_active": "BOOLEAN DEFAULT 1"
        }
        
        for column, data_type in required_columns.items():
            if column not in user_columns:
                print(f"Users tablosuna '{column}' sütunu ekleniyor...")
                cursor.execute(f"ALTER TABLE users ADD COLUMN {column} {data_type}")
                changes_made = True
        
        # group_stats tablosunu kontrol et ve gerekirse oluştur
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='group_stats'")
        if not cursor.fetchone():
            print("group_stats tablosu oluşturuluyor...")
            cursor.execute('''
            CREATE TABLE group_stats (
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
            changes_made = True
            
        conn.commit()
        
        if changes_made:
            print("Veritabanı şeması başarıyla güncellendi!")
        else:
            print("Veritabanı şeması zaten güncel.")
            
    except sqlite3.Error as e:
        print(f"SQLite hatası: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    update_database_schema()