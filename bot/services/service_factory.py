"""
# ============================================================================ #
# Dosya: service_factory.py
# Yol: /Users/siyahkare/code/telegram-bot/bot/services/service_factory.py
# İşlev: Servis nesnelerini oluşturan fabrika sınıfı.
#
# © 2025 SiyahKare Yazılım - Tüm Hakları Saklıdır
# ============================================================================ #
"""

import logging
from typing import Dict, Any, Optional
import asyncio

# BaseService'i import et
from bot.services.base_service import BaseService

# Tüm servisleri import et
from bot.services.user_service import UserService
from bot.services.group_service import GroupService
from bot.services.reply_service import ReplyService
from bot.services.dm_service import DMService
from bot.services.invite_service import InviteService
from bot.services.promo_service import PromoService
from bot.services.announcement_service import AnnouncementService
from bot.services.gpt_service import GptService
# DataMiningService sınıfını import et - düzeltildi
from bot.services.datamining_service import DataMiningService
# MessageService sınıfını import et
from bot.services.message_service import MessageService
# Yeni servisler
from bot.services.analytics_service import AnalyticsService
from bot.services.error_service import ErrorService

logger = logging.getLogger(__name__)

class ServiceFactory:
    """
    Farklı servis nesnelerini oluşturan fabrika sınıfı.
    Bu sınıf, servis türüne göre uygun servis örneği oluşturur.
    """

    def __init__(self, client, config, db, stop_event=None):
        """
        ServiceFactory sınıfının başlatıcısı.
        
        Args:
            client: Telegram istemcisi
            config: Yapılandırma nesnesi
            db: Veritabanı bağlantısı
            stop_event: Durdurma sinyali
        """
        self.client = client
        self.config = config
        self.db = db
        self.stop_event = stop_event or asyncio.Event()
        
    def create_service(self, service_type: str, client=None, config=None, db=None, stop_event=None) -> BaseService:
        """
        Belirtilen türde bir servis oluşturur.
        
        Args:
            service_type: Oluşturulacak servis türü
            client: Telegram istemcisi (opsiyonel, verilmezse sınıfın kendi istemcisi kullanılır)
            config: Yapılandırma nesnesi (opsiyonel, verilmezse sınıfın kendi yapılandırması kullanılır)
            db: Veritabanı bağlantısı (opsiyonel, verilmezse sınıfın kendi veritabanı bağlantısı kullanılır)
            stop_event: Durdurma sinyali (opsiyonel, verilmezse sınıfın kendi sinyali kullanılır)
            
        Returns:
            BaseService: Oluşturulan servis nesnesi
            
        Raises:
            ValueError: Geçersiz servis türü
        """
        try:
            # Varsayılan değerleri ayarla
            client = client or self.client
            config = config or self.config
            db = db or self.db
            stop_event = stop_event or self.stop_event
            
            # Servis sınıfını al
            service_class = {
                "user": UserService,
                "group": GroupService,
                "message": MessageService,
                "reply": ReplyService,
                "invite": InviteService,
                "dm": DMService,
                "announcement": AnnouncementService,
                "datamining": DataMiningService,
                "gpt": GptService,
                "promo": PromoService,
                "analytics": AnalyticsService,
                "error": ErrorService
            }.get(service_type)
            
            if not service_class:
                raise ValueError(f"Geçersiz servis türü: {service_type}")
            
            # Servis örneğini oluştur
            service = service_class(
                client=client,
                config=config,
                db=db,
                stop_event=stop_event
            )
            
            return service
            
        except Exception as e:
            logger.error(f"Servis oluşturulurken hata ({service_type}): {str(e)}")
            raise