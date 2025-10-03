#!/usr/bin/env python3
import logging
from typing import Dict, Any, List, Optional, Type, Union

from sqlalchemy.ext.asyncio import AsyncSession
from telethon import TelegramClient

from app.core.config import settings
from app.services.base_service import BaseService
from app.services.analytics.activity_service import ActivityService
from app.services.analytics.user_service import UserService
from app.services.monitoring.health_service import HealthService

# Geçici olarak yoruma alınmış servisler
# from app.services.messaging.engagement_service import EngagementService
from app.services.messaging.dm_service import DirectMessageService
from app.services.messaging.promo_service import PromoService

logger = logging.getLogger(__name__)

class ServiceFactory:
    """
    Servis fabrikası sınıfı.
    
    Bu sınıf, bot servislerini kontrol ederek ilgili servisleri oluşturur,
    başlatır ve durdurur. .env dosyasındaki ayarlara göre otomatik olarak
    hangi servislerin etkinleştirileceğini belirler.
    """
    
    def __init__(self, client: TelegramClient = None, db: AsyncSession = None, service_manager: Any = None):
        """ServiceFactory başlatıcısı."""
        self.client = client
        self.db = db
        self.service_manager = service_manager
        self.services: Dict[str, BaseService] = {}
        self.disabled_services: List[str] = []
        self.initialized = False
        
        # .env dosyasından servis ayarlarını oku
        self._load_service_settings()
    
    def _load_service_settings(self):
        """Hangi servislerin etkinleştirileceğini ayar dosyasından belirle."""
        # Health service her zaman etkindir
        self.disabled_services = []
        
        # EngagementService ayarı
        if not settings.ENV.startswith(("development", "staging")) and hasattr(settings, "ENGAGEMENT_ENABLED") and not settings.ENGAGEMENT_ENABLED:
            self.disabled_services.append("engagement")
        
        # DirectMessageService ayarı
        if hasattr(settings, "DM_SERVICE_ENABLED") and not settings.DM_SERVICE_ENABLED:
            self.disabled_services.append("dm")
        
        # PromoService ayarı
        if hasattr(settings, "PROMO_SERVICE_ENABLED") and not settings.PROMO_SERVICE_ENABLED:
            self.disabled_services.append("promo")
        
        logger.info(f"Devre dışı servisler: {', '.join(self.disabled_services) if self.disabled_services else 'Hepsi etkin'}")
    
    async def initialize(self):
        """Tüm servisleri başlat."""
        logger.info("Initializing services")
        
        # Temel analitik servisleri
        self.services["activity"] = ActivityService(db=self.db)
        self.services["user"] = UserService(db=self.db)
        
        # Sağlık izleme servisi
        self.services["health"] = HealthService(
            client=self.client,
            service_manager=self.service_manager,
            db=self.db
        )
        
        # Diğer servisleri şartlara bağlı olarak yükle
        # Bu servisleri devre dışı bıraktık, çünkü bazı sorunlar var
        """
        # Engagement Service
        if "engagement" not in self.disabled_services:
            try:
                self.services["engagement"] = EngagementService(
                    client=self.client,
                    db=self.db
                )
            except Exception as e:
                logger.error(f"Error initializing EngagementService: {str(e)}")
        
        # DM Service
        if "dm" not in self.disabled_services:
            try:
                self.services["dm"] = DirectMessageService(
                    client=self.client,
                    db=self.db
                )
            except Exception as e:
                logger.error(f"Error initializing DirectMessageService: {str(e)}")
        
        # Promo Service  
        if "promo" not in self.disabled_services:
            try:
                self.services["promo"] = PromoService(
                    client=self.client,
                    db=self.db
                )
            except Exception as e:
                logger.error(f"Error initializing PromoService: {str(e)}")
        """
        
        # Servisleri başlat
        for name, service in self.services.items():
            try:
                logger.info(f"Initializing service: {name}")
                await service.initialize()
            except Exception as e:
                logger.error(f"Error initializing service {name}: {str(e)}", exc_info=True)
        
        self.initialized = True
        logger.info(f"Services initialized: {', '.join(self.services.keys())}")
    
    async def start_services(self):
        """Tüm servisleri çalıştır."""
        logger.info("Starting services")
        
        for name, service in self.services.items():
            try:
                logger.info(f"Starting service: {name}")
                if hasattr(service, "start") and callable(service.start):
                    await service.start()
            except Exception as e:
                logger.error(f"Error starting service {name}: {str(e)}", exc_info=True)
    
    async def stop_services(self):
        """Tüm servisleri durdur."""
        logger.info("Stopping services")
        
        for name, service in self.services.items():
            try:
                logger.info(f"Stopping service: {name}")
                await service.cleanup()
            except Exception as e:
                logger.error(f"Error stopping service {name}: {str(e)}", exc_info=True)
    
    def get_service(self, service_name: str) -> Optional[BaseService]:
        """İsme göre servis döndür."""
        return self.services.get(service_name)
    
    async def get_service_status(self, service_name: Optional[str] = None) -> Dict[str, Any]:
        """Servis(ler)in durumunu al."""
        if service_name:
            service = self.get_service(service_name)
            if not service:
                return {"error": f"Service {service_name} not found"}
            
            if hasattr(service, "get_status") and callable(service.get_status):
                try:
                    return await service.get_status()
                except Exception as e:
                    return {"error": str(e)}
            else:
                return {"name": service_name, "running": getattr(service, "running", False)}
        else:
            # Tüm servislerin durumunu al
            status = {}
            for name, service in self.services.items():
                try:
                    if hasattr(service, "get_status") and callable(service.get_status):
                        status[name] = await service.get_status()
                    else:
                        status[name] = {"running": getattr(service, "running", False)}
                except Exception as e:
                    status[name] = {"error": str(e)}
            
            return status
    
    def register_service(self, service_name: str, service_instance: BaseService) -> bool:
        """Yeni bir servis ekle."""
        if service_name in self.services:
            logger.warning(f"Service {service_name} already exists, overwriting")
        
        self.services[service_name] = service_instance
        logger.info(f"Service {service_name} registered")
        return True
    
    def unregister_service(self, service_name: str) -> bool:
        """Bir servisi kaldır."""
        if service_name not in self.services:
            logger.warning(f"Service {service_name} not found")
            return False
        
        del self.services[service_name]
        logger.info(f"Service {service_name} unregistered")
        return True
    
    async def cleanup(self):
        """Tüm servisleri temizle."""
        await self.stop_services()
        self.services = {}
        logger.info("ServiceFactory cleanup completed")
