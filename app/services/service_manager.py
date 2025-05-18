"""
# ============================================================================ #
# Dosya: service_manager.py
# Yol: /Users/siyahkare/code/telegram-bot/app/services/service_manager.py
# İşlev: Servis yönetimi ve yaşam döngüsü kontrolü.
#
# Versiyon: v2.0.0
# ============================================================================ #
"""

import logging
import asyncio
from typing import Dict, List, Any, Optional, Type, Union
import traceback

from app.services.base_service import BaseService

logger = logging.getLogger(__name__)

class ServiceManager:
    """
    Telegram bot servislerini yöneten sınıf.
    
    Bu sınıf, farklı servislerin başlatılması, durdurulması ve durumlarının
    takip edilmesi için merkezi bir nokta sağlar.
    """
    
    def __init__(self, client=None, db=None, config=None):
        """
        ServiceManager sınıfı başlatıcısı.
        
        Args:
            client: Telegram client nesnesi
            db: Veritabanı bağlantısı
            config: Yapılandırma nesnesi
        """
        self.services = {}
        self.client = client
        self.db = db
        self.config = config
        self.stop_event = asyncio.Event()
        self.logger = logger
        
    async def register_service(self, service_name: str, service: BaseService) -> None:
        """
        Yeni bir servisi kaydeder.
        
        Args:
            service_name: Servis adı
            service: Servis nesnesi
        """
        self.services[service_name] = service
        logger.info(f"Servis kaydedildi: {service_name}")
        
    async def get_service(self, service_name: str) -> Optional[BaseService]:
        """
        Belirtilen servisi döndürür.
        
        Args:
            service_name: Servisin adı
            
        Returns:
            BaseService: Servis nesnesi ya da None
        """
        return self.services.get(service_name)
        
    async def start_service(self, service_name: str) -> bool:
        """
        Belirtilen servisi başlatır.
        
        Args:
            service_name: Başlatılacak servisin adı
            
        Returns:
            bool: İşlem başarılı ise True
        """
        service = self.services.get(service_name)
        if not service:
            logger.error(f"Servis bulunamadı: {service_name}")
            return False
            
        try:
            if hasattr(service, 'start') and callable(service.start):
                success = await service.start()
                if success:
                    logger.info(f"Servis başlatıldı: {service_name}")
                    return True
                else:
                    logger.error(f"Servis başlatılamadı: {service_name}")
                    return False
            else:
                logger.error(f"Servis başlatma metodu bulunamadı: {service_name}")
                return False
        except Exception as e:
            logger.exception(f"Servis başlatma hatası: {service_name} - {str(e)}")
            return False
            
    async def stop_service(self, service_name: str) -> bool:
        """
        Belirtilen servisi durdurur.
        
        Args:
            service_name: Durdurulacak servisin adı
            
        Returns:
            bool: İşlem başarılı ise True
        """
        service = self.services.get(service_name)
        if not service:
            logger.error(f"Servis bulunamadı: {service_name}")
            return False
            
        try:
            if hasattr(service, 'stop') and callable(service.stop):
                success = await service.stop()
                if success:
                    logger.info(f"Servis durduruldu: {service_name}")
                    return True
                else:
                    logger.error(f"Servis durdurulamadı: {service_name}")
                    return False
            else:
                logger.error(f"Servis durdurma metodu bulunamadı: {service_name}")
                return False
        except Exception as e:
            logger.exception(f"Servis durdurma hatası: {service_name} - {str(e)}")
            return False
            
    async def restart_service(self, service_name: str) -> bool:
        """
        Belirtilen servisi yeniden başlatır.
        
        Args:
            service_name: Yeniden başlatılacak servisin adı
            
        Returns:
            bool: İşlem başarılı ise True
        """
        # Önce servisi durdur
        stop_result = await self.stop_service(service_name)
        if not stop_result:
            logger.warning(f"Servis durdurulurken hata oluştu. Yine de yeniden başlatılmaya çalışılacak: {service_name}")
            
        # Ardından servisi başlat
        return await self.start_service(service_name)
        
    async def start_all_services(self) -> Dict[str, bool]:
        """
        Tüm servisleri başlatır.
        
        Returns:
            Dict[str, bool]: Her bir servisin başlatma durumu
        """
        results = {}
        
        for service_name in self.services:
            results[service_name] = await self.start_service(service_name)
            
        log_str = ", ".join([f"{name}{'✓' if status else '✗'}" for name, status in results.items()])
        logger.info(f"Tüm servisler başlatıldı: {log_str}")
        
        return results
        
    async def stop_all_services(self) -> Dict[str, bool]:
        """
        Tüm servisleri durdurur.
        
        Returns:
            Dict[str, bool]: Her bir servisin durdurma durumu
        """
        # Stop event'i tetikle
        self.stop_event.set()
        
        results = {}
        
        for service_name in self.services:
            results[service_name] = await self.stop_service(service_name)
            
        log_str = ", ".join([f"{name}{'✓' if status else '✗'}" for name, status in results.items()])
        logger.info(f"Tüm servisler durduruldu: {log_str}")
        
        return results
        
    async def get_service_status(self, service_name: str) -> Dict[str, Any]:
        """
        Belirtilen servisin durumunu döndürür.
        
        Args:
            service_name: Servis adı
            
        Returns:
            Dict[str, Any]: Servis durum bilgisi
        """
        service = self.services.get(service_name)
        if not service:
            logger.error(f"Servis bulunamadı: {service_name}")
            return {"status": "unknown", "error": "Servis bulunamadı"}
            
        try:
            if hasattr(service, 'get_status') and callable(service.get_status):
                status = await service.get_status()
                return status
            else:
                # Temel durum bilgisi
                return {
                    "name": service_name,
                    "running": getattr(service, 'running', False),
                    "initialized": getattr(service, 'initialized', False)
                }
        except Exception as e:
            logger.exception(f"Servis durum hatası: {service_name} - {str(e)}")
            return {"status": "error", "error": str(e)}
            
    async def get_all_service_status(self) -> Dict[str, Dict[str, Any]]:
        """
        Tüm servislerin durumunu döndürür.
        
        Returns:
            Dict[str, Dict[str, Any]]: Servis adları ve durum bilgileri
        """
        result = {}
        
        for service_name in self.services:
            result[service_name] = await self.get_service_status(service_name)
            
        return result
        
    def create_service(self, service_type: str) -> Optional[BaseService]:
        """
        Belirtilen tipte yeni bir servis oluşturur.
        
        Args:
            service_type: Servis tipi/adı
            
        Returns:
            Optional[BaseService]: Oluşturulan servis ya da None
        """
        try:
            # MessageService için özel işlem
            if service_type == 'message':
                from app.services.message_service import MessageService
                # Gerekli parametreleri ekleyerek oluştur
                service = MessageService(
                    client=self.client,
                    config=self.config,
                    db=self.db,
                    stop_event=self.stop_event
                )
                return service
                
            # GroupService için özel işlem
            elif service_type == 'group':
                from app.services.group_service import GroupService
                service = GroupService(
                    client=self.client,
                    config=self.config,
                    db=self.db,
                    stop_event=self.stop_event
                )
                return service
                
            # UserService için özel işlem
            elif service_type == 'user':
                from app.services.user_service import UserService
                service = UserService(
                    client=self.client,
                    config=self.config,
                    db=self.db,
                    stop_event=self.stop_event
                )
                return service
                
            # GPTService için özel işlem
            elif service_type == 'gpt':
                from app.services.gpt_service import GPTService
                service = GPTService(
                    client=self.client,
                    config=self.config,
                    db=self.db,
                    stop_event=self.stop_event
                )
                return service
                
            # DM (Direct Message) Servisi için
            elif service_type == 'dm':
                try:
                    from app.services.messaging.dm_service import DirectMessageService
                    service = DirectMessageService(
                        client=self.client,
                        db=self.db
                    )
                    return service
                except ImportError:
                    logger.error("DirectMessageService import edilemedi. İlgili modüller bulunamadı.")
                    return None
                    
            # PromoService için
            elif service_type == 'promo':
                try:
                    from app.services.messaging.promo_service import PromoService
                    service = PromoService(
                        client=self.client,
                        db=self.db
                    )
                    return service
                except ImportError:
                    logger.error("PromoService import edilemedi. İlgili modüller bulunamadı.")
                    return None

            # InviteService için özel işlem
            elif service_type == 'invite':
                from app.services.invite_service import InviteService
                service = InviteService(
                    client=self.client,
                    config=self.config,
                    db=self.db,
                    stop_event=self.stop_event
                )
                return service
                
            # Diğer servis tipleri de eklenebilir
                
            else:
                logger.error(f"Bilinmeyen servis tipi: {service_type}")
                return None
                
        except Exception as e:
            logger.exception(f"Servis oluşturma hatası ({service_type}): {str(e)}")
            return None
            
    async def load_all_services(self) -> Dict[str, bool]:
        """
        Tüm temel servisleri yükler.
        
        Returns:
            Dict[str, bool]: Servis adları ve yükleme durumları
        """
        results = {}
        
        # Temel servisleri oluştur ve yükle
        service_types = ['message', 'group', 'user', 'gpt', 'dm', 'promo', 'invite']
        
        for service_type in service_types:
            try:
                service = self.create_service(service_type)
                
                if service:
                    self.services[service.service_name] = service
                    logger.info(f"Servis yüklendi: {service.service_name}")
                    results[service.service_name] = True
                else:
                    logger.error(f"Servis yüklenemedi: {service_type}")
                    results[service_type] = False
                    
            except Exception as e:
                logger.exception(f"Servis yükleme hatası ({service_type}): {str(e)}")
                results[service_type] = False
                
        return results