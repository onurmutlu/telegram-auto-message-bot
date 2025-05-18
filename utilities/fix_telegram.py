import os
import sqlite3
import logging
import asyncio
from telethon import TelegramClient

# Telegram API bilgileri
API_ID = 20812967  # Örnek ID, kendi ID'nizi kullanın
API_HASH = "5dc3dd519e252c8553ae9e0b4ac0ced8"  # Örnek hash, kendi hash'inizi kullanın
SESSION_FILE = "telegram_session.session"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("fix_telegram")

def unlock_session_file():
    """Session dosyasının kilidini açar"""
    lock_file = f"{SESSION_FILE}.lock"
    
    if os.path.exists(lock_file):
        try:
            os.remove(lock_file)
            logger.info(f"Lock dosyası silindi: {lock_file}")
        except Exception as e:
            logger.error(f"Lock dosyası silinirken hata: {str(e)}")
    else:
        logger.info(f"Lock dosyası bulunamadı: {lock_file}")

def check_session_file():
    """Session dosyasını kontrol eder"""
    if not os.path.exists(SESSION_FILE):
        logger.warning(f"Session dosyası bulunamadı: {SESSION_FILE}")
        return False
        
    try:
        # SQLite veritabanına bağlanmayı dene
        conn = sqlite3.connect(SESSION_FILE)
        cursor = conn.cursor()
        
        # Sessions tablosunu kontrol et
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sessions'")
        sessions_exist = cursor.fetchone() is not None
        
        if sessions_exist:
            cursor.execute("SELECT COUNT(*) FROM sessions")
            session_count = cursor.fetchone()[0]
            logger.info(f"Sessions tablosunda {session_count} kayıt var")
        else:
            logger.warning("Sessions tablosu bulunamadı")
            
        conn.close()
        return True
        
    except sqlite3.Error as e:
        logger.error(f"Session dosyası kontrol edilirken SQLite hatası: {str(e)}")
        return False

async def test_connection():
    """Telegram bağlantısını test eder"""
    client = None
    try:
        # API bilgilerini .env dosyasından okuyabilirsiniz
        from dotenv import load_dotenv
        load_dotenv()
        
        api_id = os.getenv("TELEGRAM_API_ID", API_ID)
        api_hash = os.getenv("TELEGRAM_API_HASH", API_HASH)
        
        logger.info(f"Telegram client oluşturuluyor (API ID: {api_id})")
        client = TelegramClient(SESSION_FILE, api_id, api_hash)
        
        logger.info("Bağlantı kuruluyor...")
        await client.connect()
        
        if await client.is_user_authorized():
            me = await client.get_me()
            logger.info(f"Bağlantı başarılı! Kullanıcı: {me.first_name} (@{me.username})")
            return True
        else:
            logger.error("Kullanıcı yetkilendirilmemiş!")
            return False
            
    except Exception as e:
        logger.error(f"Bağlantı hatası: {str(e)}")
        return False
    finally:
        if client:
            await client.disconnect()

async def main():
    logger.info("Telegram oturumu düzeltme işlemi başlıyor...")
    
    # Lock dosyasını sil
    unlock_session_file()
    
    # Session dosyasını kontrol et
    session_ok = check_session_file()
    
    if not session_ok:
        logger.warning("Session dosyası sorunlu, tekrar oluşturulması gerekebilir")
    
    # Bağlantıyı test et
    connection_ok = await test_connection()
    
    if connection_ok:
        logger.info("Telegram bağlantısı başarıyla düzeltildi!")
    else:
        logger.error("Telegram bağlantısı düzeltilemedi.")
        logger.info("Yeni oturum oluşturmak için telegram_login.py dosyasını çalıştırabilirsiniz.")

if __name__ == "__main__":
    asyncio.run(main()) 