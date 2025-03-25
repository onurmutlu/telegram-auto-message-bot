"""
Telegram Auto Message Bot
------------------------
Version: 3.1
Author: @siyahkare
Description: Telegram gruplarına otomatik mesaj gönderen ve özel mesajları yöneten gelişmiş bot.
"""
import asyncio
import logging
import sys
from pathlib import Path
from colorama import init, Fore, Style

from dotenv import load_dotenv

from config.settings import Config
from database.user_db import UserDatabase
from bot.message_bot import MemberMessageBot
from utils.logger import LoggerSetup

init(autoreset=True)  # Colorama'yı başlat

async def main():
    """Ana uygulama başlatma fonksiyonu"""
    # Çevre değişkenlerini yükle
    load_dotenv()
    
    try:
        # Yapılandırmayı yükle
        config = Config.load_config()
        
        # Logger'ı ayarla
        logger = LoggerSetup.setup_logger(config.logs_path)
        
        # Başlık göster
        print_banner()
        
        logger.info("🚀 Uygulama başlatılıyor...")
        
        # Grup listesi
        GROUP_LINKS = [
            "premium_arayis",
            "arayisgruba", 
            "arayisplatin"
        ]
        
        # Veritabanını başlat
        user_db = UserDatabase(config.user_db_path)
        
        # Bot örneği oluştur
        bot = MemberMessageBot(
            api_id=config.api_id,
            api_hash=config.api_hash,
            phone=config.phone,
            group_links=GROUP_LINKS,
            user_db=user_db,
            config=config  # Config nesnesini geçiriyoruz
        )
        
        # Botu başlat
        await bot.start()
        
    except ValueError as e:
        logging.error(f"Yapılandırma hatası: {str(e)}")
    except KeyboardInterrupt:
        logging.info("Program manuel olarak durduruldu")
    except Exception as e:
        logging.error(f"Kritik hata: {str(e)}", exc_info=True)
    finally:
        logging.info("Program sonlandırılıyor...")

def print_banner():
    """Program başlık bilgisini gösterir"""
    banner = f"""
{Fore.CYAN}╔══════════════════════════════════════════════════╗
║  {Fore.GREEN}Telegram Auto Message Bot v3.1{Fore.CYAN}                 ║
║  {Fore.YELLOW}Author: @siyahkare{Fore.CYAN}                            ║
║  {Fore.WHITE}Telegram grupları için otomatik mesaj botu{Fore.CYAN}     ║
╚══════════════════════════════════════════════════╝{Style.RESET_ALL}
"""
    print(banner)

if __name__ == "__main__":
    asyncio.run(main())