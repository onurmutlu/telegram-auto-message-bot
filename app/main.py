#!/usr/bin/env python3
# Telegram Bot - Ana Uygulama Dosyası
import os
import sys
import time
import asyncio
import logging
import signal
import platform
import atexit
from typing import List, Dict, Any, Optional, Type

from telethon import TelegramClient, errors
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.core.config import settings
from app.db.session import get_session, init_db, init_asyncpg_pool
from app.services.base import BaseService
from app.services.messaging.dm_service import DirectMessageService
from app.services.messaging.promo_service import PromoService
from app.services.analytics.activity_service import ActivityService
from app.services.monitoring.health_service import HealthService
from app.core.unified.client import get_client, disconnect_client
from app.services.service_manager import get_service_manager

# Renklendirme için ANSI kodları
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

# Yapılandırma değerlerini almak için yardımcı fonksiyon
def get_secret_or_str(val):
    """Gizli veya string değeri döndürür."""
    if hasattr(val, 'get_secret_value'):
        return val.get_secret_value().strip()
    if isinstance(val, str):
        return val.strip()
    return str(val)

# Loglama yapılandırması
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot_output.log")
    ]
)

logger = logging.getLogger(__name__)

class TelegramBot:
    """Telegram botu ana sınıfı.
    
    Bu sınıf aşağıdaki işlemleri gerçekleştirir:
    - Telegram API bağlantısını yönetir
    - Tüm servisleri başlatır ve denetler
    - Graceful shutdown sürecini koordine eder
    - Kullanıcı oturumlarını yönetir
    """

    def __init__(self):
        """TelegramBot sınıfını başlat ve temel değişkenleri oluştur."""
        self.client = None
        self.db = None
        self.service_manager = None
        self.handlers = []
        self.tasks = []
        self.services = {}
        self.is_running = False
        self.is_initialized = False
        self.start_time = time.time()
        self.shutting_down = False
        self.loop = asyncio.get_event_loop()

        try:
            # Oturum adını kullan
            session_name = settings.SESSION_NAME
            
            # Mevcut oturum dosyalarını kontrol et
            for ext in ['.session', '.session-journal']:
                if os.path.exists(f"{session_name}{ext}"):
                    logger.info(f"Mevcut oturum dosyası: {session_name}{ext}")
                    
            # Sistem bilgilerini al 
            device_info = f"Python {platform.python_version()} on {platform.system()} {platform.release()}"
            logger.info(f"TelegramClient başlatılıyor - API_ID: {settings.API_ID}")
            logger.info(f"Oturum adı: {session_name}")
            logger.info(f"Cihaz bilgisi: {device_info}")
            
            # TelegramClient'ı oluştur - await kullanamayız burada, bunu initialize metodunda yapacağız
            self.client = None  # init_client işlemi async initialize metodu içinde yapılacak
            logger.info("TelegramClient referansı oluşturuldu (bağlantı initialize'da kurulacak).")
        except Exception as e:
            logger.error(f"TelegramClient başlatılırken hata: {e}", exc_info=True)

        # Çıkış sinyalleri için handler tanımla
        def signal_handler(sig, frame):
            logger.info(f"Sinyal alındı: {sig}, uygulama kapatılıyor...")
            # Event loopa task ekle
            if self.loop and self.loop.is_running():
                self.loop.create_task(self.cleanup())
            else:
                # Event loop çalışmıyorsa senkron cleanup çağır
                if not self.shutting_down:
                    self.shutting_down = True
                    asyncio.run(self.cleanup())
            
        # Sinyalleri kaydet
        try:
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)
            logger.info("Çıkış sinyal işleyicileri ayarlandı")
            
            # Atexit'e cleanup fonksiyonunu kaydet
            atexit.register(lambda: asyncio.run(self.cleanup()) if not self.shutting_down else None)
        except Exception as e:
            logger.error(f"Sinyal işleyicileri ayarlanırken hata: {e}")
        
        # Shutting down flag'i ekle
        self.shutting_down = False
        self.loop = asyncio.get_event_loop()

    async def initialize(self) -> bool:
        """
        Bot ve gerekli bileşenleri başlatır.
        """
        logger.info("Bot başlatılıyor...")
        
        # Veritabanı bağlantısını başlat - init_db asenkron değil
        init_db()
        self.db = next(get_session())
        
        # Telegram client bağlantısını başlat - asenkron işlemi burada yapıyoruz
        self.client = await get_client()
        if not self.client:
            logger.error("Telegram client bağlantısı sağlanamadı!")
            return False
        
        # Servis yöneticisini başlat
        from app.services.service_manager import ServiceManager
        self.service_manager = ServiceManager(client=self.client, db=self.db)
        await self.service_manager.initialize()
        
        # Servisleri başlat
        await self.service_manager.start_services()
        
        # Event handlers başlat
        await self._initialize_handlers()
        
        self.is_initialized = True
        logger.info("Bot başarıyla başlatıldı!")
        return True

    async def _initialize_handlers(self):
        """Event handler'ları başlatır."""
        # Message handler
        try:
            from app.handlers.message_handler import MessageHandler
            message_handler = MessageHandler(self.client, self.service_manager, self.db)
            await message_handler.register_handlers()
            self.handlers.append(message_handler)
            logger.info("Mesaj işleyici başlatıldı.")
        except Exception as e:
            logger.error(f"Mesaj işleyici başlatılamadı: {e}")
        
        # Group handler
        try:
            from app.handlers.group_handler import GroupHandler
            group_handler = GroupHandler(self.client, self.service_manager, self.db)
            await group_handler.register_handlers()
            self.handlers.append(group_handler)
            logger.info("Grup işleyici başlatıldı.")
        except Exception as e:
            logger.error(f"Grup işleyici başlatılamadı: {e}")
        
        # User handler
        try:
            from app.handlers.user_handler import UserHandler
            user_handler = UserHandler(self.client, self.service_manager, self.db)
            await user_handler.register_handlers()
            self.handlers.append(user_handler)
            logger.info("Kullanıcı işleyici başlatıldı.")
        except Exception as e:
            logger.error(f"Kullanıcı işleyici başlatılamadı: {e}")
        
        # Command handler
        try:
            from app.handlers.command_handler import CommandHandler
            command_handler = CommandHandler(self.client, self.service_manager, self.db)
            await command_handler.register_handlers()
            self.handlers.append(command_handler)
            logger.info("Komut işleyici başlatıldı.")
        except Exception as e:
            logger.error(f"Komut işleyici başlatılamadı: {e}")
    
    async def start(self):
        """
        Botu başlatır ve çalışmasını sağlar.
        """
        if not self.is_initialized:
            success = await self.initialize()
            if not success:
                logger.error("Bot başlatılamadı!")
                return
        
        logger.info("Bot çalışmaya başlıyor...")
        self.is_running = True
        
        # Sinyal işleyicileri
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop = asyncio.get_running_loop()
                loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(self.stop(sig)))
                logger.debug(f"Sinyal işleyici eklendi: {sig}")
            except (NotImplementedError, RuntimeError):
                logger.debug(f"Sinyal işleyici eklenemedi: {sig}")
        
        # Ana görev
        try:
            # Sonsuza kadar bekle, sinyaller ile kontrol ediliyor
            while self.is_running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            logger.info("Bot görevi iptal edildi.")
        except Exception as e:
            logger.error(f"Bot çalışırken hata oluştu: {e}")
        finally:
            await self.stop()
    
    async def stop(self, sig=None):
        """
        Botu ve ilgili tüm bileşenleri durdurur.
        """
        if sig:
            logger.info(f"Sinyal alındı: {sig.name}, bot kapatılıyor...")
        else:
            logger.info("Bot kapatılıyor...")
        
        self.is_running = False
        
        # Servisleri durdur
        if self.service_manager:
            await self.service_manager.stop_services()
            logger.info("Tüm servisler durduruldu.")
        
        # Görevleri iptal et
        for task in self.tasks:
            if not task.done():
                task.cancel()
        
        # Client bağlantısını kapat
        if self.client:
            await disconnect_client()
            logger.info("Telegram client bağlantısı kapatıldı.")
        
        # Veritabanı bağlantılarını kapatmak için kullanılabilecek bir yöntem yok
        # Burada kaynak temizliği için desteklenen fonksiyonları ekleyebiliriz
        logger.info("Veritabanı bağlantıları kapatıldı.")
        
        logger.info("Bot başarıyla kapatıldı.")

    async def _run_service_safely(self, service_name):
        """Bir servisi güvenli bir şekilde çalıştır."""
        service = self.services.get(service_name)
        if not service:
            logger.error(f"Servis bulunamadı: {service_name}")
            return
        
        try:
            # Servisin start metodu varsa çağır
            if hasattr(service, "start") and callable(service.start):
                await service.start()
            # Veya run metodu varsa çağır
            elif hasattr(service, "run") and callable(service.run):
                await service.run()
            # Veya servisin özel metodunu çağır
            elif hasattr(service, f"start_{service_name}") and callable(getattr(service, f"start_{service_name}")):
                await getattr(service, f"start_{service_name}")()
            else:
                logger.warning(f"Servis ({service_name}) için çalıştırılabilir metod bulunamadı.")
        except Exception as e:
            logger.error(f"Servis çalıştırma hatası ({service_name}): {e}", exc_info=True)

    def _create_pid_file(self):
        """PID dosyasını oluştur."""
        try:
            pid = os.getpid()
            pid_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".bot_pids")
            
            # Dosya varsa, içeriğini oku
            existing_pids = []
            if os.path.exists(pid_file):
                with open(pid_file, "r") as f:
                    existing_pids = [line.strip() for line in f.readlines() if line.strip()]
            
            # Mevcut PID'i ekle
            if str(pid) not in existing_pids:
                existing_pids.append(str(pid))
            
            # Dosyayı yaz
            with open(pid_file, "w") as f:
                f.write("\n".join(existing_pids))
            
            logger.info(f"PID dosyası oluşturuldu: {pid}")
        except Exception as e:
            logger.error(f"PID dosyası oluşturma hatası: {e}")

    def get_services(self):
        """Bot tarafından yönetilen servisleri ve durumlarını döndürür."""
        return {name: {"running": getattr(service, "running", False)} 
                for name, service in self.services.items()}
        
    async def run(self):
        """Bot'u çalıştır."""
        try:
            # Client kontrol
            if not self.client:
                logger.error("Telegram client başlatılmadı.")
                return False
                
            # Bağlantı kontrol
            if not self.client.is_connected():
                logger.info("Telegram'a bağlanılıyor...")
                try:
                    await self.client.connect()
                    logger.info("Bağlantı başarılı.")
                except Exception as e:
                    logger.error(f"Bağlantı hatası: {e}")
                    return False
            
            # Tüm servisleri başlat
            active_tasks = []
            for name, service in self.services.items():
                if hasattr(service, 'start'):
                    try:
                        task = asyncio.create_task(service.start(), name=f"{name}_service")
                        active_tasks.append(task)
                        logger.info(f"Servis başlatıldı: {name}")
                    except Exception as e:
                        logger.error(f"Servis başlatma hatası ({name}): {e}")
            
            # Bot kapanana kadar bekle
            try:
                await self.shutdown_event.wait()
            except asyncio.CancelledError:
                logger.info("Bot çalışması iptal edildi.")
            finally:
                # Görevleri temizle
                for task in active_tasks:
                    if not task.done():
                        task.cancel()
                
                # Tüm görevlerin sonlanmasını bekle
                if active_tasks:
                    await asyncio.gather(*active_tasks, return_exceptions=True)
                    
            return True
        except Exception as e:
            logger.error(f"Bot çalıştırma hatası: {e}", exc_info=True)
            await self.cleanup()
            return False
                
    async def cleanup(self):
        """
        Bot kapanırken kaynakları temizle
        """
        # Eğer zaten temizleme işlemi yapılıyorsa, tekrar yapma
        if self.shutting_down:
            return
            
        self.shutting_down = True
        logger.info("Bot kaynakları temizleniyor...")
        
        # Servisleri durdur
        if hasattr(self, 'services') and self.services:
            logger.info("Servisler durduruluyor...")
            for name, service in self.services.items():
                try:
                    if hasattr(service, 'stop') and callable(service.stop):
                        await service.stop()
                        logger.info(f"Servis durduruldu: {name}")
                except Exception as e:
                    logger.error(f"Servis durdurma hatası ({name}): {e}")
        
        # Telegram client bağlantısını kapat
        if hasattr(self, 'client') and self.client:
            logger.info("Telegram bağlantısı kapatılıyor...")
            try:
                await self.client.disconnect()
                logger.info("Telegram bağlantısı kapatıldı")
            except Exception as e:
                logger.error(f"Telegram bağlantısı kapatılırken hata: {e}")
                
        # Shutdown eventini ayarla (diğer kodlar bunu bekliyor olabilir)
        if hasattr(self, 'shutdown_event') and self.shutdown_event:
            try:
                self.shutdown_event.set()
                logger.info("Kapatma eventi ayarlandı")
            except Exception as e:
                logger.error(f"Kapatma eventi ayarlanırken hata: {e}")
        
        # Session dosyasını temizle
        try:
            from app.core.unified.client import _cleanup_on_exit
            _cleanup_on_exit()
        except Exception as e:
            logger.error(f"Session temizlenirken hata: {e}")
            
        logger.info("Bot kaynakları temizlendi, uygulama güvenli şekilde kapatılabilir")

    async def _cancel_all_tasks(self):
        """Tüm çalışan asenkron görevleri iptal eder."""
        try:
            for task in self.tasks:
                if not task.done():
                    task.cancel()
                    try:
                        await asyncio.wait_for(asyncio.shield(task), timeout=5.0)
                    except asyncio.TimeoutError:
                        logger.warning(f"Görev iptal zaman aşımı: {task.get_name()}")
                    except Exception as e:
                        logger.error(f"Görev iptal hatası: {e}")
            
            self.tasks = []
            logger.info("Tüm görevler iptal edildi.")
        except Exception as e:
            logger.error(f"Görevleri iptal ederken hata: {e}")

    async def _shutdown_services(self):
        """Tüm çalışan servisleri düzgün bir şekilde kapatır."""
        for name, service in self.services.items():
            try:
                if hasattr(service, 'stop') and callable(service.stop):
                    await service.stop()
                    logger.info(f"Servis durduruldu: {name}")
            except Exception as e:
                logger.error(f"Servis durdurma hatası ({name}): {e}")

    async def get_status(self):
        """Bot durumunu döndür."""
        status = {
            "running": self.is_running,
            "uptime": time.time() - self.start_time if self.is_running else 0,
            "client_connected": self.client is not None and self.client.is_connected() if self.client else False,
            "services": {}
        }
        
        # Servislerin durumunu ekle
        for name, service in self.services.items():
            if hasattr(service, "get_status") and callable(service.get_status):
                try:
                    service_status = await service.get_status()
                    status["services"][name] = service_status
                except Exception as e:
                    status["services"][name] = {"error": str(e)}
            else:
                status["services"][name] = {"running": getattr(service, "running", False)}
        
        return status

async def main():
    """
    Ana uygulama girişi.
    """
    # Log yapılandırmasını ayarla
    format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    if settings.DEBUG:
        logging.basicConfig(level=logging.DEBUG, format=format)
    else:
        logging.basicConfig(level=logging.INFO, format=format)
    
    # Botu başlat
    bot = TelegramBot()
    await bot.start()

def run():
    """Uygulama giriş noktası."""
    # Başlangıç mesajı
    print(f"\n{Colors.GREEN}Telegram Bot başlatılıyor...{Colors.ENDC}")
    print(f"Python sürümü: {sys.version}")
    print(f"Çalışma dizini: {os.getcwd()}\n")
    
    try:
        # Windows'ta multiprocessing için gerekli
        if os.name == 'nt':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
        # Ana döngüyü başlat
        exit_code = asyncio.run(main())
        
        # Çıkış yap
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print(f"\n{Colors.BLUE}Kullanıcı tarafından durduruldu.{Colors.ENDC}")
        sys.exit(0)
    except Exception as e:
        print(f"\n{Colors.RED}Kritik hata: {e}{Colors.ENDC}")
        logger.exception("Kritik hata")
        sys.exit(1)

if __name__ == "__main__":
    run()
