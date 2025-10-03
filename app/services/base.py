"""
Geriye dönük uyumluluk için base.py.
Bu dosya sadece BaseService'i dışa aktarmak için kullanılır.
"""

from app.services.base_service import BaseService, ConfigAdapter

__all__ = ["BaseService", "ConfigAdapter"]

#!/usr/bin/env python3
# Telegram Bot - Base Service
import asyncio
import logging
from telethon import TelegramClient

logger = logging.getLogger(__name__)

class BaseService:
    """
    Tüm servisler için temel sınıf.
    
    Bu sınıf tüm servislerde olması gereken temel metotları içerir:
    - start: Servisi başlatır
    - stop: Servisi durdurur
    - run: Ana servis döngüsü
    """
    
    def __init__(self, client: TelegramClient, db=None):
        """Temel servisi başlat."""
        self.client = client
        self.db = db
        self.running = False
        self.task = None
        self.service_name = "base_service"
    
    async def start(self):
        """Servisi başlat."""
        if self.running:
            logger.warning(f"{self.service_name} servisi zaten çalışıyor")
            return
        
        self.running = True
        self.task = asyncio.create_task(self.run())
        logger.info(f"{self.service_name} servisi başlatıldı")
    
    async def stop(self):
        """Servisi durdur."""
        if not self.running:
            logger.warning(f"{self.service_name} servisi zaten durdurulmuş")
            return
        
        self.running = False
        
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
            
        logger.info(f"{self.service_name} servisi durduruldu")
    
    async def run(self):
        """Ana servis döngüsü. Alt sınıflar tarafından uygulanmalıdır."""
        logger.warning(f"{self.service_name} servisi için run metodu uygulanmamış")
    
    async def get_status(self):
        """Servisin durumunu döndürür."""
        return {"running": self.running} 