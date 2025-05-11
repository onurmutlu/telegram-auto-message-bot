"""
# ============================================================================ #
# Dosya: service_factory.py
# Yol: /Users/siyahkare/code/telegram-bot/app/services/service_factory.py
# İşlev: Servis nesnelerini oluşturan fabrika sınıfı.
#
# © 2025 SiyahKare Yazılım - Tüm Hakları Saklıdır
# ============================================================================ #
"""

import logging
from typing import Dict, Any, Optional, List
import asyncio

# BaseService'i import et
from app.services.base_service import BaseService

# Tüm servisleri import et
from app.services.user_service import UserService
from app.services.group_service import GroupService
from app.services.messaging.reply_service import ReplyService
from app.services.messaging.dm_service import DirectMessageService
from app.services.messaging.invite_service import InviteService
from app.services.messaging.promo_service import PromoService
from app.services.messaging.announcement_service import AnnouncementService
from app.services.gpt_service import GPTService
from app.services.analytics.datamining_service import DataMiningService
from app.services.message_service import MessageService
from app.services.analytics.analytics_service import AnalyticsService
from app.services.analytics.error_service import ErrorService

# v3.9.0 özellikleri
from app.services.demo_service import DemoService
from app.services.monitoring.health_monitor import HealthMonitor
from app.services.error_handling import ErrorManager

logger = logging.getLogger(__name__)

class ServiceFactory:
    """
    Farklı servis nesnelerini oluşturan fabrika sınıfı.
    Bu sınıf, servis türüne göre uygun servis örneği oluşturur.
    """

    def __init__(self, client=None, config=None, db=None, stop_event=None, **kwargs):
        """
        ServiceFactory sınıfının başlatıcısı.
        
        Args:
            client: Telegram istemcisi
            config: Yapılandırma nesnesi
            db: Veritabanı bağlantısı
            stop_event: Durdurma sinyali
            **kwargs: Ek parametreler
        """
        self.client = client
        self.config = config
        self.db = db
        self.stop_event = stop_event or asyncio.Event()
        self.kwargs = kwargs
        self.error_manager = ErrorManager()
        
    def create_service(self, service_type: str, **override_kwargs) -> BaseService:
        """
        Belirtilen türde bir servis oluşturur.
        
        Args:
            service_type: Oluşturulacak servis türü
            **override_kwargs: Servis oluşturulurken kullanılacak özel parametreler
            
        Returns:
            BaseService: Oluşturulan servis nesnesi
            
        Raises:
            ValueError: Geçersiz servis türü
        """
        try:
            # Import edilen modülleri buraya ekle
            from app.services.user_service import UserService
            from app.services.group_service import GroupService
            from app.services.message_service import MessageService
            from app.services.messaging.dm_service import DirectMessageService
            from app.services.messaging.reply_service import ReplyService
            from app.services.messaging.announcement_service import AnnouncementService
            from app.services.messaging.invite_service import InviteService
            from app.services.messaging.promo_service import PromoService
            
            # Burada kendi servislerinizi başlatabilirsiniz
            service_map = {
                # Temel servisler
                "user": UserService,
                "group": GroupService,
                "message": MessageService,
                
                # Mesajlaşma servisleri
                "direct_message": DirectMessageService,  # Eski adı: dm
                "dm": DirectMessageService,  # Geriye uyumluluk için
                "reply_service": ReplyService,  # Eski adı: reply
                "reply": ReplyService,  # Geriye uyumluluk için
                "invitation": InviteService,
                "invite_service": InviteService,  # Eski adı: invite
                "invite": InviteService,  # Geriye uyumluluk için
                "announcement_service": AnnouncementService,  # Eski adı: announcement
                "announcement": AnnouncementService,  # Geriye uyumluluk için
                "promo_service": PromoService,  # Eski adı: promo
                "promo": PromoService,  # Geriye uyumluluk için
                
                # v3.9.0 servisleri
                "demo": DemoService,
                "health_monitor": HealthMonitor
            }
            
            # Servis sınıfını alın
            service_class = service_map.get(service_type)
            
            if not service_class:
                raise ValueError(f"Geçersiz servis türü: {service_type}")
                
            # Temel parametre sözlüğünü oluştur
            kwargs = {
                "client": self.client,
                "config": self.config,
                "db": self.db,
                "stop_event": self.stop_event,
                **self.kwargs  # Fabrika oluşturulurken verilen diğer parametreler
            }
            
            # Override parametrelerini ekle
            kwargs.update(override_kwargs)
            
            # Servis nesnesini oluşturun
            service = service_class(**kwargs)
            
            logger.info(f"'{service_type}' türünde servis oluşturuldu: {service.service_name}")
            return service
            
        except Exception as e:
            logger.error(f"Servis oluşturulurken hata: {str(e)}")
            self.error_manager.log_error(e, service_name=service_type)
            raise

    def create_services(self, service_types: List[str], **shared_kwargs) -> Dict[str, BaseService]:
        """
        Birden fazla servis oluşturur.
        
        Args:
            service_types: Oluşturulacak servis türleri listesi
            **shared_kwargs: Tüm servislere aktarılacak ortak parametreler
            
        Returns:
            Dict[str, BaseService]: Servis adı-nesne eşlemesi
        """
        services = {}
        
        for service_type in service_types:
            try:
                service = self.create_service(service_type, **shared_kwargs)
                services[service.service_name] = service
            except Exception as e:
                logger.error(f"'{service_type}' servisi oluşturulurken hata: {str(e)}")
                self.error_manager.log_error(e, service_name=service_type)
        
        return services