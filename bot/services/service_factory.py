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

# Tüm servisleri import et
from bot.services.user_service import UserService
from bot.services.group_service import GroupService
from bot.services.reply_service import ReplyService
from bot.services.dm_service import DMService
from bot.services.invite_service import InviteService
from bot.services.promo_service import PromoService
from bot.services.announcement_service import AnnouncementService
from bot.services.gpt_service import GptService
# DataMiningService sınıfını import et
from bot.services.data_mining_service import DataMiningService
# MessageService sınıfını import et
from bot.services.message_service import MessageService

logger = logging.getLogger(__name__)

class ServiceFactory:
    """
    Farklı servis nesnelerini oluşturan fabrika sınıfı.
    Bu sınıf, servis türüne göre uygun servis örneği oluşturur.
    """

    def __init__(self):
        """
        ServiceFactory sınıfının başlatıcısı.
        İhtiyaç duyulan parametreler create_service metoduna geçirilecek.
        """
        # Loglama için
        self.logger = logging.getLogger(__name__)

    def create_service(self, service_type, client, config, db, stop_event=None):
        """
        Belirtilen tipte yeni bir servis nesnesi oluşturur.
        
        Args:
            service_type: Oluşturulacak servis tipi
            client: Telegram istemcisi
            config: Yapılandırma nesnesi
            db: Veritabanı bağlantısı
            stop_event: Durdurma sinyali
            
        Returns:
            BaseService: Oluşturulan servis nesnesi
        """
        try:
            # Servis tiplerine göre service oluşturucu fonksiyonlar
            service_creators = {
                "user": lambda: UserService(client, config, db, stop_event),
                "group": lambda: GroupService(client, config, db, stop_event),
                "reply": lambda: ReplyService(client, config, db, stop_event),
                "dm": lambda: DMService(client, config, db, stop_event),
                "invite": lambda: InviteService(client, config, db, stop_event),
                "promo": lambda: PromoService(client, config, db, stop_event),
                "announcement": lambda: AnnouncementService(client, config, db, stop_event),
                "gpt": lambda: GptService(client, config, db, stop_event),
                "datamining": lambda: DataMiningService(client, config, db, stop_event),
                "message": lambda: MessageService(client, config, db, stop_event)
            }
            
            # Servis tipine uygun oluşturucu var mı?
            if service_type in service_creators:
                # Service'i oluştur ve döndür
                service = service_creators[service_type]()
                self.logger.info(f"{service_type.capitalize()} servisi başarıyla oluşturuldu")
                return service
            else:
                self.logger.warning(f"Bilinmeyen servis tipi: {service_type}")
                return None
                
        except Exception as e:
            self.logger.error(f"Servis oluşturulurken hata ({service_type}): {str(e)}")
            import traceback
            self.logger.debug(traceback.format_exc())  # Daha detaylı hata bilgisi
            return None