#!/usr/bin/env python3
"""
Telethon 1.40.0 versiyonu için uyumlu bir session dosyası oluşturan script
"""
import os
import sys
import sqlite3
import logging
import re
from pathlib import Path

# Loglama ayarları
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

def create_compatible_session():
    """
    Telethon 1.40.0 versiyonu ile uyumlu bir session dosyası oluşturur
    """
    # Ana dizinleri belirle
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    session_dir = os.path.join(base_dir, "session")
    os.makedirs(session_dir, exist_ok=True)
    
    # Yeni session dosyasının adı
    session_name = "session_v140"
    session_file = os.path.join(session_dir, f"{session_name}.session")
    
    # Eğer dosya varsa sil
    if os.path.exists(session_file):
        os.remove(session_file)
        logger.info(f"Eski oturum dosyası silindi: {session_file}")
    
    # SQLite veritabanı oluştur
    logger.info(f"Yeni oturum dosyası oluşturuluyor: {session_file}")
    conn = sqlite3.connect(session_file)
    c = conn.cursor()
    
    # Telethon 1.40.0 için sessions tablosu oluştur (takeout_id sütunu ile)
    c.execute("""
    CREATE TABLE sessions (
        dc_id INTEGER PRIMARY KEY,
        server_address TEXT,
        port INTEGER,
        auth_key BLOB,
        takeout_id INTEGER
    )
    """)
    
    # Diğer gerekli tabloları oluştur
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
    
    # Telethon 1.40.0 için version değeri
    c.execute("INSERT INTO version VALUES (7)")
    
    conn.commit()
    conn.close()
    
    logger.info(f"Session dosyası başarıyla oluşturuldu: {session_file}")
    
    # main.py dosyasını güncelle
    main_py_path = os.path.join(base_dir, "bot", "main.py")
    if os.path.exists(main_py_path):
        try:
            with open(main_py_path, 'r') as f:
                content = f.read()
            
            # session_file değişkenini güncelle
            updated_content = re.sub(
                r'session_file\s*=\s*os\.path\.join\(session_dir,\s*[\'"].*?[\'"]\)',
                f'session_file = os.path.join(session_dir, "{session_name}")',
                content
            )
            
            with open(main_py_path, 'w') as f:
                f.write(updated_content)
                
            logger.info(f"main.py dosyası güncellendi, yeni oturum dosyası: {session_name}")
        except Exception as e:
            logger.error(f"main.py güncellenirken hata: {str(e)}")
    
    return session_file, session_name

if __name__ == "__main__":
    session_file, session_name = create_compatible_session()
    
    # Talimatları göster
    logger.info(f"""\
✅ Telethon 1.40.0 ile uyumlu oturum dosyası başarıyla oluşturuldu: {session_file}

Şimdi yapmanız gerekenler:
1. Botunuzu aşağıdaki komutla başlatın:
   python -m bot.main

2. Bot ilk çalıştığında telefonunuza bir doğrulama kodu gönderecek
   Bu kodu yazmanız gerekecek.

3. Doğrulama tamamlandıktan sonra bot normal şekilde çalışmaya başlayacak.
   
Not: Eski oturum dosyalarınız artık kullanılmayacak, gerekirse session_backup/ 
dizinindeki yedekleri kullanabilirsiniz.
""") 