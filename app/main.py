#!/usr/bin/env python3
# Test amaçlı basit bir uygulama
import os
import sys
import time
import dotenv
import asyncio
import logging
import signal
from typing import List, Dict, Any, Optional

from telethon import TelegramClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.services.base import BaseService
from app.services.messaging.engagement_service import EngagementService
from app.services.messaging.dm_service import DirectMessageService
from app.services.messaging.promo_service import PromoService
from app.services.analytics.activity_service import ActivityService
from app.services.monitoring.health_monitor import HealthMonitor

dotenv.load_dotenv()

print("Bot başlatılıyor...")
print(f"Python sürümü: {sys.version}")
print(f"Çalışma dizini: {os.getcwd()}")
print("Test uygulaması çalışıyor...")

# Ortamdan temel bilgileri oku ve göster
api_id = os.getenv("API_ID", "Tanımsız")
api_hash = os.getenv("API_HASH", "Tanımsız")
session_name = os.getenv("SESSION_NAME", "Tanımsız")
phone = os.getenv("PHONE", "Tanımsız")
db_name = os.getenv("DB_NAME", "Tanımsız")

print("\n--- Ortam Bilgileri ---")
print(f"API ID: {api_id}")
print(f"API HASH: {api_hash[:5]}...{api_hash[-5:] if len(api_hash) > 10 else ''}")
print(f"Session adı: {session_name}")
print(f"Telefon numarası: {phone}")
print(f"Veritabanı adı: {db_name}")
print("----------------------\n")

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
    """
    Telegram botu ana sınıfı.
    - Tüm servisleri başlatır ve yönetir
    - Telegram bağlantısını sağlar
    - Graceful shutdown sürecini yönetir
    """

    def __init__(self):
        self.client: Optional[TelegramClient] = None
        self.db: Optional[AsyncSession] = None
        self.services: Dict[str, BaseService] = {}
        self.tasks: List[asyncio.Task] = []
        self.running = False
        self.shutdown_event = asyncio.Event()

    async def initialize(self):
        """Bot sistemini başlat."""
        logger.info("Initializing Telegram Bot")
        
        # Telethon client oluştur
        self.client = TelegramClient(
            settings.SESSION_NAME,
            settings.API_ID,
            settings.API_HASH.get_secret_value(),
            proxy=None,
            connection_retries=settings.TG_CONNECTION_RETRIES
        )
        
        # Veritabanı bağlantısı
        self.db = await get_db().__anext__()
        
        # Servisleri başlat
        await self._initialize_services()
        
        # Sinyalleri kaydet (Ctrl+C ve sistem sinyalleri)
        self._register_signal_handlers()
        
        logger.info("Telegram Bot initialized successfully")

    async def _initialize_services(self):
        """Tüm servisleri başlat."""
        # Activity Service
        activity_service = ActivityService(db=self.db)
        self.services["activity"] = activity_service
        
        # Health Monitor
        health_monitor = HealthMonitor(db=self.db)
        self.services["health"] = health_monitor
        
        # Engagement Service
        engagement_service = EngagementService(client=self.client, db=self.db)
        self.services["engagement"] = engagement_service
        
        # DM Service
        dm_service = DirectMessageService(client=self.client, db=self.db)
        self.services["dm"] = dm_service
        
        # Promo Service
        promo_service = PromoService(client=self.client, db=self.db)
        self.services["promo"] = promo_service
        
        # Tüm servisleri başlat
        for name, service in self.services.items():
            try:
                logger.info(f"Initializing service: {name}")
                await service.initialize()
            except Exception as e:
                logger.error(f"Error initializing service {name}: {str(e)}", exc_info=True)

    async def start(self):
        """Telegram oturumunu ve aktif servis döngülerini başlat."""
        try:
            logger.info("Starting Telegram Bot")
            
            # Telegram client'ı başlat
            await self.client.start(phone=settings.PHONE if settings.USER_MODE else None, bot_token=None if settings.USER_MODE else settings.BOT_TOKEN.get_secret_value())
            logger.info(f"Telegram client started successfully in {'USER' if settings.USER_MODE else 'BOT'} mode")
            
            # Servislerin çalışma döngülerini başlat
            self.tasks = []
            
            # Engagement Service döngüsü
            engagement_task = asyncio.create_task(
                self.services["engagement"].start_engagement_loop(),
                name="engagement_loop"
            )
            self.tasks.append(engagement_task)
            
            # DM Service mesaj dinleme ve tanıtım döngüsü
            dm_promo_task = asyncio.create_task(
                self.services["dm"].start_promo_loop(),
                name="dm_promo_loop"
            )
            self.tasks.append(dm_promo_task)
            
            # Promo Service döngüsü
            promo_task = asyncio.create_task(
                self.services["promo"].start_promo_loop(),
                name="promo_loop"
            )
            self.tasks.append(promo_task)
            
            # Health Monitor döngüsü
            health_task = asyncio.create_task(
                self.services["health"].start_monitoring(),
                name="health_monitor"
            )
            self.tasks.append(health_task)
            
            self.running = True
            logger.info("All services started successfully")
            
            # Kapatma sinyali bekleyelim
            await self.shutdown_event.wait()
            
        except Exception as e:
            logger.error(f"Error starting bot: {str(e)}", exc_info=True)
            await self.cleanup()

    def _register_signal_handlers(self):
        """Sistem sinyallerini kaydet."""
        # SIGINT (Ctrl+C) ve SIGTERM için handler
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, self._handle_signal)
    
    def _handle_signal(self, sig, frame):
        """Sinyal geldiğinde düzgün kapatma işlemini başlat."""
        logger.info(f"Received signal {sig}, initiating graceful shutdown...")
        if not self.shutdown_event.is_set():
            asyncio.create_task(self.cleanup())
            self.shutdown_event.set()

    async def cleanup(self):
        """Tüm servisleri ve bağlantıları düzgün bir şekilde kapat."""
        if not self.running:
            return
        
        self.running = False
        logger.info("Shutting down Telegram Bot...")
        
        # Çalışan görevleri iptal et
        for task in self.tasks:
            try:
                task.cancel()
                await asyncio.sleep(1)  # Görevlerin iptal edilmesi için kısa bir süre bekle
            except Exception as e:
                logger.error(f"Error cancelling task {task.get_name()}: {str(e)}")
        
        # Servisleri kapat
        for name, service in self.services.items():
            try:
                logger.info(f"Cleaning up service: {name}")
                await service.cleanup()
            except Exception as e:
                logger.error(f"Error cleaning up service {name}: {str(e)}")
        
        # Telegram client'ı kapat
        if self.client and self.client.is_connected():
            await self.client.disconnect()
            logger.info("Telegram client disconnected")
        
        # Veritabanı bağlantısını kapat
        if self.db:
            await self.db.close()
            logger.info("Database connection closed")
        
        logger.info("Telegram Bot shutdown complete")

async def main():
    """Ana çalışma fonksiyonu."""
    bot = TelegramBot()
    await bot.initialize()
    await bot.start()

if __name__ == "__main__":
    # Windows'ta multiprocessing için gerekli
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    # Ana döngüyü başlat
    asyncio.run(main())
