#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
# ============================================================================ #
# Dosya: update_schema.py
# Yol: /Users/siyahkare/code/telegram-bot/bot/scripts/update_schema.py
# İşlev: Telegram botunun veritabanı şema yapısını otomatik günceller
#
# Build: 2025-04-08-23:59:00
# Versiyon: v3.5.0
#
# Açıklama:
# Bu betik, veritabanı şemasını kontrol eder ve güncel olmayan tablolara
# gerekli sütunları ekler. Bot başlatıldığında core.py içindeki init() 
# metodu tarafından otomatik olarak çağrılır. Ayrıca komut satırından 
# manuel olarak da çalıştırılabilir.
#
# Şema aktualizasyonu atomic yapıda gerçekleştirilir: tüm güncellemeler
# ya tamamen başarılı olur ya da hiçbiri uygulanmaz. Böylece şema bütünlüğü
# her durumda korunur.
#
# Temel Özellikler:
# - users tablosunda eksik sütunları kontrol edip ekler
# - group_stats tablosunu gerekirse oluşturur
# - groups tablosunda eksik sütunları kontrol edip ekler
# - user_groups ilişki tablosunu oluşturur (kullanıcıların hangi gruplarda olduğunu takip eder)
# - invite_history tablosunu oluşturur (davet geçmişini izler)
# - Şema sürüm kontrolü ve tutarlılık doğrulaması yapar
# - İşlem öncesi otomatik yedekleme oluşturur
# - Detaylı değişiklik logları tutar
# - Perform ansı optimize eden indeks yapıları oluşturur
# - Foreign key kısıtlamalarını uygular
#
# Veritabanı İlişkileri:
# - users: Tüm kullanıcıların bilgilerini içeren ana tablo
# - groups: Tüm grupların bilgilerini içeren ana tablo
# - user_groups: Kullanıcı-grup ilişkilerini tutan çoka-çok ilişki tablosu
# - group_stats: Gruplara ait istatistikleri tutan tablo
# - invite_history: Kullanıcılara gönderilen davetlerin kaydını tutan tablo
# - schema_version: Veritabanı şeması sürüm takibi için kullanılan tablo
#
# Kullanım:
#   python update_schema.py [--force] [--backup] [--verbose] [--check-only] [--db-path PATH]
#
# Versiyon Geçmişi:
# v3.5.0 (2025-04-08) - Otomatik yedekleme eklendi
#                      - Komut satırı argümanları eklendi
#                      - groups tablosuna is_target sütunu eklendi 
#                      - user_groups ve invite_history tabloları eklendi
#                      - Gelişmiş bütünlük kontrolleri eklendi
#                      - Hata durumunda otomatik geri alma (rollback) özelliği
# v3.4.2 (2025-03-25) - groups tablosuna permanent_error alanı eklendi
# v3.4.0 (2025-03-10) - users tablosuna last_invited, invite_count, source_group, is_active alanları eklendi
# v3.3.0 (2025-03-01) - İlk sürüm
#
# © 2025 SiyahKare Yazılım - Tüm Hakları Saklıdır.
# ============================================================================ #
"""

import os
import sys
import sqlite3
import logging
import time
import argparse
import shutil
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional, Union, Set

# Ana dizini Python yoluna ekle
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

# Log yapılandırması
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Sabitler
SCHEMA_VERSION = "3.5.0"
DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "../../data/users.db")
BACKUP_DIR = os.path.join(os.path.dirname(__file__), "../../backups")

def backup_database(db_path: str) -> Optional[str]:
    """
    Veritabanının yedeğini alır.
    
    Bu fonksiyon, şema değişiklikleri yapmadan önce veritabanının bir yedeğini
    oluşturur, böylece herhangi bir sorun olması durumunda veriler korunur.
    
    Args:
        db_path: Yedeklenecek veritabanı dosya yolu
        
    Returns:
        Optional[str]: Yedeklenen dosyanın yolu veya başarısızsa None
    """
    if not os.path.exists(db_path):
        logger.warning(f"Yedeklenemedi: {db_path} bulunamadı")
        return None
    
    try:
        # Yedek dizini oluştur
        os.makedirs(BACKUP_DIR, exist_ok=True)
        
        # Yedek dosya adı (tarih ve saat ile)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = os.path.join(BACKUP_DIR, f"users_db_backup_{timestamp}.bak")
        
        # Dosyayı kopyala
        shutil.copy2(db_path, backup_file)
        
        logger.info(f"Veritabanı başarıyla yedeklendi: {backup_file}")
        return backup_file
        
    except Exception as e:
        logger.error(f"Veritabanı yedekleme hatası: {e}")
        return None

def update_database_schema(db_path: str = DEFAULT_DB_PATH, 
                          force: bool = False, 
                          backup: bool = True,
                          check_only: bool = False) -> bool:
    """
    Veritabanı şemasını en güncel yapıya getirir.
    
    Bu fonksiyon veritabanı şemasını kontrol eder, eksik tabloları veya sütunları
    oluşturur ve şema versiyonunu günceller. Şema güncellemeleri atomic olarak
    gerçekleştirilir: tüm güncellemeler ya tamamen başarılı olur ya da hiçbiri uygulanmaz.
    
    İşlevleri:
    1. Şema versiyonu tablosunu kontrol ve gerekirse oluşturma
    2. users tablosunu kontrol ve gerekirse oluşturma/güncelleme
    3. groups tablosunu kontrol ve gerekirse oluşturma/güncelleme
    4. group_stats tablosunu kontrol ve gerekirse oluşturma
    5. user_groups ilişki tablosunu kontrol ve gerekirse oluşturma
    6. invite_history tablosunu kontrol ve gerekirse oluşturma
    7. Bütünlük kontrolü ve tutarlılık doğrulaması
    
    Args:
        db_path: Veritabanı dosya yolu
        force: True ise, şema güncel olsa bile güncellemeyi zorla
        backup: True ise, güncelleme öncesi veritabanı yedeği alır
        check_only: True ise, sadece kontrol yapar, değişiklik yapmaz
        
    Returns:
        bool: Şema güncellemesi yapıldıysa True, gerek yoksa False
        
    Raises:
        sqlite3.Error: SQLite veritabanı işlemleri sırasında hata oluştuğunda
        Exception: Diğer beklenmeyen hatalar
    """
    logger.info(f"Veritabanı şeması kontrol ediliyor: {db_path}")
    
    # Değişkenler
    conn = None
    changes_made = False
    start_time = time.time()
    
    try:
        # Veritabanı dizini kontrolü ve oluşturma
        db_dir = os.path.dirname(db_path)
        if not os.path.exists(db_dir):
            os.makedirs(db_dir)
            logger.info(f"Veritabanı dizini oluşturuldu: {db_dir}")
        
        # Yedekleme (isteniyorsa)
        if backup and os.path.exists(db_path):
            backup_path = backup_database(db_path)
            if not backup_path:
                logger.warning("Yedekleme başarısız, işlem devam ediyor...")
            else:
                logger.info(f"Yedek oluşturuldu: {backup_path}")
        
        # Veritabanı bağlantısı
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row  # İsimlendirilebilir sütunlar için
        
        # Eğer sadece kontrol yapılacaksa transaction başlatma
        if not check_only:
            conn.isolation_level = 'IMMEDIATE'  # Explicit transaction
            conn.execute("BEGIN TRANSACTION")
            logger.debug("Transaction başlatıldı")
        
        cursor = conn.cursor()
        
        # Foreign key kısıtlamalarını aktifleştir
        cursor.execute("PRAGMA foreign_keys = ON")
        
        # 1. Şema versiyon tablosunu kontrol et/oluştur
        changes_made |= _ensure_schema_version_table(cursor)
        
        # Mevcut şema versiyonunu kontrol et
        current_version = _get_current_schema_version(cursor)
        logger.info(f"Mevcut şema versiyonu: {current_version}, Hedef versiyon: {SCHEMA_VERSION}")
        
        # Eğer force değilse ve şema zaten güncel ise, işlemleri atla
        if not force and current_version == SCHEMA_VERSION and not check_only:
            logger.info(f"Veritabanı şeması zaten güncel (v{SCHEMA_VERSION}).")
            return False
        
        # 2. Users tablosunu kontrol et/oluştur/güncelle
        changes_made |= _ensure_users_table(cursor)
        
        # 3. Groups tablosunu kontrol et/oluştur/güncelle
        changes_made |= _ensure_groups_table(cursor)
        
        # 4. Group stats tablosunu kontrol et/oluştur
        changes_made |= _ensure_group_stats_table(cursor)
        
        # 5. User groups tablosunu kontrol et/oluştur
        changes_made |= _ensure_user_groups_table(cursor)
        
        # 6. Invite history tablosunu kontrol et/oluştur
        changes_made |= _ensure_invite_history_table(cursor)
        
        # 7. Bütünlük kontrolü yap
        integrity_ok = _check_database_integrity(cursor)
        
        # Eğer sadece kontrol yapılıyorsa burada bitirebiliriz
        if check_only:
            logger.info(f"Kontrol tamamlandı. Potansiyel değişiklik sayısı: {1 if changes_made else 0}")
            end_time = time.time()
            logger.info(f"Şema kontrolü {end_time - start_time:.2f} saniyede tamamlandı.")
            return changes_made
        
        # Eğer değişiklik yapıldıysa veya zorla güncelleme isteniyorsa şema versiyonunu güncelle
        if changes_made or force:
            # Şema versiyonunu güncelle ve değişiklikleri kaydet
            changes_description = _generate_changes_description(current_version)
            cursor.execute(
                "INSERT INTO schema_version (version, updated_at, changes_description) VALUES (?, ?, ?)", 
                (SCHEMA_VERSION, datetime.now(), changes_description)
            )
            
            # Değişiklikleri commit et
            conn.commit()
            logger.info(f"Veritabanı şeması başarıyla v{SCHEMA_VERSION} versiyonuna güncellendi!")
            
        else:
            # Değişiklik yapılmadıysa transaction'ı geri al
            conn.rollback()
            logger.info("Veritabanı şemasında değişiklik yapılmadı.")
        
        # İstatistikler
        end_time = time.time()
        logger.info(f"Şema kontrolü {end_time - start_time:.2f} saniyede tamamlandı.")
        
        return changes_made or force

    except sqlite3.Error as e:
        logger.error(f"SQLite hatası: {e}")
        if conn and not check_only:
            conn.rollback()
        return False
        
    except Exception as e:
        logger.error(f"Beklenmeyen hata: {e}", exc_info=True)
        if conn and not check_only:
            conn.rollback()
        return False
        
    finally:
        if conn:
            conn.close()
            logger.debug("Veritabanı bağlantısı kapatıldı")

def _ensure_schema_version_table(cursor: sqlite3.Cursor) -> bool:
    """
    Şema versiyon tablosunu kontrol eder ve gerekirse oluşturur.
    
    Args:
        cursor: Aktif SQLite cursor nesnesi
        
    Returns:
        bool: Değişiklik yapıldıysa True
    """
    changes_made = False
    
    # Tablo var mı kontrol et
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'")
    if not cursor.fetchone():
        logger.info("schema_version tablosu oluşturuluyor...")
        cursor.execute('''
        CREATE TABLE schema_version (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            changes_description TEXT
        )
        ''')
        changes_made = True
        logger.info("✓ schema_version tablosu oluşturuldu")
    
    return changes_made

def _get_current_schema_version(cursor: sqlite3.Cursor) -> str:
    """
    Mevcut şema versiyonunu veritabanından alır.
    
    Args:
        cursor: Aktif SQLite cursor nesnesi
        
    Returns:
        str: Şema versiyonu veya tablo boşsa "0.0.0"
    """
    cursor.execute("SELECT version FROM schema_version ORDER BY updated_at DESC LIMIT 1")
    version_row = cursor.fetchone()
    return version_row["version"] if version_row else "0.0.0"

def _ensure_users_table(cursor: sqlite3.Cursor) -> bool:
    """
    Users tablosunu kontrol eder, gerekirse oluşturur/günceller.
    
    Args:
        cursor: Aktif SQLite cursor nesnesi
        
    Returns:
        bool: Değişiklik yapıldıysa True
    """
    changes_made = False
    
    # Tablo var mı kontrol et
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
    if not cursor.fetchone():
        logger.info("users tablosu oluşturuluyor...")
        cursor.execute('''
        CREATE TABLE users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_invited TIMESTAMP,
            invite_count INTEGER DEFAULT 0,
            source_group TEXT,
            is_active INTEGER DEFAULT 1,
            is_bot INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Username için indeks ekle
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)")
        
        changes_made = True
        logger.info("✓ users tablosu oluşturuldu")
        
    else:
        # Mevcut sütunları kontrol et
        cursor.execute("PRAGMA table_info(users)")
        user_columns = {row["name"] for row in cursor.fetchall()}
        
        # Eksik sütunları ekle
        required_columns = {
            "last_invited": "TIMESTAMP",             # Son davet zamanı
            "invite_count": "INTEGER DEFAULT 0",     # Toplam davet sayısı
            "source_group": "TEXT",                  # Kullanıcının hangi gruptan alındığı
            "is_active": "INTEGER DEFAULT 1",        # Kullanıcının aktif olup olmadığı
            "is_bot": "INTEGER DEFAULT 0",           # Kullanıcının bot olup olmadığı
            "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",  # Oluşturulma zamanı
            "updated_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"   # Güncellenme zamanı
        }
        
        for column, data_type in required_columns.items():
            if column not in user_columns:
                logger.info(f"Users tablosuna '{column}' sütunu ekleniyor...")
                cursor.execute(f"ALTER TABLE users ADD COLUMN {column} {data_type}")
                changes_made = True
                logger.info(f"✓ '{column}' sütunu eklendi")
    
    return changes_made

def _ensure_groups_table(cursor: sqlite3.Cursor) -> bool:
    """
    Groups tablosunu kontrol eder, gerekirse oluşturur/günceller.
    
    Args:
        cursor: Aktif SQLite cursor nesnesi
        
    Returns:
        bool: Değişiklik yapıldıysa True
    """
    changes_made = False
    
    # Tablo var mı kontrol et
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='groups'")
    if not cursor.fetchone():
        logger.info("groups tablosu oluşturuluyor...")
        cursor.execute('''
        CREATE TABLE groups (
            group_id INTEGER PRIMARY KEY,
            name TEXT,
            join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_message TIMESTAMP,
            message_count INTEGER DEFAULT 0,
            member_count INTEGER DEFAULT 0,
            error_count INTEGER DEFAULT 0,
            last_error TEXT,
            is_active INTEGER DEFAULT 1,
            permanent_error INTEGER DEFAULT 0,
            is_target INTEGER DEFAULT 1,
            retry_after TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # is_target indeksi oluştur (performans için)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_groups_is_target ON groups(is_target)")
        
        # is_active indeksi oluştur (performans için)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_groups_is_active ON groups(is_active)")
        
        changes_made = True
        logger.info("✓ groups tablosu oluşturuldu")
        
    else:
        # Mevcut sütunları kontrol et
        cursor.execute("PRAGMA table_info(groups)")
        group_columns = {row["name"] for row in cursor.fetchall()}
        
        # Eksik sütunları ekle
        required_columns = {
            "permanent_error": "INTEGER DEFAULT 0",  # Kalıcı hata olup olmadığı
            "is_target": "INTEGER DEFAULT 1",        # Hedef grup olup olmadığı
            "last_message": "TIMESTAMP",             # Son mesaj zamanı
            "message_count": "INTEGER DEFAULT 0",    # Toplam mesaj sayısı
            "error_count": "INTEGER DEFAULT 0",      # Toplam hata sayısı
            "last_error": "TEXT",                    # Son hata mesajı
            "retry_after": "TIMESTAMP",              # Tekrar deneme zamanı
            "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",  # Oluşturulma zamanı
            "updated_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"   # Güncellenme zamanı
        }
        
        for column, data_type in required_columns.items():
            if column not in group_columns:
                logger.info(f"Groups tablosuna '{column}' sütunu ekleniyor...")
                cursor.execute(f"ALTER TABLE groups ADD COLUMN {column} {data_type}")
                changes_made = True
                logger.info(f"✓ '{column}' sütunu eklendi")
                
        # İndeksleri kontrol et ve gerekirse ekle
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_groups_is_target'")
        if not cursor.fetchone():
            cursor.execute("CREATE INDEX idx_groups_is_target ON groups(is_target)")
            changes_made = True
            logger.info("✓ 'is_target' için indeks oluşturuldu")
            
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_groups_is_active'")
        if not cursor.fetchone():
            cursor.execute("CREATE INDEX idx_groups_is_active ON groups(is_active)")
            changes_made = True
            logger.info("✓ 'is_active' için indeks oluşturuldu")
    
    return changes_made

def _ensure_group_stats_table(cursor: sqlite3.Cursor) -> bool:
    """
    Group stats tablosunu kontrol eder, gerekirse oluşturur.
    
    Args:
        cursor: Aktif SQLite cursor nesnesi
        
    Returns:
        bool: Değişiklik yapıldıysa True
    """
    changes_made = False
    
    # Tablo var mı kontrol et
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='group_stats'")
    if not cursor.fetchone():
        logger.info("group_stats tablosu oluşturuluyor...")
        cursor.execute('''
        CREATE TABLE group_stats (
            group_id INTEGER PRIMARY KEY,
            group_name TEXT,
            message_count INTEGER DEFAULT 0,
            last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            avg_messages_per_hour REAL DEFAULT 0,
            last_message_sent TIMESTAMP,
            optimal_interval INTEGER DEFAULT 60,
            is_active INTEGER DEFAULT 1,
            FOREIGN KEY (group_id) REFERENCES groups(group_id) ON DELETE CASCADE
        )
        ''')
        changes_made = True
        logger.info("✓ group_stats tablosu oluşturuldu")
        
    return changes_made

def _ensure_user_groups_table(cursor: sqlite3.Cursor) -> bool:
    """
    User groups tablosunu kontrol eder, gerekirse oluşturur.
    
    Args:
        cursor: Aktif SQLite cursor nesnesi
        
    Returns:
        bool: Değişiklik yapıldıysa True
    """
    changes_made = False
    
    # Tablo var mı kontrol et
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_groups'")
    if not cursor.fetchone():
        logger.info("user_groups tablosu oluşturuluyor...")
        cursor.execute('''
        CREATE TABLE user_groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            group_id INTEGER,
            join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, group_id),
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
            FOREIGN KEY (group_id) REFERENCES groups(group_id) ON DELETE CASCADE
        )
        ''')
        
        # İndeksleri oluştur (performans için)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_groups_user_id ON user_groups(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_groups_group_id ON user_groups(group_id)")
        
        changes_made = True
        logger.info("✓ user_groups tablosu oluşturuldu")
        
    else:
        # İndeksleri kontrol et ve gerekirse oluştur
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_user_groups_user_id'")
        if not cursor.fetchone():
            cursor.execute("CREATE INDEX idx_user_groups_user_id ON user_groups(user_id)")
            changes_made = True
            logger.info("✓ user_groups tablosuna user_id indeksi eklendi")
            
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_user_groups_group_id'")
        if not cursor.fetchone():
            cursor.execute("CREATE INDEX idx_user_groups_group_id ON user_groups(group_id)")
            changes_made = True
            logger.info("✓ user_groups tablosuna group_id indeksi eklendi")
    
    return changes_made

def _ensure_invite_history_table(cursor: sqlite3.Cursor) -> bool:
    """
    Invite history tablosunu kontrol eder, gerekirse oluşturur.
    
    Args:
        cursor: Aktif SQLite cursor nesnesi
        
    Returns:
        bool: Değişiklik yapıldıysa True
    """
    changes_made = False
    
    # Tablo var mı kontrol et
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='invite_history'")
    if not cursor.fetchone():
        logger.info("invite_history tablosu oluşturuluyor...")
        cursor.execute('''
        CREATE TABLE invite_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT,
            response TEXT,
            message_template TEXT,
            error_message TEXT,
            retry_count INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        )
        ''')
        
        # İndeksleri oluştur (performans için)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_invite_history_user_id ON invite_history(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_invite_history_sent_at ON invite_history(sent_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_invite_history_status ON invite_history(status)")
        
        changes_made = True
        logger.info("✓ invite_history tablosu oluşturuldu")
        
    else:
        # Mevcut sütunları kontrol et
        cursor.execute("PRAGMA table_info(invite_history)")
        invite_columns = {row["name"] for row in cursor.fetchall()}
        
        # Eksik sütunları ekle
        required_columns = {
            "error_message": "TEXT",                # Hata mesajı
            "retry_count": "INTEGER DEFAULT 0",     # Yeniden deneme sayısı
        }
        
        for column, data_type in required_columns.items():
            if column not in invite_columns:
                logger.info(f"invite_history tablosuna '{column}' sütunu ekleniyor...")
                cursor.execute(f"ALTER TABLE invite_history ADD COLUMN {column} {data_type}")
                changes_made = True
                logger.info(f"✓ '{column}' sütunu eklendi")
        
        # İndeksleri kontrol et ve gerekirse ekle
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_invite_history_user_id'")
        if not cursor.fetchone():
            cursor.execute("CREATE INDEX idx_invite_history_user_id ON invite_history(user_id)")
            changes_made = True
            logger.info("✓ invite_history tablosuna user_id indeksi eklendi")
            
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_invite_history_sent_at'")
        if not cursor.fetchone():
            cursor.execute("CREATE INDEX idx_invite_history_sent_at ON invite_history(sent_at)")
            changes_made = True
            logger.info("✓ invite_history tablosuna sent_at indeksi eklendi")
            
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_invite_history_status'")
        if not cursor.fetchone():
            cursor.execute("CREATE INDEX idx_invite_history_status ON invite_history(status)")
            changes_made = True
            logger.info("✓ invite_history tablosuna status indeksi eklendi")
    
    return changes_made

def _check_database_integrity(cursor: sqlite3.Cursor) -> bool:
    """
    Veritabanı bütünlüğünü kontrol eder.
    
    Args:
        cursor: Aktif SQLite cursor nesnesi
        
    Returns:
        bool: Bütünlük sağlamsa True
    """
    try:
        # SQLite bütünlük kontrolü
        cursor.execute("PRAGMA integrity_check")
        integrity_result = cursor.fetchone()[0]
        
        if integrity_result != "ok":
            logger.warning(f"Veritabanı bütünlük kontrolü başarısız: {integrity_result}")
            return False
            
        # Foreign key kısıtlamalarını kontrol et
        cursor.execute("PRAGMA foreign_key_check")
        fk_violations = cursor.fetchall()
        
        if fk_violations:
            logger.warning(f"Foreign key ihlalleri tespit edildi: {len(fk_violations)} ihlal")
            for violation in fk_violations:
                logger.warning(f"  - Tablo: {violation[0]}, Satır: {violation[1]}, İlişkisel Tablo: {violation[2]}")
            return False
            
        logger.info("Veritabanı bütünlük kontrolü başarılı")
        return True
        
    except Exception as e:
        logger.error(f"Bütünlük kontrolü sırasında hata: {e}")
        return False

def _generate_changes_description(current_version: str) -> str:
    """
    Şema değişiklikleri açıklamasını oluşturur.
    
    Args:
        current_version: Mevcut şema versiyonu
        
    Returns:
        str: Değişiklik açıklaması
    """
    descriptions = {
        "0.0.0": "İlk veritabanı şema oluşturma: users, groups, ve schema_version tabloları eklendi",
        "3.3.0": "users tablosuna last_invited, invite_count, source_group, is_active alanları eklendi",
        "3.4.0": "groups tablosuna permanent_error alanı eklendi",
        "3.4.2": "groups tablosuna is_target sütunu eklendi, user_groups ve invite_history tabloları eklendi",
    }
    
    # Önceki versiyon için özel açıklama varsa döndür
    if current_version in descriptions:
        return descriptions[current_version]
    
    # Yoksa genel bir açıklama döndür
    return f"Şema güncelleme: v{current_version} -> v{SCHEMA_VERSION}"

def verify_database_integrity(db_path: str) -> bool:
    """
    Veritabanı bütünlüğünü doğrular ve temel tablo varlıklarını kontrol eder.
    
    Bu fonksiyon, veritabanında gerekli tüm tabloların varlığını ve bütünlüğünü
    doğrular. Herhangi bir değişiklik yapmaz, sadece kontrol eder.
    
    Args:
        db_path: Veritabanı dosya yolu
        
    Returns:
        bool: Veritabanı bütünlüğü sağlamsa True, aksi halde False
    """
    conn = None
    try:
        # Dosyanın varlığını kontrol et
        if not os.path.exists(db_path):
            logger.error(f"Veritabanı dosyası bulunamadı: {db_path}")
            return False
            
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Temel tabloların varlığını kontrol et
        required_tables = ['users', 'groups', 'group_stats', 'user_groups', 'invite_history', 'schema_version']
        missing_tables = []
        
        for table in required_tables:
            cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
            if not cursor.fetchone():
                missing_tables.append(table)
                logger.error(f"'{table}' tablosu bulunamadı!")
        
        if missing_tables:
            logger.error(f"Eksik tablolar tespit edildi: {', '.join(missing_tables)}")
            return False
                
        # Bütünlük kontrolü
        cursor.execute("PRAGMA integrity_check")
        result = cursor.fetchone()[0]
        
        if result != "ok":
            logger.error(f"Veritabanı bütünlük kontrolü başarısız: {result}")
            return False
            
        # Foreign key kontrolü
        cursor.execute("PRAGMA foreign_key_check")
        fk_violations = cursor.fetchall()
        
        if fk_violations:
            logger.error(f"{len(fk_violations)} foreign key ihlali tespit edildi")
            return False
            
        logger.info("Veritabanı bütünlük kontrolü başarılı")
        return True
        
    except Exception as e:
        logger.error(f"Veritabanı doğrulama hatası: {e}")
        return False
        
    finally:
        if conn:
            conn.close()

def generate_database_report(db_path: str) -> Dict[str, Any]:
    """
    Veritabanı hakkında detaylı bir rapor oluşturur.
    
    Bu fonksiyon veritabanındaki tüm tabloları ve kayıt sayılarını,
    indeksleri, şema versiyonunu ve diğer meta verileri içeren
    kapsamlı bir rapor hazırlar.
    
    Args:
        db_path: Veritabanı dosya yolu
        
    Returns:
        Dict[str, Any]: Veritabanı rapor verileri
    """
    report = {
        "tables": {},
        "indexes": [],
        "schema_version": "Bilinmiyor",
        "integrity_check": False,
        "database_size_kb": 0,
        "creation_time": "Bilinmiyor",
        "modification_time": "Bilinmiyor"
    }
    
    conn = None
    try:
        # Dosya meta verilerini al
        if os.path.exists(db_path):
            file_stats = os.stat(db_path)
            report["database_size_kb"] = file_stats.st_size / 1024
            report["creation_time"] = datetime.fromtimestamp(file_stats.st_ctime).strftime('%Y-%m-%d %H:%M:%S')
            report["modification_time"] = datetime.fromtimestamp(file_stats.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
        else:
            return {"error": f"Veritabanı dosyası bulunamadı: {db_path}"}
        
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Tüm tabloları listele
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row["name"] for row in cursor.fetchall()]
        
        # Her tablo için kayıt sayısını al
        for table in tables:
            try:
                cursor.execute(f"SELECT COUNT(*) as count FROM {table}")
                count = cursor.fetchone()["count"]
                report["tables"][table] = count
            except sqlite3.Error:
                report["tables"][table] = "Erişim hatası"
        
        # Tüm indeksleri listele
        cursor.execute("SELECT name, tbl_name FROM sqlite_master WHERE type='index'")
        report["indexes"] = [{"name": row["name"], "table": row["tbl_name"]} for row in cursor.fetchall()]
        
        # Şema versiyonunu al
        try:
            cursor.execute("SELECT version FROM schema_version ORDER BY updated_at DESC LIMIT 1")
            version_row = cursor.fetchone()
            if version_row:
                report["schema_version"] = version_row["version"]
        except sqlite3.Error:
            pass
            
        # Bütünlük kontrolü
        try:
            cursor.execute("PRAGMA integrity_check")
            integrity_result = cursor.fetchone()[0]
            report["integrity_check"] = (integrity_result == "ok")
        except sqlite3.Error:
            pass
            
        return report
        
    except Exception as e:
        logger.error(f"Rapor oluşturma hatası: {e}")
        return {"error": str(e)}
        
    finally:
        if conn:
            conn.close()

def format_database_report(report: Dict[str, Any]) -> str:
    """
    Veritabanı raporunu okunabilir metin formatına dönüştürür.
    
    Args:
        report: generate_database_report() tarafından oluşturulan rapor
        
    Returns:
        str: Biçimlendirilmiş rapor metni
    """
    if "error" in report:
        return f"HATA: {report['error']}"
        
    lines = []
    lines.append("\n" + "=" * 60)
    lines.append("              VERİTABANI RAPORU                ")
    lines.append("=" * 60)
    
    lines.append(f"\nŞema Versiyonu: {report['schema_version']}")
    lines.append(f"Bütünlük Kontrolü: {'Başarılı' if report['integrity_check'] else 'Başarısız'}")
    lines.append(f"Veritabanı Boyutu: {report['database_size_kb']:.2f} KB")
    lines.append(f"Oluşturulma Zamanı: {report['creation_time']}")
    lines.append(f"Son Değiştirilme Zamanı: {report['modification_time']}")
    
    # Tablo bilgileri
    lines.append("\n" + "-" * 60)
    lines.append("TABLOLAR")
    lines.append("-" * 60)
    
    for table, count in report["tables"].items():
        lines.append(f"{table}: {count} kayıt")
    
    # İndeks bilgileri
    lines.append("\n" + "-" * 60)
    lines.append("İNDEKSLER")
    lines.append("-" * 60)
    
    for index in report["indexes"]:
        lines.append(f"{index['name']} -> {index['table']}")
    
    lines.append("\n" + "=" * 60)
    return "\n".join(lines)

# Eğer doğrudan çalıştırılıyorsa şemayı güncelle
if __name__ == "__main__":
    # Komut satırı argümanları
    parser = argparse.ArgumentParser(description='Veritabanı şemasını günceller ve tutarlılığını kontrol eder.')
    parser.add_argument('--force', action='store_true', help='Şema güncel olsa bile güncellemeyi zorla')
    parser.add_argument('--backup', action='store_true', help='Güncelleme öncesi veritabanı yedeği al')
    parser.add_argument('--verbose', '-v', action='store_true', help='Detaylı log çıktısı göster')
    parser.add_argument('--check-only', action='store_true', help='Sadece kontrol yap, değişiklik yapma')
    parser.add_argument('--db-path', type=str, help='Veritabanı dosya yolu')
    parser.add_argument('--report', action='store_true', help='Veritabanı raporu oluştur')
    
    args = parser.parse_args()
    
    # Verbose modda daha detaylı log
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    # Başlık banner
    print("\n" + "=" * 60)
    print(" " * 10 + "VERİTABANI ŞEMA GÜNCELLEME ARACI v3.5.0" + " " * 10)
    print("=" * 60)
    
    # Veritabanı yolu
    db_path = args.db_path or DEFAULT_DB_PATH
    
    # Rapor oluşturma
    if args.report:
        report = generate_database_report(db_path)
        formatted_report = format_database_report(report)
        print(formatted_report)
        sys.exit(0)
    
    # Veritabanı şemasını güncelle
    result = update_database_schema(
        db_path=db_path,
        force=args.force,
        backup=args.backup,
        check_only=args.check_only
    )
    
    # Sonucu görüntüle
    if args.check_only:
        if result:
            print("\n🔍 Veritabanı şemasında güncelleme gerekiyor.")
        else:
            print("\n✅ Veritabanı şeması zaten güncel.")
    else:
        if result:
            print("\n✅ Veritabanı şeması güncellemeleri tamamlandı!")
        else:
            print("\n🔄 Veritabanı şeması zaten güncel veya bir hata oluştu.")
            
    print("\nBilgi: Bu betik bot başlangıcında otomatik olarak çalıştırılır.")
    print("=" * 50 + "\n")