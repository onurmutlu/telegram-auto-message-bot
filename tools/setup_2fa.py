#!/usr/bin/env python3
"""
İki faktörlü doğrulama ile oturum açma yardımcı programı
"""

import os
import sys
import asyncio
import sqlite3
from dotenv import load_dotenv

# .env dosyasını yükle
load_dotenv()

# Klasörleri import path'e ekle
sys.path.append('.')
sys.path.append('..')

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError

# API kimlik bilgileri
API_ID = int(os.getenv("API_ID", "23692263"))
API_HASH = os.getenv("API_HASH", "ff5d6053b266f78d1293f9343f40e77e")
PHONE = os.getenv("PHONE", "+905382617727")

# Session ve veritabanı yolları
SESSION_DIR = "runtime/sessions"
SESSION_FILE = os.path.join(SESSION_DIR, "bot_session")
DB_PATH = os.getenv("DB_PATH", "data/users.db")

async def setup_session():
    """İki faktörlü doğrulama gerektiren oturum kurulumu"""
    print(f"📱 Telegram oturum kurulum yardımcısı")
    print(f"API ID: {API_ID}")
    print(f"API Hash: {API_HASH[:5]}...{API_HASH[-5:]}")
    print(f"Telefon: {PHONE}")
    print(f"Session dizini: {SESSION_DIR}")
    print(f"Veritabanı yolu: {DB_PATH}")
    
    # Dizinleri oluştur
    os.makedirs(SESSION_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    try:
        # Disk tabanlı oturum oluştur
        client = TelegramClient(SESSION_FILE, API_ID, API_HASH)
        
        # Bağlantı kur
        await client.connect()
        
        if not await client.is_user_authorized():
            print("❌ Oturum yetkili değil, oturum açma işlemi başlatılıyor...")
            
            # Telegram'dan doğrulama kodu iste
            await client.send_code_request(PHONE)
            code = input("📟 Telegram'dan gelen doğrulama kodunu girin: ")
            
            try:
                # Kod ile oturum açmayı dene
                await client.sign_in(PHONE, code)
            except SessionPasswordNeededError:
                # İki faktörlü doğrulama gerekli
                print("🔐 İki faktörlü doğrulama şifresi gerekli")
                password = input("🔑 İki faktörlü doğrulama şifrenizi girin: ")
                await client.sign_in(password=password)
            
            # Kullanıcı bilgilerini kontrol et
            me = await client.get_me()
            print(f"✅ Oturum açma başarılı! Kullanıcı: {me.first_name} (@{me.username})")
        else:
            me = await client.get_me()
            print(f"✅ Zaten oturum açılmış: {me.first_name} (@{me.username})")
        
        # StringSession oluştur
        session_string = client.session.save()
        print(f"\n🔵 StringSession oluşturuldu:\n{session_string}\n")
        
        # StringSession'ı veritabanına kaydet
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Settings tablosunu oluştur
        cursor.execute('''CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )''')
        
        # Session stringi kaydet
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                      ("session_string", session_string))
        conn.commit()
        conn.close()
        
        print(f"💾 StringSession veritabanına kaydedildi: {DB_PATH}")
        print(f"🟢 Kurulum tamamlandı! Artık botunuzu 'python main.py' komutu ile çalıştırabilirsiniz.")
        
        # Bağlantıyı kapat
        await client.disconnect()
        
    except Exception as e:
        import traceback
        print(f"\n❌ HATA: {str(e)}")
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    # Windows için Policy ayarla
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    # Ana fonksiyonu çalıştır
    success = asyncio.run(setup_session())
    
    # Başarı durumuna göre çıkış yap
    sys.exit(0 if success else 1) 