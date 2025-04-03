"""
# ============================================================================ #
# Dosya: service_manager.py
# Yol: /Users/siyahkare/code/telegram-bot/bot/services/service_manager.py
# İşlev: Servis yaşam döngüsü ve koordinasyon yönetimi
# ============================================================================ #
"""

import asyncio
import logging
import threading
from typing import Dict, List, Any, Optional
from datetime import datetime

from bot.services.service_factory import ServiceFactory

logger = logging.getLogger(__name__)

class ServiceManager:
    """
    Servis yaşam döngüsünü ve koordinasyonunu yöneten sınıf.
    """
    
    def __init__(self, factory: ServiceFactory):
        self.factory = factory
        self.services = {}
        
    async def start_services(self, service_names: Optional[List[str]] = None) -> None:
        """
        Belirtilen servisleri başlatır. Eğer service_names None ise, tüm servisleri başlatır.
        """
        # Eğer belirli servisler istenmemişse, zaten oluşturulan tüm servisleri başlat
        if service_names is None:
            service_names = list(self.factory.services.keys())
        
        logger.info(f"Servisler başlatılıyor: {service_names}")
        
        for name in service_names:
            try:
                # Servis henüz oluşturulmamışsa oluştur
                if name not in self.services:
                    service = self.factory.create_service(name)
                    self.services[name] = service
                else:
                    service = self.services[name]
                
                # Servisin start veya run metodu varsa çağır
                if hasattr(service, 'start'):
                    await service.start()
                    logger.info(f"{name} servisi başlatıldı (start metodu)")
                elif hasattr(service, 'run'):
                    # Run metodunu ayrı bir görev olarak başlat
                    asyncio.create_task(service.run(), name=f"{name}_service_task")
                    logger.info(f"{name} servisi başlatıldı (run metodu)")
                else:
                    logger.warning(f"{name} servisi için start/run metodu bulunamadı")
            
            except Exception as e:
                logger.error(f"{name} servisi başlatılırken hata: {str(e)}", exc_info=True)
        
        logger.info("Tüm istenen servisler başlatıldı")
    
    async def stop_services(self, service_names: Optional[List[str]] = None) -> None:
        """
        Belirtilen servisleri durdurur. Eğer service_names None ise, tüm servisleri durdurur.
        """
        if service_names is None:
            service_names = list(self.services.keys())
        
        logger.info(f"Servisler durduruluyor: {service_names}")
        
        for name in service_names:
            try:
                if name in self.services:
                    service = self.services[name]
                    
                    # Servisin stop metodu varsa çağır
                    if hasattr(service, 'stop'):
                        await service.stop()
                    # Alternatif olarak running özelliğini False yap
                    elif hasattr(service, 'running'):
                        service.running = False
                    
                    logger.info(f"{name} servisi durduruldu")
            
            except Exception as e:
                logger.error(f"{name} servisi durdurulurken hata: {str(e)}")
        
        logger.info("Tüm istenen servisler durduruldu")
    
    def get_service_status(self) -> Dict[str, Any]:
        """
        Tüm servislerin durumlarını içeren bir sözlük döndürür.
        """
        status = {}
        
        for name, service in self.services.items():
            # Varsayılan durum bilgisi
            service_status = {
                "running": False,
                "last_activity": "Bilinmiyor"
            }
            
            # Servisin get_status metodu varsa kullan
            if hasattr(service, 'get_status'):
                service_status = service.get_status()
            # Yoksa mevcut özelliklerden durumu çıkar
            else:
                # Running durumu
                if hasattr(service, 'running'):
                    service_status["running"] = service.running
                elif hasattr(service, 'is_running'):
                    service_status["running"] = service.is_running
                
                # Son aktivite
                if hasattr(service, 'last_activity'):
                    if isinstance(service.last_activity, datetime):
                        service_status["last_activity"] = service.last_activity.strftime("%H:%M:%S")
                    else:
                        service_status["last_activity"] = str(service.last_activity)
            
            status[name] = service_status
            
        return status