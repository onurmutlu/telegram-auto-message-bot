import os
import sys
import asyncio
import sqlite3
from dotenv import load_dotenv

sys.path.append('.')
load_dotenv()

from telethon import TelegramClient
from telethon.sessions import StringSession

# API kimlik bilgileri
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")

# Session dizini - proje yapısına uygun
SESSION_DIR = "runtime/sessions"
SESSION_FILE = os.path.join(SESSION_DIR, "bot_session")

async def main():
    """Session string oluştur ve veritabanına kaydet"""
    print(f"API ID: {API_ID}")
    print(f"API HASH: {API_HASH[:5]}...{API_HASH[-5:]}")
    
    # Veritabanı dosyası
    db_path = os.getenv("DB_PATH", "data/users.db")
    
    try:
        # Dizinleri oluştur
        os.makedirs(SESSION_DIR, exist_ok=True)
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        print(f"Session dizini: {SESSION_DIR}")
        print(f"Veritabanı dizini: {os.path.dirname(db_path)}")
        
        # Disk tabanlı istemci
        client = TelegramClient(SESSION_FILE, API_ID, API_HASH)
        
        # Bağlan ve oturum aç
        await client.start()
        
        if await client.is_user_authorized():
            # Kullanıcı bilgisi
            me = await client.get_me()
            print(f"Bağlı kullanıcı: {me.first_name} (@{me.username})")
            
            # StringSession oluştur
            session_string = client.session.save()
            print(f"Session string başarıyla oluşturuldu!")
            
            # Veritabanına kaydet
            conn = sqlite3.connect(db_path)
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
            
            print(f"Session string veritabanına kaydedildi: {db_path}")
            
            # Oturumu kapat
            await client.disconnect()
        else:
            print("HATA: Kullanıcı oturumu açılamadı!")
            # Telefon numarası ile oturum açma
            phone = os.getenv("PHONE")
            if not phone:
                phone = input("Telefon numaranızı girin (+90xxxxxxxxxx): ")
            
            print(f"Oturum açma işlemi başlatılıyor: {phone}")
            await client.send_code_request(phone)
            code = input("Doğrulama kodunu girin: ")
            await client.sign_in(phone, code)
            
            # Kontrol et
            if await client.is_user_authorized():
                me = await client.get_me()
                print(f"Oturum açma başarılı: {me.first_name} (@{me.username})")
                
                # StringSession oluştur ve kaydet
                session_string = client.session.save()
                
                # Veritabanına kaydet
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute('''CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )''')
                cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                              ("session_string", session_string))
                conn.commit()
                
                print(f"Session string veritabanına kaydedildi: {db_path}")
            else:
                print("Oturum açma başarısız!")
            
            # Oturumu kapat
            await client.disconnect()
            
    except Exception as e:
        import traceback
        print(f"HATA: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main()) 