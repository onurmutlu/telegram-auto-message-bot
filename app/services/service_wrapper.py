"""
# ============================================================================ #
# Dosya: service_wrapper.py
# Yol: /Users/siyahkare/code/telegram-bot/app/services/service_wrapper.py
# İşlev: ServiceManager için tek bir entry-point sağlayan wrapper sınıfı.
#
# © 2025 SiyahKare Yazılım - Tüm Hakları Saklıdır
# ============================================================================ #
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Set

from app.services.service_factory import ServiceFactory
from app.services.service_manager import ServiceManager

logger = logging.getLogger(__name__)

class ServiceWrapper:
    """
    ServiceManager için tek bir entry-point sağlayan wrapper sınıfı.
    
    Bu sınıf, service manager'a daha basit bir arayüz sunar ve
    tüm servisleri tek bir noktadan yönetmeyi kolaylaştırır.
    """
    
    def __init__(
        self, 
        client=None, 
        config=None, 
        db=None, 
        stop_event=None, 
        services_to_run: Optional[List[str]] = None
    ):
        """
        ServiceWrapper sınıfının başlatıcısı.
        
        Args:
            client: Telegram istemcisi
            config: Yapılandırma nesnesi
            db: Veritabanı bağlantısı
            stop_event: Durdurma sinyali
            services_to_run: Başlatılacak servis listesi (None ise tüm aktif servisler)
        """
        self.client = client
        self.config = config
        self.db = db
        self.stop_event = stop_event or asyncio.Event()
        
        # ServiceFactory ve ServiceManager oluştur
        self.service_factory = ServiceFactory(client, config, db, self.stop_event)
        self.service_manager = ServiceManager(self.service_factory, client, config, db, self.stop_event)
        
        # Başlatılacak servisleri ayarla
        if services_to_run is not None:
            self.service_manager.active_services = services_to_run
            
        # Durumu takip et
        self.is_running = False
        
        # Tasks listesi - service_manager'dan alınacak
        self.tasks = []
    
    async def start(self) -> bool:
        """
        Tüm servisleri başlatır.
        
        Returns:
            bool: Başarılı ise True
        """
        if self.is_running:
            logger.warning("Servisler zaten çalışıyor")
            return True
            
        try:
            # Başlamadan önce aktif servis listesini kontrol et
            if not self.service_manager.active_services:
                logger.error("Aktif servis listesi boş, başlatılacak servis yok")
                return False
                
            # Hiçbir servis başlatılamaması durumunu önle
            if len(self.service_manager.active_services) == 0:
                logger.error("Başlatılacak servis belirtilmemiş")
                return False
            
            # Belirtilen tüm servislerin var olduğunu kontrol et
            for service_name in self.service_manager.active_services:
                if service_name not in self.service_manager.available_services:
                    logger.warning(f"'{service_name}' servisi mevcut değil, bu servis atlanacak")
            
            # Tüm servisleri başlat
            logger.info(f"Başlatılacak servisler: {', '.join(self.service_manager.active_services)}")
            
            result = await self.service_manager.start_all()
            
            if result:
                self.is_running = True
                # Tasks listesini güncelle (None kontrolü yap)
                if hasattr(self.service_manager, 'tasks'):
                    self.tasks = self.service_manager.tasks
                    logger.info(f"ServiceWrapper: {len(self.tasks)} servis görevi başlatıldı")
                else:
                    logger.warning("ServiceWrapper: Service manager'da tasks listesi bulunamadı")
                
                logger.info("ServiceWrapper: Tüm servisler başlatıldı")
            else:
                logger.error("ServiceWrapper: Servisler başlatılamadı")
                
            return result
        except Exception as e:
            logger.error(f"ServiceWrapper başlatma hatası: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    async def stop(self) -> bool:
        """
        Tüm servisleri durdurur.
        
        Returns:
            bool: Başarılı ise True
        """
        if not self.is_running:
            logger.warning("Servisler zaten durdurulmuş")
            return True
            
        try:
            # Tüm servisleri durdur
            result = await self.service_manager.stop_all()
            if result:
                self.is_running = False
                logger.info("ServiceWrapper: Tüm servisler durduruldu")
            return result
        except Exception as e:
            logger.error(f"ServiceWrapper durdurma hatası: {str(e)}")
            return False
    
    async def restart(self) -> bool:
        """
        Tüm servisleri yeniden başlatır.
        
        Returns:
            bool: Başarılı ise True
        """
        try:
            await self.stop()
            return await self.start()
        except Exception as e:
            logger.error(f"ServiceWrapper yeniden başlatma hatası: {str(e)}")
            return False
    
    async def add_service(self, service_name: str) -> bool:
        """
        Belirli bir servisi aktif listeye ekler ve başlatır.
        
        Args:
            service_name: Eklenecek servis adı
            
        Returns:
            bool: Başarılı ise True
        """
        try:
            # Servis zaten aktif mi kontrol et
            if service_name in self.service_manager.active_services:
                logger.warning(f"Servis zaten aktif: {service_name}")
                return True
                
            # Listeye ekle
            self.service_manager.active_services.append(service_name)
            
            # Çalışıyorsa servisi oluştur ve başlat
            if self.is_running:
                if service_name not in self.service_manager.services:
                    created = await self.service_manager.register_service(service_name)
                    if not created:
                        logger.error(f"Servis oluşturulamadı: {service_name}")
                        return False
                        
                    # İletişimi kur
                    await self.service_manager.initialize_service_communications()
                    
                    # Servisi al ve None kontrolü yap
                    service = self.service_manager.services.get(service_name)
                    if service is None:
                        logger.error(f"Servis {service_name} oluşturuldu ancak None değeri döndü")
                        return False
                    
                    # initialize et
                    init_success = await service.initialize()
                    if not init_success:
                        logger.error(f"Servis başlatılamadı (initialize hatası): {service_name}")
                        return False
                        
                    # Başlat
                    start_success = await service.start()
                    if not start_success:
                        logger.error(f"Servis başlatılamadı (start hatası): {service_name}")
                        return False
                        
                    # Task oluştur
                    task = asyncio.create_task(service.run())
                    task.set_name(f"service_task_{service_name}")
                    self.service_manager.tasks.append(task)
                    
                    logger.info(f"Servis başlatıldı: {service_name}")
            
            return True
        except Exception as e:
            logger.error(f"Servis ekleme hatası ({service_name}): {str(e)}")
            return False
    
    async def remove_service(self, service_name: str) -> bool:
        """
        Belirli bir servisi aktif listeden çıkarır ve durdurur.
        
        Args:
            service_name: Çıkarılacak servis adı
            
        Returns:
            bool: Başarılı ise True
        """
        try:
            # Servis aktif mi kontrol et
            if service_name not in self.service_manager.active_services:
                logger.warning(f"Servis zaten aktif değil: {service_name}")
                return True
                
            # Listeden çıkar
            self.service_manager.active_services.remove(service_name)
            
            # Çalışıyorsa servisi durdur
            if self.is_running and service_name in self.service_manager.services:
                service = self.service_manager.services[service_name]
                
                # Servisi durdur
                try:
                    stop_success = await service.stop()
                    if not stop_success:
                        logger.error(f"Servis durdurulamadı: {service_name}")
                        return False
                        
                    # İlgili task'ı bul ve iptal et
                    for task in self.service_manager.tasks:
                        if task.get_name() == f"service_task_{service_name}":
                            if not task.done() and not task.cancelled():
                                task.cancel()
                                try:
                                    await task
                                except asyncio.CancelledError:
                                    pass
                                except Exception as task_e:
                                    logger.error(f"Task iptal hatası ({service_name}): {str(task_e)}")
                            
                            # Task'ı listeden çıkar
                            self.service_manager.tasks.remove(task)
                            break
                    
                    logger.info(f"Servis durduruldu: {service_name}")
                except Exception as e:
                    logger.error(f"Servis durdurma hatası ({service_name}): {str(e)}")
                    return False
            
            return True
        except Exception as e:
            logger.error(f"Servis çıkarma hatası ({service_name}): {str(e)}")
            return False
    
    def get_service(self, service_name: str) -> Any:
        """
        Belirli bir servisi getirir.
        
        Args:
            service_name: Servis adı
            
        Returns:
            Any: Servis nesnesi veya None
        """
        return self.service_manager.get_service(service_name)
    
    def get_active_services(self) -> List[str]:
        """
        Aktif servislerin listesini döndürür.
        
        Returns:
            List[str]: Aktif servis adları
        """
        return self.service_manager.active_services
    
    def get_available_services(self) -> List[str]:
        """
        Kullanılabilir tüm servislerin listesini döndürür.
        
        Returns:
            List[str]: Kullanılabilir servis adları
        """
        return self.service_manager.available_services
    
    async def list_services(self) -> Dict[str, Dict[str, Any]]:
        """
        Tüm servislerin durumunu içeren bir liste döndürür.
        
        Returns:
            Dict[str, Dict[str, Any]]: Servis adı -> Servis durumu listesi
        """
        return await self.service_manager.get_status()
    
    async def get_service_status(self) -> Dict[str, Dict[str, Any]]:
        """
        Tüm servislerin durumunu döndürür.
        
        Returns:
            Dict: Servis adı -> Durum eşleşmesi
        """
        return await self.service_manager.get_status()
    
    async def get_status(self) -> Dict[str, Dict[str, Any]]:
        """
        Tüm servislerin durumunu döndürür.
        Bu metod, get_service_status metodunun bir aliası olarak kullanılır.
        
        Returns:
            Dict: Servis adı -> Durum eşleşmesi
        """
        return await self.service_manager.get_status()
    
    async def get_service_statistics(self) -> Dict[str, Dict[str, Any]]:
        """
        Tüm servislerin istatistiklerini döndürür.
        
        Returns:
            Dict: Servis adı -> İstatistik eşleşmesi
        """
        return await self.service_manager.get_statistics() 