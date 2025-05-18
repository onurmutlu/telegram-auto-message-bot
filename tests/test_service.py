#!/usr/bin/env python3
"""Minimal servis testi"""

import asyncio
import logging
import os
import sys

# Logging yapılandırması
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("service_test.log")
    ]
)

logger = logging.getLogger(__name__)

class MinimalService:
    """Test için minimal servis sınıfı"""
    
    def __init__(self, name):
        self.name = name
        self.initialized = False
        logger.info(f"{self.name} servisi oluşturuluyor")
    
    async def initialize(self):
        """Servisi başlat"""
        self.initialized = True
        logger.info(f"{self.name} servisi başlatıldı")
        return True
    
    async def cleanup(self):
        """Kaynakları temizle"""
        self.initialized = False
        logger.info(f"{self.name} servisi temizlendi")

class ServiceManager:
    """Test için minimal servis yöneticisi"""
    
    def __init__(self):
        self.services = {}
        logger.info("Servis yöneticisi oluşturuluyor")
    
    async def register_service(self, name, service):
        """Servis kaydet"""
        self.services[name] = service
        logger.info(f"{name} servisi kaydedildi")
    
    async def initialize_all(self):
        """Tüm servisleri başlat"""
        for name, service in self.services.items():
            await service.initialize()
        logger.info("Tüm servisler başlatıldı")
    
    async def cleanup_all(self):
        """Tüm servisleri temizle"""
        for name, service in self.services.items():
            await service.cleanup()
        logger.info("Tüm servisler temizlendi")

async def main():
    """Ana test fonksiyonu"""
    try:
        logger.info("Test başlatılıyor...")
        
        # Servis yöneticisi oluştur
        manager = ServiceManager()
        
        # Test servisleri oluştur
        service1 = MinimalService("test_service_1")
        service2 = MinimalService("test_service_2")
        service3 = MinimalService("test_service_3")
        
        # Servisleri kaydet
        await manager.register_service("test1", service1)
        await manager.register_service("test2", service2)
        await manager.register_service("test3", service3)
        
        # Tüm servisleri başlat
        await manager.initialize_all()
        
        # Test işlemleri
        logger.info(f"Aktif servis sayısı: {len(manager.services)}")
        logger.info("Test işlemleri yapılıyor...")
        await asyncio.sleep(1)  # Simüle edilmiş işlem
        
        # Servisleri temizle
        await manager.cleanup_all()
        
        logger.info("Test başarıyla tamamlandı")
        return True
        
    except Exception as e:
        logger.error(f"Test sırasında hata oluştu: {str(e)}", exc_info=True)
        return False

if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1) 