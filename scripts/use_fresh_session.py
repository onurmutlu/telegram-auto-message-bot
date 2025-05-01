#!/usr/bin/env python3
"""
Yepyeni bir Telethon oturum dosyası oluşturur ve kullanır.
Bu script, tamamen temiz bir başlangıç yapmanızı sağlar ve
database is locked hatalarını çözer.

Kullanım:
    python use_fresh_session.py
"""

import os
import sys
import sqlite3
import logging
import random
import string
import shutil
from pathlib import Path

# Log ayarları
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

def generate_random_string(length=8):
    """Belirtilen uzunlukta rastgele bir string üretir"""
    return ''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(length))

def create_totally_fresh_session():
    """Tamamen yeni bir oturum dosyası oluşturur"""
    try:
        # Ana dizini belirle
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        session_dir = os.path.join(base_dir, "session")
        os.makedirs(session_dir, exist_ok=True)
        
        # Benzersiz bir isim üret
        session_name = f"fresh_session_{generate_random_string()}"
        session_path = os.path.join(session_dir, f"{session_name}.session")
        
        logger.info(f"Yeni oturum dosyası oluşturuluyor: {session_path}")
        
        # SQLite veritabanı oluştur
        conn = sqlite3.connect(session_path)
        c = conn.cursor()
        
        # Gerekli tabloları oluştur
        c.execute("""
        CREATE TABLE sessions (
            dc_id INTEGER PRIMARY KEY,
            server_address TEXT,
            port INTEGER,
            auth_key BLOB
        )
        """)
        
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
        
        c.execute("""
        CREATE TABLE update_state (
            id INTEGER PRIMARY KEY,
            pts INTEGER,
            qts INTEGER,
            date INTEGER,
            seq INTEGER
        )
        """)
        
        c.execute("""
        CREATE TABLE version (
            version INTEGER PRIMARY KEY
        )
        """)
        c.execute("INSERT INTO version VALUES (7)")
        
        conn.commit()
        conn.close()
        
        logger.info(f"Yeni oturum dosyası başarıyla oluşturuldu: {session_path}")
        
        # main.py dosyasını güncelle
        update_main_py(session_name)
        
        # Clean backup
        backup_dir = os.path.join(base_dir, "session_backup")
        os.makedirs(backup_dir, exist_ok=True)
        
        # Eski session dosyalarını yedekle ve sil
        old_sessions = []
        old_sessions.extend(Path(session_dir).glob("*.session"))
        old_sessions.extend(Path(base_dir).glob("*.session"))
        # Yeni oluşturduğumuz dosya hariç
        old_sessions = [s for s in old_sessions if s.name != f"{session_name}.session"]
        
        for old_session in old_sessions:
            backup_path = os.path.join(backup_dir, old_session.name)
            logger.info(f"Eski oturum dosyası yedekleniyor: {old_session} -> {backup_path}")
            shutil.copy2(old_session, backup_path)
        
        logger.info(f"Eski oturum dosyaları {backup_dir} dizinine yedeklendi")
        
        return session_name, session_path
    except Exception as e:
        logger.error(f"Oturum dosyası oluşturulurken hata: {str(e)}")
        return None, None

def update_main_py(session_name):
    """main.py dosyasını yeni oturum dosyasını kullanacak şekilde günceller"""
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        main_py_path = os.path.join(base_dir, "bot", "main.py")
        
        if not os.path.exists(main_py_path):
            logger.error(f"main.py dosyası bulunamadı: {main_py_path}")
            return False
        
        # Dosyayı oku
        with open(main_py_path, 'r') as f:
            content = f.read()
        
        # Yeni içerik
        new_content = []
        for line in content.splitlines():
            # TelegramClient çağrısını değiştir
            if line.strip().startswith("client = TelegramClient("):
                # Yeni oturum dosyasını kullanacak şekilde güncelle
                new_line = f'        client = TelegramClient(os.path.join(session_dir, "{session_name}"), '
                
                # API ID ve hash bilgileri devamdaki satırda olabilir, bu yüzden mevcut satırı incele
                import re
                match = re.search(r'TelegramClient\([^,]*,(.*)\)', line)
                if match and match.group(1):
                    # İlk virgülden sonrasını al
                    rest = match.group(1).strip()
                    if rest:
                        new_line += rest + ")"
                    else:
                        new_line += 'config.get("api_id"), config.get("api_hash"))'
                else:
                    # Varsayılan olarak config kullan
                    new_line += 'config.get("api_id"), config.get("api_hash"))'
                
                new_content.append(new_line)
            else:
                new_content.append(line)
        
        # Dosyayı güncelle
        with open(main_py_path, 'w') as f:
            f.write('\n'.join(new_content))
        
        logger.info(f"main.py dosyası başarıyla güncellendi, yeni oturum dosyası kullanılacak: {session_name}")
        return True
    
    except Exception as e:
        logger.error(f"main.py dosyası güncellenirken hata: {str(e)}")
        return False

def restart_bot():
    """Telegram botu yeniden başlatır"""
    try:
        logger.info("Bot yeniden başlatılıyor...")
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # Önce mevcut botu durdur
        os.system("pkill -f 'python -m bot.main'")
        
        # 1 saniye bekle
        import time
        time.sleep(1)
        
        # Botu başlat
        cmd = f"cd {base_dir} && python -m bot.main > /dev/null 2>&1 &"
        os.system(cmd)
        
        logger.info("Bot yeniden başlatıldı")
        return True
    except Exception as e:
        logger.error(f"Bot yeniden başlatılırken hata: {str(e)}")
        return False

def main():
    """Ana çalışma işlevi"""
    logger.info("🚀 Tamamen yeni bir oturum dosyasına geçme aracı başlatılıyor...")
    
    # Yeni oturum dosyası oluştur
    session_name, session_path = create_totally_fresh_session()
    
    if not session_name:
        logger.error("❌ Yeni oturum dosyası oluşturulamadı!")
        return
    
    # Botu yeniden başlat
    if restart_bot():
        logger.info(f"✅ İşlem başarıyla tamamlandı! Bot yeni oturum dosyasıyla ({session_name}) başlatıldı.")
        logger.info("⚠️ Telefonunuza gelen doğrulama kodunu girmeniz gerekebilir.")
    else:
        logger.warning("⚠️ Bot yeniden başlatılamadı, lütfen manuel olarak başlatın.")
        logger.info(f"✅ Yeni oturum dosyası başarıyla oluşturuldu: {session_path}")

if __name__ == "__main__":
    main() 