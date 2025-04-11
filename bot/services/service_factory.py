"""
# ============================================================================ #
# Dosya: service_factory.py
# Yol: /Users/siyahkare/code/telegram-bot/bot/services/service_factory.py
# İşlev: Servis nesnelerini oluşturan fabrika sınıfı.
#
# © 2025 SiyahKare Yazılım - Tüm Hakları Saklıdır
# ============================================================================ #
"""

import asyncio
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

class ServiceFactory:
    """
    Servis nesnelerini oluşturan fabrika sınıfı.
    
    Bu sınıf, çeşitli servis tiplerini oluşturmaktan sorumludur. Tüm servislerin
    aynı yapılandırma ve bağımlılıkları paylaşmasını sağlar.
    
    Attributes:
        client: Telethon istemcisi
        config: Uygulama yapılandırması
        db: Veritabanı bağlantısı
        stop_event: Durdurma sinyali için asyncio.Event nesnesi
    """
    
    def __init__(self, client: Any, config: Any, db: Any, stop_event: asyncio.Event):
        """
        ServiceFactory sınıfının başlatıcısı.
        
        Args:
            client: Telethon istemcisi
            config: Uygulama yapılandırması
            db: Veritabanı bağlantısı
            stop_event: Durdurma sinyali için asyncio.Event nesnesi
        """
        self.client = client
        self.config = config
        self.db = db
        self.stop_event = stop_event
        
    def create_service(self, service_type: str) -> Optional[Any]:
        """
        Belirtilen tipte servis oluşturur.
        
        Args:
            service_type: Servis tipi ('user', 'group', 'dm', vb.)
            
        Returns:
            Optional[Any]: Oluşturulan servis nesnesi veya None
        """
        try:
            if service_type == "user":
                from bot.services.user_service import UserService
                return UserService(self.client, self.config, self.db, self.stop_event)
                
            elif service_type == "group":
                from bot.services.group_service import GroupService
                return GroupService(self.client, self.config, self.db, self.stop_event)
                
            elif service_type == "reply":
                from bot.services.reply_service import ReplyService
                return ReplyService(self.client, self.config, self.db, self.stop_event)
                
            elif service_type == "dm":
                from bot.services.dm_service import DMService
                return DMService(self.client, self.config, self.db, self.stop_event)
                
            elif service_type == "invite":
                from bot.services.invite_service import InviteService
                return InviteService(self.client, self.config, self.db, self.stop_event)
                
            else:
                logger.warning(f"Bilinmeyen servis tipi: {service_type}")
                return None
                
        except ImportError as e:
            logger.error(f"Servis modülü içe aktarılamadı ({service_type}): {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Servis oluşturulamadı ({service_type}): {str(e)}")
            return None