#!/usr/bin/env python3
"""
Yeni temiz bir Telethon oturum dosyası oluşturur.
Bu script, sıfırdan yeni bir Telethon oturum dosyası oluşturarak
oturum dosyalarındaki şema sorunlarını çözer.

Kullanım:
    python create_fresh_session.py [session_name]
"""

import os
import sys
import sqlite3
import logging
from pathlib import Path

# Log ayarları
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

def create_new_session(session_name="bot_session_clean"):
    """Belirtilen adla temiz bir oturum dosyası oluşturur"""
    try:
        # Ana dizini belirle
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        session_dir = os.path.join(base_dir, "session")
        os.makedirs(session_dir, exist_ok=True)
        
        # Oturum dosyası yolunu oluştur
        session_path = os.path.join(session_dir, f"{session_name}.session")
        
        # Eğer dosya varsa sil
        if os.path.exists(session_path):
            os.remove(session_path)
            logger.info(f"Var olan oturum dosyası silindi: {session_path}")
        
        # Yeni SQLite veritabanı oluştur
        logger.info(f"Yeni oturum dosyası oluşturuluyor: {session_path}")
        conn = sqlite3.connect(session_path)
        c = conn.cursor()
        
        # sessions tablosu
        c.execute("""
        CREATE TABLE sessions (
            dc_id INTEGER PRIMARY KEY,
            server_address TEXT,
            port INTEGER,
            auth_key BLOB
        )
        """)
        
        # entities tablosu
        c.execute("""
        CREATE TABLE entities (
            id INTEGER PRIMARY KEY,
            hash INTEGER NOT NULL,
            username TEXT,
            phone INTEGER,
            name TEXT,
            date INTEGER
        )
        """)
        
        # sent_files tablosu
        c.execute("""
        CREATE TABLE sent_files (
            md5_digest BLOB,
            file_size INTEGER,
            type INTEGER,
            id INTEGER,
            hash INTEGER,
            PRIMARY KEY(md5_digest, file_size, type)
        )
        """)
        
        # update_state tablosu
        c.execute("""
        CREATE TABLE update_state (
            id INTEGER PRIMARY KEY,
            pts INTEGER,
            qts INTEGER,
            date INTEGER,
            seq INTEGER
        )
        """)
        
        # version tablosu
        c.execute("""
        CREATE TABLE version (
            version INTEGER PRIMARY KEY
        )
        """)
        c.execute("INSERT INTO version VALUES (7)")
        
        # İndeksler ekle
        c.execute("CREATE INDEX IF NOT EXISTS entities_username_idx ON entities (username)")
        c.execute("CREATE INDEX IF NOT EXISTS entities_name_idx ON entities (name)")
        
        # Değişiklikleri kaydet ve bağlantıyı kapat
        conn.commit()
        conn.close()
        
        # Main.py için session yolunu güncelle
        update_main_py(session_name)
        
        logger.info(f"Temiz Telethon oturum dosyası başarıyla oluşturuldu: {session_path}")
        return True
        
    except Exception as e:
        logger.error(f"Oturum dosyası oluşturulurken hata: {str(e)}")
        return False

def update_main_py(session_name):
    """main.py dosyasını yeni oturum dosyasını kullanacak şekilde günceller"""
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        main_py_path = os.path.join(base_dir, "bot", "main.py")
        
        if not os.path.exists(main_py_path):
            logger.warning(f"main.py dosyası bulunamadı: {main_py_path}")
            return False
            
        # Dosyayı oku
        with open(main_py_path, 'r') as f:
            content = f.read()
            
        # Session path'i bul ve değiştir
        import re
        
        # İki farklı pattern için kontrol et (tırnak tipi farkı için)
        pattern_single = r"session_file\s*=\s*os\.path\.join\(session_dir,\s*'([^']+)'\)"
        pattern_double = r'session_file\s*=\s*os\.path\.join\(session_dir,\s*"([^"]+)")'
        pattern_direct_single = r"client\s*=\s*TelegramClient\(\s*'([^']+)'"
        pattern_direct_double = r'client\s*=\s*TelegramClient\(\s*"([^"]+)"'
        pattern_path_single = r"client\s*=\s*TelegramClient\(\s*os\.path\.join\(session_dir,\s*'([^']+)'\)"
        pattern_path_double = r'client\s*=\s*TelegramClient\(\s*os\.path\.join\(session_dir,\s*"([^"]+)"\)'
        
        # Güncel session_file adını al
        match_single = re.search(pattern_single, content)
        match_double = re.search(pattern_double, content)
        match_direct_single = re.search(pattern_direct_single, content)
        match_direct_double = re.search(pattern_direct_double, content)
        match_path_single = re.search(pattern_path_single, content)
        match_path_double = re.search(pattern_path_double, content)
        
        updated_content = content
        
        # session_file değişkenini güncelle
        if match_single:
            old_session = match_single.group(1)
            updated_content = updated_content.replace(
                f"session_file = os.path.join(session_dir, '{old_session}')",
                f"session_file = os.path.join(session_dir, '{session_name}')"
            )
        elif match_double:
            old_session = match_double.group(1)
            updated_content = updated_content.replace(
                f'session_file = os.path.join(session_dir, "{old_session}")',
                f'session_file = os.path.join(session_dir, "{session_name}")'
            )
        
        # Doğrudan TelegramClient() çağrılarını güncelle
        if match_direct_single:
            old_session = match_direct_single.group(1)
            updated_content = updated_content.replace(
                f"client = TelegramClient('{old_session}'",
                f"client = TelegramClient(os.path.join(session_dir, '{session_name}')"
            )
        elif match_direct_double:
            old_session = match_direct_double.group(1)
            updated_content = updated_content.replace(
                f'client = TelegramClient("{old_session}"',
                f'client = TelegramClient(os.path.join(session_dir, "{session_name}")'
            )
        
        # os.path.join kullanımını güncelle
        if match_path_single:
            old_session = match_path_single.group(1)
            updated_content = updated_content.replace(
                f"client = TelegramClient(os.path.join(session_dir, '{old_session}')",
                f"client = TelegramClient(os.path.join(session_dir, '{session_name}')"
            )
        elif match_path_double:
            old_session = match_path_double.group(1)
            updated_content = updated_content.replace(
                f'client = TelegramClient(os.path.join(session_dir, "{old_session}"))',
                f'client = TelegramClient(os.path.join(session_dir, "{session_name}"))'
            )
        
        # Değişiklikleri kaydet
        with open(main_py_path, 'w') as f:
            f.write(updated_content)
            
        logger.info(f"main.py dosyası güncellendi, yeni oturum dosyası kullanılacak: {session_name}")
        return True
        
    except Exception as e:
        logger.error(f"main.py dosyası güncellenirken hata: {str(e)}")
        return False

def main():
    """Ana çalışma fonksiyonu"""
    logger.info("Temiz Telethon oturum oluşturma aracı başlatılıyor...")
    
    # Kullanıcı özel session adı belirleyebilir
    session_name = "bot_session_clean"
    if len(sys.argv) > 1:
        session_name = sys.argv[1]
    
    # Yeni oturum dosyası oluştur
    if create_new_session(session_name):
        logger.info(f"'{session_name}' adlı temiz oturum dosyası başarıyla oluşturuldu.")
        logger.info("Bot'u yeniden başlatın ve yeni telefon doğrulaması yaparak oturumu oluşturun.")
    else:
        logger.error("Temiz oturum dosyası oluşturulamadı!")

if __name__ == "__main__":
    main() 