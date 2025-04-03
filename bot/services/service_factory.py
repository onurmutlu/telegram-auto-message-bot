"""
# ============================================================================ #
# Dosya: service_factory.py
# Yol: /Users/siyahkare/code/telegram-bot/bot/services/service_factory.py
# İşlev: Servis nesnelerinin merkezi oluşturma fabrikası
# ============================================================================ #
"""

import logging
import asyncio
from typing import Dict, Any, Optional

# Servis sınıflarını içe aktar
from bot.services.dm_service import DirectMessageService
from bot.services.group_service import GroupService
from bot.services.reply_service import ReplyService
from bot.services.user_service import UserService

logger = logging.getLogger(__name__)

class ServiceFactory:
    """Servis nesneleri üretir"""
    
    def __init__(self, client, config, db, shutdown_event=None):
        """ServiceFactory sınıfını başlatır"""
        self.client = client
        self.config = config
        self.db = db
        self.stop_event = shutdown_event
        self.services = {}  # Önbelleğe alınmış servisler
        
    def create_service(self, service_type: str) -> Any:
        """
        Belirtilen türde bir servis oluşturur.
        
        Args:
            service_type: Servis türü ("group", "dm", "reply", "user", vb.)
        
        Returns:
            İstenilen türde servis nesnesi
        """
        # Önbelleğe bakarak daha önce oluşturulmuş servisi varsa döndür
        if service_type in self.services:
            logger.debug(f"{service_type} servisi önbellekten alındı")
            return self.services[service_type]
            
        logger.info(f"{service_type} servisi oluşturuluyor...")
        
        if service_type == "group":
            service = GroupService(
                self.client, 
                self.db, 
                self.config,
                self.stop_event
            )
        elif service_type == "dm":
            service = DirectMessageService(
                self.client, 
                self.config, 
                self.db, 
                self.stop_event
            )
        elif service_type == "reply":
            service = ReplyService(
                self.client, 
                self.config, 
                self.db, 
                self.stop_event
            )
        elif service_type == "user":
            service = UserService(
                self.client,
                self.db,
                self.config
            )
        else:
            raise ValueError(f"Bilinmeyen servis türü: {service_type}")
            
        # Servisi önbelleğe al
        self.services[service_type] = service
        logger.info(f"{service_type} servisi oluşturuldu")
        return service
        
    def get_all_services(self) -> Dict[str, Any]:
        """
        Tüm oluşturulmuş servisleri döndürür.
        
        Returns:
            Dict[str, Any]: Servis adı ve nesne eşleşmelerini içeren sözlük
        """
        return self.services
        
    def stop_all_services(self) -> None:
        """Tüm servisleri durdurur."""
        logger.info("Tüm servisler durduruluyor...")
        self.stop_event.set()
        for name, service in self.services.items():
            if hasattr(service, "running"):
                service.running = False
            logger.info(f"{name} servisi durduruldu")