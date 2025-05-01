#!/usr/bin/env python3
"""
# ============================================================================ #
# Dosya: main.py
# Yol: /Users/siyahkare/code/telegram-bot/bot/main.py
# İşlev: Telegram botunun ana giriş noktası ve uygulama başlangıcı.
#
# © 2025 SiyahKare Yazılım - Tüm Hakları Saklıdır
# ============================================================================ #
"""

import asyncio
import logging
import os
import signal
import sys
from datetime import datetime
from pathlib import Path

from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

from bot.utils.logger_setup import setup_logger
from bot.utils.cli_interface import handle_keyboard_input, print_banner, show_help
from bot.utils.postgres_db import setup_postgres_db
from database.user_db import UserDatabase
from bot.config import Config
from dotenv import load_dotenv

# Log yapılandırması
logger = setup_logger()

# .env dosyasından çevre değişkenlerini yükle
load_dotenv()

# Kapatma olayı için
shutdown_event = asyncio.Event()

# Bot durumu
bot_running = False

# Oturum dizini
session_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "session")
os.makedirs(session_dir, exist_ok=True)

# Logs klasörünü oluştur (yoksa)
logs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
Path(logs_dir).mkdir(exist_ok=True)

def signal_handler(sig, frame):
    """Sinyal işleyici, programın düzgün kapatılmasını sağlar."""
    logger.info(f"Sinyal alındı: {sig}. Bot kapatılıyor...")
    shutdown_event.set()

# Sinyal işleyicileri ekle
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)
if sys.platform != 'win32':  # Windows'ta SIGBREAK yok
    try:
        signal.signal(signal.SIGHUP, signal_handler)
    except AttributeError:
        pass  # SIGHUP bazı platformlarda olmayabilir

# Kullanıcı arayüzü durumu
ui_state = {
    'current_menu': 'main',
    'selected_option': 0,
    'scroll_position': 0,
    'show_logs': True,
    'last_command': None,
    'debug_mode': False,
    'status_message': '',
}

# Bot kontrol durumu
bot_control = {
    'is_running': False,
    'start_time': None,
    'stats': {
        'messages_sent': 0,
        'errors': 0,
        'users_processed': 0,
    }
}

# Klavye giriş işleyici
async def keyboard_input_handler(client, config, user_db):
    """Klavye girişini işler. Bu metot başka bir thread içinde çalıştırılmalıdır."""
    global bot_running
    bot_control = {"is_running": True, "start_time": datetime.now()}
    
    while not shutdown_event.is_set():
        try:
            # Klavye girişini işle (non-blocking)
            await handle_keyboard_input(client, config, user_db, bot_control, shutdown_event)
            
            # Biraz bekle
            await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Klavye giriş işleyici hatası: {str(e)}", exc_info=True)
            await asyncio.sleep(1)  # Hata durumunda biraz daha uzun bekle

async def main():
    """Ana uygulama fonksiyonu"""
    global bot_running, bot_control
    
    # Banner'ı göster
    print_banner()
    
    logger.info("Bot başlatılıyor...")
    
    try:
        # Yapılandırma yükle
        logger.info("Yapılandırma yükleniyor...")
        # Çevre değişkenlerinden bir yapılandırma sözlüğü oluştur
        config_dict = {
            'api_id': os.getenv('API_ID'),
            'api_hash': os.getenv('API_HASH'),
            'database_url': os.getenv('DATABASE_URL'),
            'bot_token': os.getenv('BOT_TOKEN')
        }
        config = Config(config_dict)
        
        # PostgreSQL veritabanını kur
        logger.info("PostgreSQL veritabanına bağlanılıyor...")
        db_conn = setup_postgres_db()
        if not db_conn:
            logger.error("PostgreSQL veritabanı bağlantısı kurulamadı. Uygulama durduruluyor.")
            return
            
        # Veritabanı bağlantısı
        logger.info("Ana veritabanına bağlanılıyor...")
        user_db = UserDatabase(config.get('database_url'))
        
        # Telegram istemcisi oluştur
        logger.info("Telegram istemcisi başlatılıyor...")
        
        # Yeni temiz session dosyasını kullan
        session_file = os.path.join(session_dir, "session_v140")
            
        # Yolu güncellenmiş session dosyasıyla kullan
        logger.info(f"Kullanılan oturum dosyası: {session_file}")
        client = TelegramClient(
            session_file,
            config.get('api_id'), 
            config.get('api_hash')
        )
        
        # Oturum aç
        await client.start()
        
        if not await client.is_user_authorized():
            logger.info("Kullanıcı oturumu bulunamadı. Lütfen telefon numarası ile giriş yapın.")
            phone = input("Telefon numarası (+905xxxxxxxxx): ")
            await client.send_code_request(phone)
            code = input("Telegram'dan aldığınız kodu girin: ")
            
            try:
                await client.sign_in(phone, code)
            except SessionPasswordNeededError:
                password = input("İki faktörlü kimlik doğrulama şifrenizi girin: ")
                await client.sign_in(password=password)
        
        # Botun bağlı olduğunu göster
        me = await client.get_me()
        logger.info(f"Bağlantı başarılı: {me.first_name} (@{me.username})")
        
        # Bot kontrol durumunu güncelle
        bot_running = True
        bot_control = {'is_running': True, 'start_time': datetime.now()}
        
        # Klavye giriş görevini başlat
        input_task = asyncio.create_task(keyboard_input_handler(client, config, user_db))
        
        # Ana görev döngüsü
        while not shutdown_event.is_set():
            # Burada botun ana işlemlerini gerçekleştir
            # ...
            
            # Her 1 saniyede bir kontrol et
            try:
                await asyncio.wait_for(shutdown_event.wait(), timeout=1.0)
            except asyncio.TimeoutError:
                pass
        
        # Kapatma işlemleri
        logger.info("Bot kapatılıyor...")
        
        # PostgreSQL bağlantısını kapat
        if db_conn:
            db_conn.close()
            logger.info("PostgreSQL veritabanı bağlantısı kapatıldı.")
        
        # Klavye giriş görevini iptal et
        if not input_task.done():
            input_task.cancel()
            try:
                await input_task
            except asyncio.CancelledError:
                pass
        
        # Telegram istemcisini kapat
        await client.log_out()
        
        logger.info("Bot başarıyla kapatıldı.")
        
    except Exception as e:
        logger.error(f"Bot çalışırken hata oluştu: {str(e)}", exc_info=True)
    finally:
        # Varsa botu durdur ve kaynakları serbest bırak
        if 'client' in locals() and hasattr(client, 'disconnect'):
            logger.info("Telegram istemcisi kapatılıyor...")
            await client.disconnect()
        
        logger.info("Bot kapatıldı.")

def run():
    """Ana botu çalıştırır"""
    asyncio.run(main())

if __name__ == "__main__":
    run() 