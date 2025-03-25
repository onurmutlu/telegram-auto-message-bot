"""
Telegram Auto Message Bot
------------------------
Version: 3.1
Author: @siyahkare
Description: Telegram gruplarına otomatik mesaj gönderen ve özel mesajları yöneten gelişmiş bot.
License: Proprietary Commercial Software - All rights reserved
Copyright (c) 2025 Arayiş Yazılım. Tüm hakları saklıdır.

Bu yazılım, Arayiş Yazılım'ın özel mülkiyetindedir ve yalnızca lisanslı kullanıcılar tarafından,
kiralama sözleşmesi şartları dahilinde kullanılabilir. Yazılımın herhangi bir şekilde kopyalanması,
dağıtılması veya değiştirilmesi lisans sahibinin önceden yazılı izni olmadan yasaktır.
"""
import asyncio
import logging
import sys
from pathlib import Path
from colorama import init, Fore, Style
from datetime import datetime
import argparse
import traceback

from dotenv import load_dotenv

from config.settings import Config
from database.user_db import UserDatabase
from bot.message_bot import MemberMessageBot
from utils.logger import LoggerSetup

init(autoreset=True)  # Colorama'yı başlat

# Root logger yapılandırması
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Geçici hata ayıklama için konsol handler
console_debug = logging.StreamHandler(sys.stderr)
console_debug.setLevel(logging.DEBUG)
console_debug.setFormatter(logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
))
logging.getLogger('').addHandler(console_debug)

def parse_arguments():
    """Komut satırı argümanlarını ayrıştırır"""
    parser = argparse.ArgumentParser(description="Telegram Auto Message Bot")
    
    parser.add_argument('--debug', action='store_true', help='Debug modunda çalıştır')
    parser.add_argument('--reset-errors', action='store_true', help='Hata veren grupları sıfırla')
    parser.add_argument('--optimize-db', action='store_true', help='Veritabanını optimize et')
    parser.add_argument('--env', choices=['production', 'development'], default='production', 
                      help='Çalışma ortamı')
    
    return parser.parse_args()

def show_helper_info():
    """Bot çalıştırma öncesinde yardımcı bilgileri göster"""
    print(f"\n{Fore.CYAN}=== HIZLI İPUÇLARI ==={Style.RESET_ALL}")
    print(f"{Fore.GREEN}•{Style.RESET_ALL} Bot başladığında komut satırında 'h' yazarak mevcut komutları görebilirsiniz")
    print(f"{Fore.GREEN}•{Style.RESET_ALL} Bot hata verirse 'logs/bot.log' ve 'logs/errors.log' dosyalarını kontrol edin")
    print(f"{Fore.GREEN}•{Style.RESET_ALL} Uygulamayı Ctrl+C ya da 'q' komutuyla güvenli bir şekilde sonlandırın")
    print(f"{Fore.GREEN}•{Style.RESET_ALL} İnternet bağlantınızın stabil olduğundan emin olun")
    print(f"{Fore.GREEN}•{Style.RESET_ALL} Telegram API limitlerini aşmamak için mesaj gönderim ayarlarını düşük tutun\n")

async def main():
    """Ana uygulama başlatma fonksiyonu"""
    # Komut satırı argümanlarını çözümle
    args = parse_arguments()
    
    # Çevre değişkenlerini yükle
    load_dotenv()
    
    try:
        # Log ekleyelim
        logger = logging.getLogger('telegram_bot')
        
        # Yapılandırmayı yükle
        config = Config.load_config()
        
        # Ortam ayarını komut satırı argümanından güncelle
        if args.env:
            config.environment = args.env
        
        # Logger'ı ayarla
        logger = LoggerSetup.setup_logger(config.logs_path)
        
        # Başlık göster
        print_banner()
        
        # Yardımcı bilgileri göster
        show_helper_info()
        
        logger.info("🚀 Uygulama başlatılıyor...")
        
        # Grup listesi
        GROUP_LINKS = [
            "premium_arayis",
            "arayisgruba", 
            "arayisplatin"
        ]
        
        # Veritabanını başlat
        user_db = UserDatabase(config.user_db_path)
        
        # Veritabanı optimizasyonu (opsiyonel)
        if args.optimize_db:
            if user_db.optimize_database():
                print(f"{Fore.GREEN}✅ Veritabanı optimize edildi{Style.RESET_ALL}")
        
        # Uygulama başlangıç zamanını göster
        start_time = datetime.now().strftime("%H:%M:%S")
        logger.info(f"⏱️ Başlangıç zamanı: {start_time}")
        
        # Bot örneği oluştur
        bot = MemberMessageBot(
            api_id=config.api_id,
            api_hash=config.api_hash,
            phone=config.phone,
            group_links=GROUP_LINKS,
            user_db=user_db,
            config=config,
            debug_mode=args.debug  # Debug modu argümandan al
        )
        
        # Hata veren grupları sıfırla
        if args.reset_errors:
            count = user_db.clear_all_error_groups()
            print(f"{Fore.GREEN}✅ {count} hata veren grup sıfırlandı{Style.RESET_ALL}")
            
        # Botu başlat
        await bot.start()
        
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}⚠️ Kullanıcı tarafından sonlandırıldı{Style.RESET_ALL}")
        logger.info("Bot kullanıcı tarafından sonlandırıldı")
        
    except Exception as e:
        print(f"\n{Fore.RED}❌ Kritik hata: {str(e)}{Style.RESET_ALL}")
        logger.critical(f"Kritik hata: {str(e)}", exc_info=True)
        
        # Kapanış temizliği
        try:
            if 'bot' in locals() and bot:
                await bot.client.disconnect()
            if 'user_db' in locals() and user_db:
                user_db.close()
        except:
            pass
            
        # Detaylı hata bilgisi
        print(f"\n{Fore.RED}Hata ayrıntıları:{Style.RESET_ALL}")
        traceback.print_exc()
        
        print(f"\n{Fore.YELLOW}Hatalar logs/bot.log dosyasında kaydedildi{Style.RESET_ALL}")
        return 1  # Hata kodu dön
        
    return 0  # Başarılı sonlanma kodu

def print_banner():
    """Program başlık bilgisini gösterir"""
    banner = f"""
{Fore.CYAN}╔══════════════════════════════════════════════════╗
║  {Fore.GREEN}Telegram Auto Message Bot v3.1{Fore.CYAN}                 ║
║  {Fore.YELLOW}Author: @siyahkare{Fore.CYAN}                            ║
║  {Fore.WHITE}Telegram grupları için otomatik mesaj botu{Fore.CYAN}     ║
║  {Fore.RED}Ticari Ürün - Tüm Hakları Saklıdır © 2025{Fore.CYAN}      ║
╚══════════════════════════════════════════════════╝{Style.RESET_ALL}

{Fore.YELLOW}UYARI:{Style.RESET_ALL} Bu yazılım, Arayiş Yazılım'ın lisanslı bir ticari ürünüdür.
İzinsiz kullanım, kopyalama veya dağıtım yasal işlem gerektirir.
"""
    print(banner)

if __name__ == "__main__":
    asyncio.run(main())