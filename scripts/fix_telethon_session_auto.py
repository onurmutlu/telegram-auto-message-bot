#!/usr/bin/env python3
"""
Telethon oturum dosyalarındaki kilitleme sorunlarını otomatik olarak düzeltir.
Bu script, SQLite veritabanındaki "database is locked" hatalarını çözer ve
oturum dosyalarını temizler.

Kullanım:
    python fix_telethon_session_auto.py
"""

import os
import sys
import glob
import sqlite3
import logging
import time
import shutil
from pathlib import Path

# Log ayarları
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

def find_telethon_sessions(base_dir=None):
    """Tüm Telethon session dosyalarını bulur"""
    if base_dir is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # Session klasörü
    session_dir = os.path.join(base_dir, "session")
    if os.path.exists(session_dir):
        session_files = glob.glob(os.path.join(session_dir, "*.session"))
    else:
        session_files = []
    
    # Ana dizinde de ara
    session_files.extend(glob.glob(os.path.join(base_dir, "*.session")))
    
    # Alt dizinlerde de ara (sadece 2 seviye)
    for subdir in os.listdir(base_dir):
        subdir_path = os.path.join(base_dir, subdir)
        if os.path.isdir(subdir_path):
            session_files.extend(glob.glob(os.path.join(subdir_path, "*.session")))
    
    return session_files

def fix_session_file(session_path):
    """Telethon session dosyasını düzeltir"""
    logger.info(f"Oturum dosyası düzeltiliyor: {session_path}")
    
    # Yedek oluştur
    backup_path = f"{session_path}.bak"
    try:
        shutil.copy2(session_path, backup_path)
        logger.info(f"Yedek oluşturuldu: {backup_path}")
    except Exception as e:
        logger.error(f"Yedek oluşturulurken hata: {str(e)}")
        return False
    
    # Session dosyasını aç ve düzelt
    try:
        # Önce bağlantıyı test et
        try:
            conn = sqlite3.connect(session_path, timeout=1)
            conn.close()
            logger.info(f"Dosya açıldı, kilitleme sorunu yok.")
            return True
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e):
                logger.warning(f"Veritabanı kilitli, düzeltiliyor: {str(e)}")
            else:
                logger.error(f"Veritabanı hatası: {str(e)}")
                return False
        
        # Kilidi kırmak için yeni bir veritabanı oluştur
        try:
            # 1. Orijinal dosyayı geçici olarak yeniden adlandır
            temp_path = f"{session_path}.temp"
            os.rename(session_path, temp_path)
            
            # 2. Yeni bir veritabanı oluştur ve şemayı kopyala
            new_conn = sqlite3.connect(session_path)
            new_cursor = new_conn.cursor()
            
            # Telethon oturum şeması
            new_cursor.executescript("""
                CREATE TABLE sessions (
                    dc_id INTEGER PRIMARY KEY,
                    server_address TEXT,
                    port INTEGER,
                    auth_key BLOB
                );
                
                CREATE TABLE entities (
                    id INTEGER PRIMARY KEY,
                    hash INTEGER NOT NULL,
                    username TEXT,
                    phone TEXT,
                    name TEXT,
                    date INTEGER
                );
                
                CREATE TABLE sent_files (
                    md5_digest BLOB,
                    file_size INTEGER,
                    type INTEGER,
                    id INTEGER,
                    hash INTEGER,
                    PRIMARY KEY(md5_digest, file_size, type)
                );
                
                CREATE TABLE update_state (
                    id INTEGER PRIMARY KEY,
                    pts INTEGER,
                    qts INTEGER,
                    date INTEGER,
                    seq INTEGER
                );
                
                CREATE TABLE version (
                    version INTEGER PRIMARY KEY
                );
                
                INSERT INTO version VALUES (7);
            """)
            new_conn.commit()
            
            # 3. Orijinal veritabanından veri yüklemeye çalış
            try:
                old_conn = sqlite3.connect(temp_path, timeout=1)
                old_cursor = old_conn.cursor()
                
                # Sessions tablosunu kopyala
                old_cursor.execute("SELECT dc_id, server_address, port, auth_key FROM sessions")
                for row in old_cursor.fetchall():
                    new_cursor.execute(
                        "INSERT INTO sessions VALUES (?, ?, ?, ?)",
                        row
                    )
                
                # Entities tablosunu kopyala
                old_cursor.execute("SELECT id, hash, username, phone, name, date FROM entities")
                for row in old_cursor.fetchall():
                    new_cursor.execute(
                        "INSERT INTO entities VALUES (?, ?, ?, ?, ?, ?)",
                        row
                    )
                
                # Sent_files tablosunu kopyala
                old_cursor.execute("SELECT md5_digest, file_size, type, id, hash FROM sent_files")
                for row in old_cursor.fetchall():
                    new_cursor.execute(
                        "INSERT INTO sent_files VALUES (?, ?, ?, ?, ?)",
                        row
                    )
                
                # Update_state tablosunu kopyala
                old_cursor.execute("SELECT id, pts, qts, date, seq FROM update_state")
                for row in old_cursor.fetchall():
                    new_cursor.execute(
                        "INSERT INTO update_state VALUES (?, ?, ?, ?, ?)",
                        row
                    )
                
                old_conn.close()
                logger.info("Veriler başarıyla yeni veritabanına kopyalandı.")
                
            except sqlite3.OperationalError as e:
                logger.warning(f"Orijinal veritabanından veri çekerken hata: {str(e)}")
                logger.info("Temiz bir oturum veritabanı oluşturuldu.")
            
            # 4. Yeni veritabanını kaydet ve kapat
            new_conn.commit()
            new_conn.close()
            
            # 5. Geçici dosyayı sil
            try:
                os.remove(temp_path)
            except:
                logger.warning(f"Geçici dosya silinemedi: {temp_path}")
            
            logger.info(f"Oturum dosyası başarıyla düzeltildi: {session_path}")
            return True
            
        except Exception as e:
            logger.error(f"Veritabanı düzeltme işlemi sırasında hata: {str(e)}")
            
            # Hata durumunda orijinali geri yükle
            try:
                if os.path.exists(session_path):
                    os.remove(session_path)
                if os.path.exists(temp_path):
                    os.rename(temp_path, session_path)
            except:
                pass
            
            return False
            
    except Exception as e:
        logger.error(f"Session düzeltme hatası: {str(e)}")
        return False

def main():
    """Ana fonksiyon"""
    logger.info("Telethon oturum düzeltme aracı başlatılıyor...")
    
    # Session dosyalarını bul
    session_files = find_telethon_sessions()
    logger.info(f"{len(session_files)} adet Telethon oturum dosyası bulundu")
    
    if not session_files:
        logger.warning("Hiç oturum dosyası bulunamadı!")
        return
    
    # Her dosyayı düzelt
    success_count = 0
    for session_file in session_files:
        if fix_session_file(session_file):
            success_count += 1
    
    logger.info(f"İşlem tamamlandı: {success_count}/{len(session_files)} dosya düzeltildi")

if __name__ == "__main__":
    main() 