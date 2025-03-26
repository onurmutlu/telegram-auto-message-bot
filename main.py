"""
Telegram Auto Message Bot - Ana program
"""
import os
import sys
import asyncio
import logging
import argparse
import traceback
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from colorama import Fore, Style, init
from tabulate import tabulate

# Proje modülleri
from config.settings import Config
from database.user_db import UserDatabase
from bot.message_bot import MemberMessageBot
from bot.utils.logger_setup import setup_logger, configure_console_logger, LoggerSetup

# Sabit değişkenler
GROUP_LINKS = ["sohbetgrubum", "premiumpaylasim", "teknolojisohbet"]

# Renkli çıktı desteğini ayarla
init(autoreset=True)
logger = logging.getLogger(__name__)

def is_terminal_support_color():
    """Terminal renk desteğini tespit eder"""
    # Terminal mi yoksa pipe mı?
    if not sys.stdout.isatty():
        return False
    
    # Çevre değişkenlerine bakarak destek kontrolü
    term = os.environ.get('TERM', '')
    if term == 'dumb' or 'NO_COLOR' in os.environ:
        return False
    
    return True

def parse_arguments():
    """Komut satırı argümanlarını ayrıştırır"""
    parser = argparse.ArgumentParser(description="Telegram Auto Message Bot")
    
    parser.add_argument('-d', '--debug', action='store_true', help='Debug modunda çalıştır')
    parser.add_argument('-r', '--reset-errors', action='store_true', help='Hata veren grupları sıfırla')
    parser.add_argument('-o', '--optimize-db', action='store_true', help='Veritabanını optimize et')
    parser.add_argument('-e', '--env', choices=['production', 'development'], default='production', 
                      help='Çalışma ortamı')
    parser.add_argument('-b', '--backup', action='store_true', help='Başlangıçta veritabanı yedeği al')
    
    return parser.parse_args()

def show_helper_info():
    """Bot çalıştırma öncesinde yardımcı bilgileri göster"""
    tips = [
        ["h", "Mevcut komutları gösterme"],
        ["logs/", "Hata kayıtlarına erişim"],
        ["Ctrl+C / q", "Güvenli kapatma"],
        ["İnternet", "Stabil bağlantı gerekli"],
        ["Limitler", "Mesaj gönderim ayarlarını düşük tutun"]
    ]
    
    print(f"\n{Fore.CYAN}=== HIZLI İPUÇLARI ==={Style.RESET_ALL}")
    print(tabulate(tips, headers=["Konu", "Açıklama"], tablefmt="simple"))
    print()

def print_banner():
    """Program başlık bilgisini gösterir"""
    print(f"{Fore.CYAN}╔══════════════════════════════════════════════╗")
    print(f"{Fore.CYAN}║ {Fore.GREEN}TELEGRAM AUTO MESSAGE BOT v3.3{Fore.CYAN}                ║")
    print(f"{Fore.CYAN}║ {Fore.YELLOW}Author: @siyahkare{Fore.CYAN}                            ║")
    print(f"{Fore.CYAN}║ {Fore.RED}Ticari Ürün - Tüm Hakları Saklıdır © 2025{Fore.CYAN}      ║")
    print(f"{Fore.CYAN}╚══════════════════════════════════════════════╝{Style.RESET_ALL}")
    print(f"\nBu yazılım, SiyahKare Yazılım tarafından geliştirilmiş ticari bir ürünüdür.")

async def main():
    """Ana uygulama başlatma fonksiyonu"""
    # Komut satırı argümanlarını çözümle
    args = parse_arguments()
    
    # Çevre değişkenlerini yükle
    load_dotenv()
    
    try:
        # Renkli çıktı desteğini ayarla
        init(autoreset=True, strip=not is_terminal_support_color())

        # Log ekleyelim
        logger = logging.getLogger('telegram_bot')
        
        # Konsol handler'ı ekle - yeni modülden al
        console_handler = configure_console_logger(
            level=logging.DEBUG if args.debug else logging.INFO
        )
        logging.getLogger('').addHandler(console_handler)
        
        # Yapılandırmayı yükle
        config = Config.load_config()
        
        # Ortam ayarını komut satırı argümanından güncelle
        if args.env:
            config.environment = args.env
        
        # Logger'ı ayarla - config nesnesi ile
        logger = LoggerSetup.setup_logger(config)
        
        # Başlık göster
        print_banner()
        
        # Yardımcı bilgileri göster
        show_helper_info()
        
        logger.info("🚀 Uygulama başlatılıyor...")
        
        # API Kimlik bilgilerini al
        api_id, api_hash, phone = Config.load_api_credentials()
        
        # Veritabanını başlat
        user_db = UserDatabase(config.user_db_path)
        
        # Veritabanı optimizasyonu (opsiyonel)
        if args.optimize_db:
            user_db.optimize_database()
            print(f"{Fore.GREEN}✅ Veritabanı optimize edildi{Style.RESET_ALL}")
        
        # Başlangıç zamanını kaydet
        start_time = datetime.now().strftime("%H:%M:%S")
        logger.info(f"⏱️ Başlangıç zamanı: {start_time}")
        
        # Mesajlaşma botunu oluştur
        bot = MemberMessageBot(
            api_id=api_id, 
            api_hash=api_hash,
            phone=phone,
            group_links=GROUP_LINKS,
            user_db=user_db,
            config=config,
            debug_mode=args.debug  # Debug modu argümandan al
        )
        
        # Hata gruplarını sıfırlama (opsiyonel)
        if args.reset_errors:
            cleared = user_db.clear_all_error_groups()
            print(f"{Fore.GREEN}✅ {cleared} hata grubu temizlendi{Style.RESET_ALL}")
        
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

if __name__ == "__main__":
    # Async olarak ana fonksiyonu çalıştır
    exit_code = asyncio.run(main())
    sys.exit(exit_code)