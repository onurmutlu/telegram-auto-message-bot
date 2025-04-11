"""
# ============================================================================ #
# Dosya: service_manager.py
# Yol: /Users/siyahkare/code/telegram-bot/bot/services/service_manager.py
# İşlev: Servislerin yaşam döngüsünü ve koordinasyonunu yöneten sınıf.
#
# © 2025 SiyahKare Yazılım - Tüm Hakları Saklıdır
# ============================================================================ #
"""

import asyncio
import logging
from typing import Dict, Any, List, Set, Optional

logger = logging.getLogger(__name__)

class ServiceManager:
    """
    Servislerin yaşam döngüsünü ve koordinasyonunu yöneten sınıf.
    
    Bu sınıf, servis başlatma, durdurma ve iletişim işlemlerini
    koordine eder. Servisler arasındaki bağımlılıkları yönetir ve
    hizmetlerin düzgün çalışmasını sağlar.
    
    Attributes:
        service_factory: Servis oluşturmak için fabrika nesnesi
        services: Servis adı -> Servis nesnesi eşleşmesi
        dependencies: Servis bağımlılıkları
        tasks: Çalışan görevler
    """
    
    def __init__(self, service_factory: Any):
        """
        ServiceManager sınıfının başlatıcısı.
        
        Args:
            service_factory: Servis oluşturmak için kullanılacak fabrika nesnesi
        """
        self.service_factory = service_factory
        self.services: Dict[str, Any] = {}
        self.dependencies: Dict[str, Set[str]] = {}
        self.tasks: List[asyncio.Task] = []
        
        # Bağımlılıkları tanımla
        self._setup_dependencies()
        
    def _setup_dependencies(self):
        """
        Servisler arasındaki bağımlılıkları tanımlar.
        
        Returns:
            None
        """
        # Servis bağımlılıklarını tanımla
        self.dependencies = {
            'user': set(),          # UserService bağımsız çalışabilir
            'group': set(),         # GroupService bağımsız çalışabilir
            'reply': set(),         # ReplyService bağımsız çalışabilir
            'dm': {'user'},         # DMService, UserService'e bağımlıdır
            'invite': {'dm'},       # InviteService, DMService'e bağımlıdır
        }
        
    async def create_and_register_services(self, service_names: List[str]) -> None:
        """
        Belirtilen servisleri oluşturur ve kaydeder.
        
        Args:
            service_names: Oluşturulacak servis adları
            
        Returns:
            None
        """
        logger.info(f"Servisler oluşturuluyor: {', '.join(service_names)}")
        
        for name in service_names:
            service = self.service_factory.create_service(name)
            if service:
                self.services[name] = service
                logger.info(f"Servis oluşturuldu: {name}")
            else:
                logger.warning(f"Servis oluşturulamadı: {name}")
                
        # Servislere referansları ilet
        self._inject_service_references()
        
    def _inject_service_references(self) -> None:
        """
        Her servise diğer servislere referansları enjekte eder.
        
        Returns:
            None
        """
        for name, service in self.services.items():
            if hasattr(service, 'set_services'):
                service.set_services(self.services)
                logger.debug(f"Servis referansları enjekte edildi: {name}")
                
    async def start_services(self) -> None:
        """
        Tüm servisleri başlatır. Bağımlılıkları göz önünde bulundurarak sıralı başlatma yapar.
        
        Returns:
            None
        """
        # Başlatma sırasını belirle (bağımlılıklara göre)
        start_order = self._determine_start_order()
        logger.info(f"Servisler başlatılıyor. Sıra: {', '.join(start_order)}")
        
        # Servisleri başlat
        for name in start_order:
            if name in self.services:
                service = self.services[name]
                try:
                    # Servisi başlat
                    logger.info(f"Servis başlatılıyor: {name}")
                    
                    # İlk olarak initialize
                    init_success = await service.initialize()
                    if not init_success:
                        logger.error(f"Servis başlatılamadı (initialize hatası): {name}")
                        continue
                        
                    # Sonra start
                    start_success = await service.start()
                    if not start_success:
                        logger.error(f"Servis başlatılamadı (start hatası): {name}")
                        continue
                        
                    # Servis döngüsünü başlat
                    task = asyncio.create_task(service.run())
                    self.tasks.append(task)
                    
                    logger.info(f"Servis başlatıldı: {name}")
                    
                except Exception as e:
                    logger.error(f"Servis başlatma hatası ({name}): {str(e)}")
                
    def _determine_start_order(self) -> List[str]:
        """
        Servis başlatma sırasını belirler (bağımlılıklara göre).
        
        Returns:
            List[str]: Servis başlatma sırası
        """
        result = []
        visited = set()
        
        def visit(name):
            if name in visited:
                return
            visited.add(name)
            
            # Önce bağımlılıkları ekle
            if name in self.dependencies:
                for dependency in self.dependencies[name]:
                    visit(dependency)
                    
            result.append(name)
            
        # Tüm servisleri dolaş
        for name in self.services.keys():
            visit(name)
            
        return result
        
    async def stop_services(self) -> None:
        """
        Tüm servisleri güvenli bir şekilde durdurur.
        
        Returns:
            None
        """
        # Durdurma sırasını belirle (başlatma sırasının tersi)
        stop_order = self._determine_start_order()
        stop_order.reverse()  # Tersten
        
        logger.info(f"Servisler durduruluyor. Sıra: {', '.join(stop_order)}")
        
        # Servisleri durdur
        for name in stop_order:
            if name in self.services:
                service = self.services[name]
                try:
                    logger.info(f"Servis durduruluyor: {name}")
                    await service.stop()
                    logger.info(f"Servis durduruldu: {name}")
                except Exception as e:
                    logger.error(f"Servis durdurma hatası ({name}): {str(e)}")
                    
        # Görevleri bekle
        if self.tasks:
            for task in self.tasks:
                if not task.done():
                    task.cancel()
                    
            await asyncio.gather(*self.tasks, return_exceptions=True)
            self.tasks.clear()
            
    async def get_status(self) -> Dict[str, Dict[str, Any]]:
        """
        Tüm servislerin durumunu getirir.
        
        Returns:
            Dict: Servis adı -> Servis durumu eşleşmesi
        """
        status = {}
        for name, service in self.services.items():
            if hasattr(service, 'get_status'):
                status[name] = await service.get_status()
                
        return status
        
    async def get_statistics(self) -> Dict[str, Dict[str, Any]]:
        """
        Tüm servislerin istatistiklerini getirir.
        
        Returns:
            Dict: Servis adı -> Servis istatistikleri eşleşmesi
        """
        statistics = {}
        for name, service in self.services.items():
            if hasattr(service, 'get_statistics'):
                statistics[name] = await service.get_statistics()
                
        return statistics
        
    async def pause_service(self, service_name: str) -> bool:
        """
        Belirli bir servisi duraklatır.
        
        Args:
            service_name: Durdurulacak servis adı
            
        Returns:
            bool: Başarılı ise True
        """
        if service_name in self.services:
            service = self.services[service_name]
            if hasattr(service, 'pause'):
                await service.pause()
                return True
                
        return False
        
    async def resume_service(self, service_name: str) -> bool:
        """
        Duraklatılmış bir servisi devam ettirir.
        
        Args:
            service_name: Devam ettirilecek servis adı
            
        Returns:
            bool: Başarılı ise True
        """
        if service_name in self.services:
            service = self.services[service_name]
            if hasattr(service, 'resume'):
                await service.resume()
                return True
                
        return False