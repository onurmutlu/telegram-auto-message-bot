#!/usr/bin/env python3
"""
# ============================================================================ #
# Dosya: main.py
# Yol: /Users/siyahkare/code/telegram-bot/unified/main.py
# İşlev: Birleştirilmiş Telegram bot başlatma modülü
#
# © 2025 SiyahKare Yazılım - Tüm Hakları Saklıdır
# ============================================================================ #
"""

import argparse
import asyncio
import logging
import os
import signal
import sys
from datetime import datetime
import shutil
import subprocess
from pathlib import Path

# Proje kök dizinini Python yoluna ekle
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
import psycopg2
from telethon import TelegramClient
from telethon.sessions import StringSession
from logging.handlers import RotatingFileHandler
from telethon.errors import SessionPasswordNeededError, UnauthorizedError
from rich.console import Console

# Gerekli dizinleri oluştur
def create_required_directories():
    """Uygulama için gerekli dizinleri oluşturur"""
    directories = [
        'data',
        'session',
        'logs',
        'runtime',
        'runtime/logs',
        'runtime/database',
        'runtime/sessions'
    ]
    
    for directory in directories:
        try:
            os.makedirs(directory, exist_ok=True)
            print(f"Dizin oluşturuldu/kontrol edildi: {directory}")
        except Exception as e:
            print(f"Dizin oluşturma hatası ({directory}): {str(e)}")

# .env dosyasını yükle
load_dotenv()

# Uygulama başlatılmadan önce dizinleri oluştur
create_required_directories()

# Komut satırı argümanlarını işle
def parse_arguments():
    """Komut satırı argümanlarını işler"""
    parser = argparse.ArgumentParser(description="Telegram Bot")
    parser.add_argument("--debug", action="store_true", help="Debug modunu etkinleştirir")
    parser.add_argument("--clean", action="store_true", help="Başlamadan önce temizlik yapar")
    parser.add_argument("--config", help="Belirli bir yapılandırma dosyası kullanır")
    parser.add_argument("--service", help="Belirli bir servisi başlatır (grup, mesaj, davet)")
    return parser.parse_args()

# Yapılandırma yükleme
def load_configuration(config_path=None):
    """Yapılandırma bilgisini yükler"""
    try:
        from bot.config import Config
        
        # Çevre değişkenlerinden bir yapılandırma sözlüğü oluştur
        config_dict = {
            'api_id': os.getenv('API_ID'),
            'api_hash': os.getenv('API_HASH'),
            'database_url': os.getenv('DATABASE_URL'),
            'bot_token': os.getenv('BOT_TOKEN')
        }
        
        # Belirli bir yapılandırma dosyası belirtilmişse kullan
        if config_path and os.path.exists(config_path):
            # Özel yapılandırma dosyası işleme kodu buraya gelecek
            print(f"Yapılandırma dosyası yükleniyor: {config_path}")
        
        return Config(config_dict)
    except ImportError:
        print("Config sınıfı bulunamadı, basit bir yapılandırma kullanılacak")
        
        # Basit bir config sınıfı tanımla
        class SimpleConfig:
            def __init__(self, config_dict=None):
                self._config = config_dict or {}
                
            def get(self, key, default=None):
                return self._config.get(key, default)
        
        # Çevre değişkenlerinden bir yapılandırma sözlüğü oluştur
        config_dict = {
            'api_id': os.getenv('API_ID'),
            'api_hash': os.getenv('API_HASH'),
            'database_url': os.getenv('DATABASE_URL'),
            'bot_token': os.getenv('BOT_TOKEN')
        }
        
        return SimpleConfig(config_dict)

# Log yapılandırması
def configure_logging(debug_mode=False):
    """Log yapılandırmasını yapar."""
    # Varsayılan olarak INFO seviyesini kullan
    log_level = logging.DEBUG if debug_mode else logging.INFO
    
    # Root logger
    root_logger = logging.getLogger()
    
    # Önce tüm eski handler'ları temizle
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)
    
    # Ana log seviyesini ayarla
    root_logger.setLevel(log_level)
    
    # Konsol handler - Rich formatıyla
    from rich.logging import RichHandler
    console_handler = RichHandler(
        level=log_level,
        rich_tracebacks=True,
        show_time=False,
        omit_repeated_times=True
    )
    
    # Ana log dosyası için dönen dosya handler
    log_file_path = "runtime/logs/bot.log"
    file_handler = RotatingFileHandler(
        log_file_path, 
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=10,             # 10 adet yedek dosya
        encoding="utf-8"
    )
    file_handler.setLevel(log_level)
    
    # Hata logları için ayrı bir dosya
    error_log_path = "runtime/logs/errors.log"
    error_file_handler = RotatingFileHandler(
        error_log_path, 
        maxBytes=5 * 1024 * 1024,   # 5MB
        backupCount=5,              # 5 adet yedek dosya
        encoding="utf-8"
    )
    error_file_handler.setLevel(logging.ERROR)  # Sadece ERROR ve üstü

    # Formatlayıcılar
    detailed_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s"
    )
    simple_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Formatlayıcıları ayarla
    file_handler.setFormatter(detailed_formatter)
    error_file_handler.setFormatter(detailed_formatter)
    
    # Root logger'a handler'ları ekle
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(error_file_handler)
    
    # Daha az ayrıntılı loglama için bazı modüllerin seviyelerini artır
    noise_loggers = [
        'telethon', 'asyncio', 'urllib3', 'aiosqlite', 
        'matplotlib', 'PIL', 'httpx', 'httpcore'
    ]
    
    for logger_name in noise_loggers:
        logging.getLogger(logger_name).setLevel(logging.WARNING)
    
    return root_logger

# PostgreSQL veritabanı kurulumu
def setup_postgres_db():
    """PostgreSQL veritabanı bağlantısını kurar"""
    try:
        from bot.utils.postgres_db import setup_postgres_db
        return setup_postgres_db()
    except ImportError:
        print("PostgreSQL bağlantı modülü bulunamadı, basit bir bağlantı kurulacak.")
        try:
            # Basit bir bağlantı dene
            conn = psycopg2.connect(
                host=os.getenv('POSTGRES_HOST', 'localhost'),
                port=os.getenv('POSTGRES_PORT', '5432'),
                dbname=os.getenv('POSTGRES_DB', 'telegram_bot'),
                user=os.getenv('POSTGRES_USER', 'postgres'),
                password=os.getenv('POSTGRES_PASSWORD', '')
            )
            print("PostgreSQL bağlantısı başarıyla kuruldu.")
            return conn
        except Exception as e:
            print(f"PostgreSQL bağlantı hatası: {str(e)}")
            return None

# Telegram istemcisi kurulumu
async def setup_telegram_client(config):
    """Telegram istemcisini kurar ve başlatır"""
    try:
        session_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "session")
        os.makedirs(session_dir, exist_ok=True)
        
        # API kimlik bilgilerini al
        api_id = config.get('api_id')
        api_hash = config.get('api_hash')
        
        # Eksik API kimlik bilgilerini kontrol et
        if not api_id or not api_hash:
            print("UYARI: API kimlik bilgileri eksik, lütfen .env dosyasını kontrol edin.")
            print("API_ID ve API_HASH değerlerini my.telegram.org adresinden alabilirsiniz.")
            # Kullanıcıdan giriş iste
            if not api_id:
                api_id = input("API ID: ")
            if not api_hash:
                api_hash = input("API Hash: ")
        
        # Session dosyasının yolunu belirle
        session_path = os.path.join(session_dir, "bot_session")
        
        # Telegram istemcisi oluştur
        client = TelegramClient(
            session_path,
            api_id,
            api_hash
        )
        
        # Oturum aç
        await client.start()
        
        if not await client.is_user_authorized():
            print("Kullanıcı oturumu bulunamadı. Giriş yapılması gerekiyor.")
            
            # Telefon numarasını önce .env dosyasından almayı dene
            phone = os.getenv('PHONE')
            
            # Eğer .env'de telefon numarası yoksa kullanıcıdan iste
            if not phone:
                phone = input("Telefon numarası (+905xxxxxxxxx): ")
            else:
                print(f"Telefon numarası .env dosyasından alındı: {phone}")
                
            await client.send_code_request(phone)
            code = input("Telegram'dan aldığınız kodu girin: ")
            
            try:
                await client.sign_in(phone, code)
                print(f"Giriş başarılı! Oturum bilgileri {session_path} dosyasına kaydedildi.")
                print("Bundan sonraki oturumlarda tekrar giriş yapmanız gerekmeyecek.")
            except SessionPasswordNeededError:
                password = input("İki faktörlü kimlik doğrulama şifrenizi girin: ")
                await client.sign_in(password=password)
                print(f"Giriş başarılı! Oturum bilgileri {session_path} dosyasına kaydedildi.")
                print("Bundan sonraki oturumlarda tekrar giriş yapmanız gerekmeyecek.")
        else:
            me = await client.get_me()
            print(f"Mevcut oturum kullanılıyor: {me.first_name} (@{me.username})")
        
        return client
    except Exception as e:
        print(f"Telegram istemcisi başlatma hatası: {str(e)}")
        # Daha önceden yaratılmış bir istemci var mı kontrol et
        if 'client' in locals() and isinstance(client, TelegramClient):
            return client
        else:
            raise  # Hatayı tekrar fırlat

# Servis başlatma
async def start_service(service_name, client, config, db):
    """Belirli bir servisi başlatır"""
    try:
        from bot.services.service_factory import ServiceFactory
        from bot.services.service_manager import ServiceManager
        
        # Kapatma olayı
        stop_event = asyncio.Event()
        
        # ServiceFactory ve ServiceManager kullanarak servisleri yönet
        service_factory = ServiceFactory(client, config, db, stop_event)
        
        # Service manager'ı global değişken olarak tanımla
        global service_manager
        service_manager = ServiceManager(service_factory, client, config, db, stop_event)
        
        # Aktif servisleri belirle
        active_services = service_manager.active_services
        
        if service_name:
            # Belirli bir servisi başlat
            service = service_factory.create_service(service_name)
            if service:
                print(f"{service_name} servisi başlatılıyor...")
                await service.initialize()
                await service.run()
            else:
                print(f"Hata: {service_name} servisi bulunamadı")
        else:
            # Tüm servisleri başlat
            await service_manager.create_and_register_services(active_services)
            await service_manager.start_services()
        
        return service_manager
    except ImportError as e:
        print(f"Servis modüllerini yüklerken hata: {str(e)}")
        print("Bot, servis yapılandırması olmadan çalışıyor.")
        # Basit bir servis manager nesnesi döndür
        class SimpleServiceManager:
            async def stop(self):
                pass
            
            async def initialize(self):
                pass
                
            async def run(self):
                pass
                
            async def stop_all_services(self):
                pass
                
            def get_service(self, name):
                return None
                
            async def get_status(self):
                return {}
                
        return SimpleServiceManager()
    except NameError as e:
        print(f"Servis sınıfı tanımı hatası: {str(e)}")
        print("Bot, servis yapılandırması olmadan çalışıyor.")
        # Basit bir servis manager nesnesi döndür
        class SimpleServiceManager:
            async def stop(self):
                pass
            
            async def initialize(self):
                pass
                
            async def run(self):
                pass
                
            async def stop_all_services(self):
                pass
                
            def get_service(self, name):
                return None
                
            async def get_status(self):
                return {}
                
        return SimpleServiceManager()

# Ana döngü
async def main():
    """Ana uygulama fonksiyonu"""
    # Rich konsol nesnesi
    console = Console()
    
    # Kapatma olayı
    shutdown_event = asyncio.Event()
    
    # Banner'ı göster
    try:
        from bot.utils.cli_interface import print_banner
        print_banner()
    except ImportError:
        # Bot modülü bulunamazsa basit bir banner göster
        print("\n")
        print("╔════════════════════════════════════════════════════════════╗")
        print("║          TELEGRAM AUTO MESSAGE BOT v3.5.0          ║")
        print("║               Author: @siyahkare               ║")
        print("║     Ticari Ürün - Tüm Hakları Saklıdır © 2025     ║")
        print("╚════════════════════════════════════════════════════════════╝")
        print("\nBu yazılım, SiyahKare Yazılım tarafından geliştirilmiş ticari bir ürünüdür.")
        print("\n")
    
    # Argümanları işle
    args = parse_arguments()
    
    # Loglama yapılandırması
    logger = configure_logging(debug_mode=args.debug)
    logger.info("Bot başlatılıyor...")
    
    try:
        # Temizlik yapılacaksa yap
        if args.clean:
            logger.info("Temizlik yapılıyor...")
            try:
                subprocess.run([sys.executable, "tools/cleanup.py", "--all"], check=True)
            except Exception as e:
                logger.error(f"Temizlik hatası: {str(e)}")
        
        # Yapılandırma yükle
        logger.info("Yapılandırma yükleniyor...")
        config = load_configuration(args.config)
        
        # PostgreSQL veritabanını kur
        logger.info("PostgreSQL veritabanına bağlanılıyor...")
        db_conn = setup_postgres_db()
        if not db_conn:
            logger.error("PostgreSQL veritabanı bağlantısı kurulamadı. Uygulama durduruluyor.")
            return
        
        # Veritabanı bağlantısı
        logger.info("Ana veritabanına bağlanılıyor...")
        try:
            from database.user_db import UserDatabase
            user_db = UserDatabase(config.get('database_url'))
        except ImportError:
            logger.warning("Kullanıcı veritabanı modülü bulunamadı, basit bir veritabanı kullanılacak")
            # Basit bir veritabanı sınıfı tanımla
            class SimpleUserDB:
                def __init__(self, connection_string=None):
                    self.connection_string = connection_string
                    logger.info("Basit veritabanı başlatıldı")
                
                def get(self, key, default=None):
                    return default
            
            user_db = SimpleUserDB(config.get('database_url'))
        
        # Telegram istemcisi kur
        logger.info("Telegram istemcisi başlatılıyor...")
        client = await setup_telegram_client(config)
        
        # Botun bağlı olduğunu göster
        me = await client.get_me()
        logger.info(f"Bağlantı başarılı: {me.first_name} (@{me.username})")
        
        # Bot kontrol durumunu güncelle
        bot_running = True
        bot_control = {'is_running': True, 'start_time': datetime.now()}
        
        # Klavye giriş görevini başlat
        try:
            from bot.utils.cli_interface import handle_keyboard_input
            
            # Basit bir service_manager oluştur (eğer gerçek service_manager yoksa)
            class SimpleServiceManager:
                def __init__(self):
                    self.services = {}
                
                async def get_status(self):
                    return {}
                
                async def stop_all_services(self):
                    pass
                
                def get_service(self, name):
                    return None
            
            simple_manager = SimpleServiceManager()
            
            # Gerçek service_manager'ı kullan veya basit olanı kullan
            service_mgr = service_manager if 'service_manager' in locals() else simple_manager
            
            # Doğru parametrelerle handle_keyboard_input çağır
            input_task = asyncio.create_task(
                handle_keyboard_input(console, service_mgr, shutdown_event)
            )
        except ImportError:
            logger.warning("Klavye giriş modülü bulunamadı, basit bir giriş işleyici kullanılacak")
            # Basit bir giriş işleyici oluştur
            async def simple_input_handler():
                while not shutdown_event.is_set():
                    await asyncio.sleep(1.0)
            input_task = asyncio.create_task(simple_input_handler())
        
        # Servis başlat
        service_manager = await start_service(args.service, client, config, user_db)
        
        # Sinyal işleyicileri
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
        
        # Ana görev döngüsü
        while not shutdown_event.is_set():
            # Her 1 saniyede bir kontrol et
            try:
                await asyncio.wait_for(shutdown_event.wait(), timeout=1.0)
            except asyncio.TimeoutError:
                pass
        
        # Kapatma işlemleri
        logger.info("Bot kapatılıyor...")
        
        # Servisleri durdur
        try:
            await service_manager.stop()
        except Exception as e:
            logger.error(f"Servis durdurma hatası: {str(e)}")
        
        # PostgreSQL bağlantısını kapat
        if db_conn:
            try:
                db_conn.close()
                logger.info("PostgreSQL veritabanı bağlantısı kapatıldı.")
            except Exception as e:
                logger.error(f"Veritabanı bağlantısını kapatırken hata: {str(e)}")
        
        # Klavye giriş görevini iptal et
        if not input_task.done():
            try:
                input_task.cancel()
                try:
                    await input_task
                except asyncio.CancelledError:
                    pass
            except Exception as e:
                logger.error(f"Klavye görevi kapatırken hata: {str(e)}")
        
        # Telegram istemcisini kapat
        try:
            await client.log_out()
        except Exception as e:
            logger.error(f"İstemci oturumunu kapatırken hata: {str(e)}")
        
        logger.info("Bot başarıyla kapatıldı.")
        
    except Exception as e:
        logger.error(f"Bot çalışırken hata oluştu: {str(e)}", exc_info=True)
    finally:
        # Varsa botu durdur ve kaynakları serbest bırak
        try:
            if 'client' in locals() and hasattr(client, 'disconnect'):
                logger.info("Telegram istemcisi kapatılıyor...")
                await client.disconnect()
        except Exception as e:
            logger.error(f"İstemci kapatılırken hata: {str(e)}")
        
        logger.info("Bot kapatıldı.")

# Ana başlatma fonksiyonu
def run():
    """Ana botu çalıştırır"""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Klavye kesintisi (Ctrl+C) algılandı, bot kapatıldı.")
    except Exception as e:
        print(f"Bot çalıştırılırken hata oluştu: {str(e)}")
        import traceback
        traceback.print_exc()

# Doğrudan çalıştırılırsa
if __name__ == "__main__":
    run() 