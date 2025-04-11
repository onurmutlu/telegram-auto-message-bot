"""
# ============================================================================ #
# Dosya: main.py
# Yol: /Users/siyahkare/code/telegram-bot/main.py
# İşlev: Telegram botunun ana giriş noktası ve uygulama başlangıcı.
#
# © 2025 SiyahKare Yazılım - Tüm Hakları Saklıdır
# ============================================================================ #
"""

import argparse
import asyncio
import logging
import signal
import sys
from datetime import datetime

from rich.console import Console
from rich.logging import RichHandler
from telethon import TelegramClient

from config import Config
from database.user_db import UserDatabase as Database
from bot.services.service_factory import ServiceFactory
from bot.services.service_manager import ServiceManager
from bot.utils.cli_interface import handle_keyboard_input

# Loglama ayarları
FORMAT = "%(message)s"
logging.basicConfig(
    level=logging.INFO, 
    format=FORMAT, 
    datefmt="[%X]", 
    handlers=[RichHandler(rich_tracebacks=True)]
)
logger = logging.getLogger("bot")
console = Console()

async def main():
    """
    Ana uygulama döngüsü.
    
    Returns:
        None
    """
    # Kod başlangıcında argümanları işleyin
    parser = argparse.ArgumentParser(description='Telegram Bot')
    parser.add_argument('--cli', action='store_true', help='CLI arayüzünü etkinleştir')
    parser.add_argument('--tdlib', action='store_true', help='TDLib grup keşif servisini etkinleştir')
    args = parser.parse_args()

    console.print("[bold green]Telegram Bot başlatılıyor...[/bold green]")
    
    # Yapılandırma yükle
    config = Config()
    
    # Veritabanı bağlantısı
    try:
        # Yapılandırma dosyasından veritabanı yolunu al
        if hasattr(config, 'database') and hasattr(config.database, 'path'):
            # SQLite için
            db_path = config.database.path
        else:
            # Varsayılan yol
            db_path = 'data/bot.db'
            
        # Database nesnesini doğru şekilde oluştur
        db = Database(db_path)
        await db.connect()
    except Exception as e:
        console.print(f"[bold red]Veritabanı bağlantısı hatası: {str(e)}[/bold red]")
        logger.error(f"Veritabanı bağlantısı başarısız: {str(e)}")
        sys.exit(1)
    
    # TelegramClient oluştur
    client = TelegramClient(
        config.telegram.session_name,
        config.telegram.api_id,
        config.telegram.api_hash,
        proxy=config.telegram.proxy if hasattr(config.telegram, 'proxy') else None
    )
    
    # Durdurma sinyali
    stop_event = asyncio.Event()
    
    try:
        # Telethon istemcisini başlat
        await client.start(bot_token=config.telegram.bot_token)
        
        # Bot bilgilerini göster
        me = await client.get_me()
        console.print(f"[bold]Bot başlatıldı: @{me.username}[/bold]")
        
        # Servis fabrikası ve yöneticisi
        service_factory = ServiceFactory(client, config, db, stop_event)
        service_manager = ServiceManager(service_factory)
        
        # Servisleri oluştur ve başlat
        await service_manager.create_and_register_services([
            'user',     # Kullanıcı servisi
            'group',    # Grup servisi
            'reply',    # Yanıt servisi
            'dm',       # DM servisi
            'invite'    # Davet servisi
        ])
        
        # TDLib Discovery servisini başlat (opsiyonel)
        tdlib_discovery = None
        if args.tdlib or config.get_setting('use_tdlib', False):
            tdlib_discovery = service_factory.create_discovery_service()
            if tdlib_discovery:
                await tdlib_discovery.initialize()
                await tdlib_discovery.start()
                logger.info("TDLib grup keşif servisi başlatıldı")
        
        # Servisleri başlat
        await service_manager.start_services()
        
        # CLI arayüzü için koşullu başlatma
        if args.cli:
            keyboard_task = asyncio.create_task(handle_keyboard_input(
                services={
                    'user': service_manager.services.get('user'),  # get() kullan, KeyError önler
                    'group': service_manager.services.get('group'),  # Yoksa None döner
                    'reply': service_manager.services.get('reply'),
                    'dm': service_manager.services.get('dm'),
                    'invite': service_manager.services.get('invite'),
                    'service_manager': service_manager,  
                    'user_db': db
                }, 
                start_time=datetime.now()
            ))
        
        # Signal handler tanımla
        loop = asyncio.get_event_loop()
        
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown(service_manager, client, db, stop_event)))
        
        # Bot bilgilerini göster
        console.print(f"[bold green]Bot aktif - {datetime.now().strftime('%d.%m.%Y %H:%M')}[/bold green]")
        
        # İstemci bağlantısını koru
        await client.run_until_disconnected()
        
    except Exception as e:
        console.print(f"[bold red]Hata: {str(e)}[/bold red]")
        logger.exception("Bot çalışırken bir hata oluştu")
        
    finally:
        # Uygulama kapanışı
        await shutdown(service_manager, client, db, stop_event)
        
async def shutdown(service_manager, client, db, stop_event):
    """
    Uygulamayı güvenli bir şekilde kapatır.
    
    Args:
        service_manager: Servis yöneticisi
        client: Telethon istemcisi
        db: Veritabanı bağlantısı
        stop_event: Durdurma sinyali
        
    Returns:
        None
    """
    console.print("[bold yellow]Bot kapatılıyor...[/bold yellow]")
    
    # Durdurma sinyalini tetikle
    stop_event.set()
    
    # Klavye girdisi işleme taskını iptal et
    for task in asyncio.all_tasks():
        if task.get_name().startswith('handle_keyboard'):
            task.cancel()
    
    # Servisleri durdur
    await service_manager.stop_services()
    
    # Telethon istemcisini kapat
    if client.is_connected():
        await client.disconnect()
    
    # Veritabanı bağlantısını kapat
    await db.disconnect()
    
    console.print("[bold red]Bot kapatıldı.[/bold red]")
    
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("[bold yellow]Klavye kesintisi ile sonlandırıldı.[/bold yellow]")
    sys.exit(0)
