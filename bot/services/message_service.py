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
from bot.handlers.group_handler import GroupHandler

logger = logging.getLogger(__name__)

class MessageService(GroupHandler):
    """
    Telegram gruplarına mesaj gönderimi için servis sınıfı.
    Bu sınıf, GroupHandler sınıfını genişleterek mesaj gönderme işlevselliğini sağlar.
    """
    
    def __init__(self, client, config, db, stop_event=None):
        super().__init__(client, config, db, stop_event)
        logger.info("MessageService başlatıldı (GroupHandler wrapper)")
    
    async def run(self):
        """Ana servis döngüsü"""
        logger.info("MessageService çalışıyor, grup mesajları gönderilecek")
        # Ana servis döngüsünü çalıştır
        result = await self.process_group_messages()
        return result
        
    def get_status(self):
        """Servis durum bilgilerini döndürür"""
        status = super().get_status() if hasattr(super(), "get_status") else {}
        status.update({
            "service_type": "message",
            "name": "Mesaj Servisi"
        })
        return status