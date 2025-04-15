"""
# ============================================================================ #
# Dosya: gpt_service.py
# Yol: /Users/siyahkare/code/telegram-bot/bot/services/gpt_service.py
# İşlev: OpenAI GPT entegrasyonu için Telegram bot servisi.
#
# © 2025 SiyahKare Yazılım - Tüm Hakları Saklıdır
# ============================================================================ #
"""

import asyncio
import logging
from bot.services.base_service import BaseService

logger = logging.getLogger(__name__)

class GptService(BaseService):
    """Basit OpenAI GPT entegrasyonu."""
    
    def __init__(self, client, config, db, stop_event=None):
        """GptService başlatıcısı."""
        super().__init__("gpt", client, config, db, stop_event)
        logger.info("GPT servisi başlatıldı")
    
    async def initialize(self):
        """Servisi başlatmadan önce hazırlar."""
        await super().initialize()
        return True
        
    async def run(self):
        """Servisin ana çalışma döngüsü."""
        logger.info("GPT servisi çalışıyor (pasif mod)")
        while self.running:
            if self.stop_event.is_set():
                break
            await asyncio.sleep(60)
    
    async def get_status(self):
        """Servisin mevcut durumunu döndürür."""
        status = await super().get_status()
        status.update({
            "service_type": "gpt",
            "name": "GPT Servisi",
            "active": False,
            "api_available": False,
            "status": "API Key yok - GPT devre dışı"
        })
        return status