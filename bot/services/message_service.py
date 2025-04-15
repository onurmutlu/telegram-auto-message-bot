"""
# ============================================================================ #
# Dosya: message_service.py
# Yol: /Users/siyahkare/code/telegram-bot/bot/services/message_service.py
# İşlev: Telegram bot için mesaj gönderimi servisi.
#
# Amaç: Bu modül, gruplara otomatik mesaj gönderme işlevselliğini sağlar.
#       GroupHandler sınıfı üzerine inşa edilmiş bir wrapper servistir.
#
# Build: 2025-04-10-20:30:00
# Versiyon: v3.5.0
# ============================================================================ #
"""
import logging
import asyncio
import functools
from typing import Dict, Any
from bot.handlers.group_handler import GroupHandler
from bot.services.base_service import BaseService

logger = logging.getLogger(__name__)

class MessageService(BaseService):
    """
    Telegram gruplarına mesaj gönderimi için servis sınıfı.
    Bu sınıf, GroupHandler sınıfını kullanarak mesaj gönderme işlevselliğini sağlar.
    """
    
    def __init__(self, client, config, db, stop_event=None):
        super().__init__("message", client, config, db, stop_event)
        self.group_handler = GroupHandler(client, config, db)
        logger.info("MessageService başlatıldı")
    
    async def run(self):
        """Ana servis döngüsü"""
        logger.info("MessageService çalışıyor, grup mesajları gönderilecek")
        # Ana servis döngüsünü çalıştır
        result = await self.group_handler.process_group_messages()
        return result
        
    async def get_status(self):
        """Servis durum bilgilerini döndürür"""
        status = await super().get_status()
        status.update({
            "service_type": "message",
            "name": "Mesaj Servisi"
        })
        return status

    def set_services(self, services: Dict[str, Any]) -> None:
        """
        Diğer servislere referansları ayarlar.
        
        Args:
            services: Servis adı -> Servis nesnesi eşleşmesi
        """
        self.services = services
        logger.debug(f"{self.name} servisi diğer servislere bağlandı")

    async def _run_async_db_method(self, method, *args, **kwargs):
        """Veritabanı metodunu thread-safe biçimde çalıştırır."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, 
            functools.partial(method, *args, **kwargs)
        )