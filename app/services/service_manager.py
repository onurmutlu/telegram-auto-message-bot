#!/usr/bin/env python3
# Telegram Bot - Service Manager
from typing import Dict, List, Optional, Type
import logging
import asyncio
from telethon import TelegramClient

from app.services.base_service import BaseService

logger = logging.getLogger(__name__)

class ServiceManager:
    """
    Bot servislerini yöneten ana sınıf.
    
    Bu sınıf şunları yapar:
    - Servislerin başlatılması ve durdurulması
    - Servislerin durumunun izlenmesi
    - Servislerin birbiriyle iletişimi
    """
    
    def __init__(self, client: TelegramClient, db=None):
        """Servis yöneticisini başlat"""
        self.client = client
        self.db = db
        self.services: Dict[str, BaseService] = {}
        self.initialized = False
    
    async def initialize(self):
        """Tüm servisleri başlatır"""
        if self.initialized:
            logger.warning("Servis yöneticisi zaten başlatıldı")
            return
        
        # Servisleri dinamik olarak içe aktar ve oluştur
        try:
            # DM servisini ekle
            from app.services.messaging.dm_service import DirectMessageService
            dm_service = DirectMessageService(self.client, self.db)
            self.services["dm"] = dm_service
            logger.info("DM servisi yüklendi")
        except ImportError:
            logger.warning("DM servisi yüklenemedi")
        
        try:
            # Promo servisini ekle
            from app.services.messaging.promo_service import PromoService
            promo_service = PromoService(self.client, self.db)
            self.services["promo"] = promo_service
            logger.info("Promo servisi yüklendi")
        except ImportError:
            logger.warning("Promo servisi yüklenemedi")
        
        try:
            # Engagement servisini ekle
            from app.services.messaging.engagement_service import EngagementService
            engagement_service = EngagementService(self.client, self.db)
            self.services["engagement"] = engagement_service
            logger.info("Engagement servisi yüklendi")
        except ImportError:
            logger.warning("Engagement servisi yüklenemedi")
        
        try:
            # Activity servisini ekle
            from app.services.analytics.activity_service import ActivityService
            activity_service = ActivityService(self.client, self.db)
            self.services["activity"] = activity_service
            logger.info("Activity servisi yüklendi")
        except ImportError:
            logger.warning("Activity servisi yüklenemedi")
        
        try:
            # Health servisini ekle
            from app.services.monitoring.health_service import HealthService
            health_service = HealthService(self.client, self.db)
            self.services["health"] = health_service
            logger.info("Health servisi yüklendi")
        except ImportError:
            logger.warning("Health servisi yüklenemedi")
        
        self.initialized = True
        logger.info(f"Servis yöneticisi başlatıldı ({len(self.services)} servis bulundu)")
    
    async def start_services(self):
        """Tüm servisleri başlatır"""
        if not self.initialized:
            await self.initialize()
        
        for name, service in self.services.items():
            try:
                await service.start()
                logger.info(f"Servis başlatıldı: {name}")
            except Exception as e:
                logger.error(f"Servis başlatılırken hata ({name}): {e}")
    
    async def stop_services(self):
        """Tüm servisleri durdurur"""
        for name, service in self.services.items():
            try:
                await service.stop()
                logger.info(f"Servis durduruldu: {name}")
            except Exception as e:
                logger.error(f"Servis durdurulurken hata ({name}): {e}")
    
    def get_service(self, service_name: str) -> Optional[BaseService]:
        """Belirtilen isimde servisi döndürür"""
        return self.services.get(service_name)
    
    async def get_service_status(self, service_name: str = None) -> Dict:
        """Servislerin durumunu döndürür"""
        if service_name:
            service = self.get_service(service_name)
            if service:
                return {service_name: {"running": service.running}}
            return {service_name: {"running": False, "error": "Service not found"}}
        
        return {name: {"running": service.running} for name, service in self.services.items()}

# Helper fonksiyon - singleton ServiceManager
_service_manager = None

def get_service_manager(client=None, db=None) -> ServiceManager:
    """ServiceManager singleton'ını döndürür"""
    global _service_manager
    
    if _service_manager is None and client is not None:
        _service_manager = ServiceManager(client, db)
    
    return _service_manager