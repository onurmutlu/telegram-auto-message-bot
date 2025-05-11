import os
import sys
import asyncio
import sqlite3
from dotenv import load_dotenv

sys.path.append('.')
load_dotenv()

from main import setup_telegram_client, Database

# Session dizini - proje yapısına uygun
SESSION_DIR = "runtime/sessions"

async def create_settings_table(db_path):
    """Settings tablosunu oluştur"""
    try:
        # Veritabanı dizini
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        # SQLite bağlantısı
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Settings tablosunu oluştur
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        ''')
        
        conn.commit()
        conn.close()
        print("Settings tablosu oluşturuldu.")
    except Exception as e:
        print(f"Settings tablosu oluşturulurken hata: {e}")

async def test():
    try:
        # DB_PATH çevre değişkenini kontrol et
        db_path = os.getenv('DB_PATH', 'data/users.db')
        print(f"Veritabanı yolu: {db_path}")
        
        # Session dizininin var olduğundan emin ol
        os.makedirs(SESSION_DIR, exist_ok=True)
        print(f"Session dizini: {SESSION_DIR}")
        
        # Settings tablosunu oluştur
        await create_settings_table(db_path)
            
        print("Veritabanı bağlanıyor...")
        db = Database(db_path=db_path)
        await db.connect()
        
        # Veritabanı tablolarını oluştur
        await db.create_tables()
        print("Veritabanı tabloları oluşturuldu.")
        
        print("Telegram istemcisi kuruluyor...")
        client = await setup_telegram_client(db)
        
        print("Kullanıcı bilgisi alınıyor...")
        me = await client.get_me()
        if me:
            print(f'Bağlantı başarılı: {me.first_name} (@{me.username})')
            # Session string'i kaydet
            session_string = client.session.save()
            db.cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                            ("session_string", session_string))
            db.conn.commit()
            print("Session string veritabanına kaydedildi.")
        else:
            print("Yetkilendirme başarısız! Kullanıcı bilgisi alınamadı.")
            print("Lütfen manuel olarak oturum açın:")
            # runtime/sessions dizinine göre komut güncellendi
            print(f"  python -c 'from telethon.sync import TelegramClient; client = TelegramClient(\"{SESSION_DIR}/bot_session\", API_ID, API_HASH); client.start(); print(client.session.save())'")
        
        await client.disconnect()
        await db.close()
    except Exception as e:
        import traceback
        print(f"HATA: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test()) 