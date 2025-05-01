#!/usr/bin/env python3
"""
Telethon oturum dosyalarındaki kilitleme sorunlarını kalıcı olarak çözen script.
Bu script, SQLite veritabanındaki "database is locked" hatalarını çözer ve
yeni bir oturum dosyası oluşturur.

Kullanım:
    python fix_telethon_session_permanent.py
"""

import os
import sys
import glob
import sqlite3
import logging
import time
import shutil
import random
import string
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
    
    # Tüm .session dosyalarını bul
    session_files = []
    
    # Ana dizindeki session dosyaları
    session_files.extend(glob.glob(os.path.join(base_dir, "*.session")))
    
    # Session dizini varsa oradaki dosyaları da ekle
    session_dir = os.path.join(base_dir, "session")
    if os.path.exists(session_dir) and os.path.isdir(session_dir):
        session_files.extend(glob.glob(os.path.join(session_dir, "*.session")))
    
    logger.info(f"{len(session_files)} adet Telethon oturum dosyası bulundu")
    return session_files

def generate_random_string(length=8):
    """Belirtilen uzunlukta rastgele bir string üretir"""
    return ''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(length))

def copy_telethon_session_without_locking(session_file):
    """
    Kilitlenmiş session dosyasını kopyalayarak düzeltir
    """
    try:
        # Orijinal dosya adını al
        original_path = Path(session_file)
        directory = original_path.parent
        base_name = original_path.stem
        
        # Yeni dosya adı oluştur (orijinal_ad + _new.session)
        new_filename = f"{base_name}_new.session"
        new_path = directory / new_filename
        
        logger.info(f"Yeni oturum dosyası oluşturuluyor: {new_path}")
        
        # Orijinal dosyayı kopyala
        shutil.copy2(session_file, new_path)
        
        # Yeni dosyayı aç ve tabloları kontrol et/düzelt
        try:
            # Yeni dosyayı salt okunur modda aç
            conn_read = sqlite3.connect(f"file:{new_path}?mode=ro", uri=True)
            c_read = conn_read.cursor()
            
            # Tabloları kontrol et
            tables = c_read.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            tables = [t[0] for t in tables]
            
            # sessions tablosu var mı?
            has_sessions = 'sessions' in tables
            
            # entities tablosu var mı?
            has_entities = 'entities' in tables
            
            # sent_files tablosu var mı?
            has_sent_files = 'sent_files' in tables
            
            # update_state tablosu var mı?
            has_update_state = 'update_state' in tables
            
            conn_read.close()
            
            # Yeni dosyayı yazma modunda aç
            conn_write = sqlite3.connect(new_path)
            c_write = conn_write.cursor()
            
            # session tablosunu yeniden oluştur (kilitleme sorununu çözmek için)
            if has_sessions:
                c_write.execute("DROP TABLE IF EXISTS sessions")
                c_write.execute("""
                CREATE TABLE sessions (
                    dc_id INTEGER PRIMARY KEY,
                    server_address TEXT,
                    port INTEGER,
                    auth_key BLOB
                )
                """)
            
            # Değişiklikleri kaydet
            conn_write.commit()
            conn_write.close()
            
            logger.info(f"Yeni oturum dosyası başarıyla oluşturuldu: {new_path}")
            
            # Ana script için bir yönlendirme/bağlantı dosyası oluştur
            redirect_file = directory / f"{base_name}.redirect"
            with open(redirect_file, 'w') as f:
                f.write(str(new_path))
            
            logger.info(f"Yönlendirme dosyası oluşturuldu: {redirect_file}")
            
            # main.py dosyasını düzenle
            main_file = os.path.join(os.path.dirname(directory), "bot", "main.py")
            if os.path.exists(main_file):
                # Önce içeriği oku
                with open(main_file, 'r') as f:
                    content = f.read()
                
                # session_file satırını değiştir
                import re
                session_pattern = r'session_file\s*=\s*[\'"]([^\'"]+)[\'"]'
                
                # Eşleşme var mı kontrol et
                match = re.search(session_pattern, content)
                if match:
                    old_session = match.group(1)
                    # Ana dizine göre yeni session dosyasının yolunu oluştur
                    relative_new_path = os.path.relpath(new_path, os.path.dirname(directory))
                    new_content = content.replace(
                        f"session_file = '{old_session}'", 
                        f"session_file = '{relative_new_path}'"
                    )
                    new_content = content.replace(
                        f'session_file = "{old_session}"', 
                        f'session_file = "{relative_new_path}"'
                    )
                    
                    # main.py'yi güncelle
                    with open(main_file, 'w') as f:
                        f.write(new_content)
                    
                    logger.info(f"main.py içindeki session_file yolunu güncelledi: {relative_new_path}")
            
            return True
            
        except sqlite3.Error as e:
            logger.error(f"SQLite hatası: {str(e)}")
            return False
    
    except Exception as e:
        logger.error(f"Oturum dosyası kopyalanırken hata: {str(e)}")
        return False

def main():
    """Ana çalışma işlevi"""
    logger.info("Telethon oturumları kalıcı düzeltme aracı başlatılıyor...")
    
    # Session dosyalarını bul
    session_files = find_telethon_sessions()
    
    # Her dosya için işlem yap
    fixed_count = 0
    for session_file in session_files:
        logger.info(f"Oturum dosyası kalıcı olarak düzeltiliyor: {session_file}")
        
        # Yeni bir kopyasını oluştur
        if copy_telethon_session_without_locking(session_file):
            fixed_count += 1
    
    logger.info(f"İşlem tamamlandı: {fixed_count}/{len(session_files)} dosya düzeltildi")
    
    if fixed_count > 0:
        logger.info("Düzeltme işlemi tamamlandı. Lütfen bot'u yeniden başlatın.")
    else:
        logger.warning("Hiçbir dosya düzeltilemedi!")

if __name__ == "__main__":
    main() 