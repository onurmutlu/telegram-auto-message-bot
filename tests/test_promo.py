#!/usr/bin/env python3
import asyncio
import logging
from telethon import TelegramClient

from app.core.config import settings
from app.db.session import get_session
from app.services.base_service import BaseService

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

class MinimalPromoService(BaseService):
    """Test amaçlı minimal PromoService"""
    
    service_name = "minimal_promo"
    
    def __init__(self, db=None):
        super().__init__(name="minimal_promo")
        self.db = db
        self.initialized = False
    
    async def initialize(self):
        """Servisi başlat"""
        self.db = self.db or next(get_session())
        self.initialized = True
        logger.info("Minimal PromoService başlatıldı")
        return True
    
    async def get_status(self):
        """Durum bilgisi"""
        return {
            "name": self.service_name,
            "initialized": self.initialized
        }
    
    async def _start(self):
        return await self.initialize()
    
    async def _stop(self):
        self.initialized = False
        return True
    
    async def _update(self):
        logger.info("Güncelleme yapılıyor")
        return True

async def main():
    logger.info("Test başlatılıyor...")
    
    # PromoService'i oluştur ve başlat
    promo = MinimalPromoService()
    await promo.start()
    
    # Durum kontrol et
    status = await promo.get_status()
    logger.info(f"PromoService durumu: {status}")
    
    # Servis update çağrısı
    await promo.update()
    
    # Servisi durdur
    await promo.stop()
    
    logger.info("Test tamamlandı.")

if __name__ == "__main__":
    asyncio.run(main()) 