#!/usr/bin/env python3
import asyncio
import logging
import os
import sys

# Proje kök dizinini Python yoluna ekle
project_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_dir)

# BaseService'i doğrudan import et
from app.services.base_service import BaseService

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

class MinimalService(BaseService):
    """Test amaçlı minimal servis"""
    
    service_name = "minimal_service"
    
    def __init__(self):
        super().__init__(name="minimal_service")
        self.initialized = False
    
    async def initialize(self):
        """Servisi başlat"""
        self.initialized = True
        logger.info("Minimal servis başlatıldı")
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
    
    # Servisi oluştur ve başlat
    service = MinimalService()
    await service.start()
    
    # Durum kontrol et
    status = await service.get_status()
    logger.info(f"Servis durumu: {status}")
    
    # Servis update çağrısı
    await service.update()
    
    # Servisi durdur
    await service.stop()
    
    logger.info("Test tamamlandı.")

if __name__ == "__main__":
    asyncio.run(main()) 