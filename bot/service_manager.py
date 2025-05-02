#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ServiceManager - Servis başlatma, durdurma ve bağımlılık yönetimi için merkezi yönetici
"""

import os
import sys
import time
import asyncio
import logging
import inspect
import traceback
from typing import Dict, List, Any, Optional, Set, Tuple, Union, Callable, Type
from enum import Enum
from datetime import datetime, timedelta

from bot.services.base_service import BaseService
from bot.services.event_service import EventService, EventBus, Event

# Log ayarları
logger = logging.getLogger(__name__)

class ServiceStatus(Enum):
    """Servis durumlarını temsil eden enum"""
    UNINITIALIZED = 0
    INITIALIZING = 1
    INITIALIZED = 2
    STARTING = 3
    RUNNING = 4
    STOPPING = 5
    STOPPED = 6
    FAILED = 7
    
    def __str__(self):
        return self.name
    
    @property
    def is_running(self):
        return self in (ServiceStatus.RUNNING, ServiceStatus.STARTING)
    
    @property
    def is_stopped(self):
        return self in (ServiceStatus.STOPPED, ServiceStatus.UNINITIALIZED)
    
    @property
    def is_failed(self):
        return self == ServiceStatus.FAILED

class ServiceManagerException(Exception):
    """ServiceManager özel istisna sınıfı"""
    pass

class ServiceDependencyGraph:
    """
    Servisler arasındaki bağımlılık ilişkilerini temsil eden graf
    """
    def __init__(self):
        self.dependencies = {}  # service_name -> [dependencies]
        self.dependents = {}    # service_name -> [dependents]
        
    def add_dependency(self, service: str, dependency: str):
        """Bir servisin bağımlılığını ekle"""
        # Servis bağımlılıklarını ekle
        if service not in self.dependencies:
            self.dependencies[service] = set()
        self.dependencies[service].add(dependency)
        
        # Karşı yönlü bağımlılıkları (bağımlı olanları) ekle
        if dependency not in self.dependents:
            self.dependents[dependency] = set()
        self.dependents[dependency].add(service)
        
    def get_dependencies(self, service: str) -> Set[str]:
        """Bir servisin bağımlılıklarını döndür"""
        return self.dependencies.get(service, set())
        
    def get_dependents(self, service: str) -> Set[str]:
        """Bir servise bağımlı olan servisleri döndür"""
        return self.dependents.get(service, set())
        
    def get_all_services(self) -> Set[str]:
        """Tüm servisleri döndür"""
        services = set(self.dependencies.keys())
        for deps in self.dependencies.values():
            services.update(deps)
        return services
        
    def get_roots(self) -> Set[str]:
        """Bağımlılığı olmayan (kök) servisleri döndür"""
        all_services = self.get_all_services()
        roots = set()
        
        for service in all_services:
            if service not in self.dependencies or not self.dependencies[service]:
                roots.add(service)
                
        return roots
        
    def get_leaves(self) -> Set[str]:
        """Hiçbir servisin bağımlı olmadığı (yaprak) servisleri döndür"""
        all_services = self.get_all_services()
        leaves = set()
        
        for service in all_services:
            if service not in self.dependents or not self.dependents[service]:
                leaves.add(service)
                
        return leaves
        
    def get_start_order(self) -> List[str]:
        """
        Servis başlatma sırasını topological sort ile hesapla
        Returns:
            Önce başlatılması gereken servisler listenin başında
        """
        all_services = self.get_all_services()
        visited = set()
        temp_visited = set()
        order = []
        
        def visit(service):
            if service in temp_visited:
                raise ServiceManagerException(f"Döngüsel bağımlılık tespit edildi. Servis: {service}")
                
            if service in visited:
                return
                
            temp_visited.add(service)
            
            for dependency in self.get_dependencies(service):
                visit(dependency)
                
            temp_visited.remove(service)
            visited.add(service)
            order.append(service)
        
        # Yaprak servisleri son başlatılacak şekilde sırala
        for service in all_services:
            if service not in visited:
                visit(service)
                
        return list(reversed(order))
        
    def get_stop_order(self) -> List[str]:
        """
        Servis durdurma sırasını hesapla
        Returns:
            Önce durdurulması gereken servisler listenin başında
        """
        # Durdurma sırası, başlatma sırasının tam tersidir
        return list(reversed(self.get_start_order()))
        
    def has_circular_dependencies(self) -> bool:
        """Döngüsel bağımlılık olup olmadığını kontrol et"""
        try:
            self.get_start_order()
            return False
        except ServiceManagerException:
            return True
            
    def detect_circular_dependencies(self) -> List[str]:
        """Döngüsel bağımlılıkları tespit et ve döndür"""
        all_services = self.get_all_services()
        visited = set()
        path = []
        cycles = []
        
        def visit(service):
            if service in path:
                cycle_start_index = path.index(service)
                cycles.append(path[cycle_start_index:] + [service])
                return
                
            if service in visited:
                return
                
            visited.add(service)
            path.append(service)
            
            for dependency in self.get_dependencies(service):
                visit(dependency)
                
            path.pop()
        
        for service in all_services:
            if service not in visited:
                visit(service)
                
        return cycles

class ServiceManager:
    """
    Servis başlatma, durdurma ve bağımlılık yönetimi için merkezi yönetici
    Singleton pattern kullanır
    """
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(ServiceManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, config=None, db=None, client=None):
        """
        ServiceManager constructor
        
        Args:
            config: Uygulama yapılandırması
            db: Veritabanı bağlantısı
            client: Telegram istemcisi
        """
        if self._initialized:
            return
            
        self.config = config
        self.db = db
        self.client = client
        
        self.services = {}  # service_name -> service_instance
        self.service_classes = {}  # service_name -> service_class
        self.service_status = {}  # service_name -> ServiceStatus
        self.service_errors = {}  # service_name -> error
        self.service_start_times = {}  # service_name -> start_time
        self.service_stop_times = {}  # service_name -> stop_time
        
        self.dependency_graph = ServiceDependencyGraph()
        self.stop_event = asyncio.Event()
        self.initialization_lock = asyncio.Lock()
        self._running = False
        
        # Otomatik olarak EventService ekle
        self._initialized = True
    
    def register_service_class(self, service_class: Type[BaseService], dependencies: List[str] = None):
        """
        Bir servis sınıfını kaydet
        
        Args:
            service_class: Kaydedilecek servis sınıfı
            dependencies: Servisin bağımlı olduğu diğer servisler
        """
        # Sınıf BaseService'ten türetilmiş mi kontrol et
        if not issubclass(service_class, BaseService):
            raise ServiceManagerException(f"{service_class.__name__} sınıfı BaseService'ten türetilmemiş")
            
        # Servis adını al (BaseService'ten geliyor)
        service_name = service_class.get_service_name()
        
        # Servisi kaydet
        self.service_classes[service_name] = service_class
        self.service_status[service_name] = ServiceStatus.UNINITIALIZED
        
        # Bağımlılıkları kaydet
        dependencies = dependencies or []
        for dependency in dependencies:
            self.dependency_graph.add_dependency(service_name, dependency)
            
        logger.info(f"Servis sınıfı kaydedildi: {service_name}")
        
    def register_service(self, service: BaseService, dependencies: List[str] = None):
        """
        Bir servis örneğini kaydet
        
        Args:
            service: Kaydedilecek servis örneği
            dependencies: Servisin bağımlı olduğu diğer servisler
        """
        service_name = service.service_name
        
        # Servisi kaydet
        self.services[service_name] = service
        self.service_status[service_name] = ServiceStatus.UNINITIALIZED
        
        # Bağımlılıkları kaydet
        dependencies = dependencies or []
        for dependency in dependencies:
            self.dependency_graph.add_dependency(service_name, dependency)
            
        logger.info(f"Servis kaydedildi: {service_name}")
        
    def get_service(self, service_name: str) -> Optional[BaseService]:
        """
        Bir servisi adına göre döndür
        
        Args:
            service_name: Servis adı
            
        Returns:
            Servis örneği veya None
        """
        return self.services.get(service_name)
        
    def get_service_status(self, service_name: str) -> Optional[ServiceStatus]:
        """
        Bir servisin durumunu döndür
        
        Args:
            service_name: Servis adı
            
        Returns:
            Servis durumu veya None
        """
        return self.service_status.get(service_name)
        
    def get_service_error(self, service_name: str) -> Optional[Exception]:
        """
        Bir servisin hatasını döndür
        
        Args:
            service_name: Servis adı
            
        Returns:
            Servis hatası veya None
        """
        return self.service_errors.get(service_name)
        
    def get_service_uptime(self, service_name: str) -> Optional[timedelta]:
        """
        Bir servisin çalışma süresini döndür
        
        Args:
            service_name: Servis adı
            
        Returns:
            Çalışma süresi veya None
        """
        if service_name not in self.service_start_times:
            return None
            
        start_time = self.service_start_times[service_name]
        
        if service_name in self.service_stop_times:
            stop_time = self.service_stop_times[service_name]
            return stop_time - start_time
        else:
            return datetime.now() - start_time
    
    def get_all_services(self) -> Dict[str, BaseService]:
        """
        Tüm servisleri döndür
        
        Returns:
            Servis adı -> servis örneği sözlüğü
        """
        return self.services.copy()
        
    def get_all_service_statuses(self) -> Dict[str, ServiceStatus]:
        """
        Tüm servislerin durumlarını döndür
        
        Returns:
            Servis adı -> servis durumu sözlüğü
        """
        return self.service_status.copy()
        
    async def initialize_service(self, service_name: str) -> bool:
        """
        Bir servisi başlat
        
        Args:
            service_name: Başlatılacak servis adı
            
        Returns:
            bool: Başarılı ise True
        """
        # Servis var mı kontrol et
        if service_name not in self.services and service_name not in self.service_classes:
            logger.error(f"Servis bulunamadı: {service_name}")
            return False
            
        # Servis zaten başlatılmış mı?
        status = self.service_status.get(service_name)
        if status in (ServiceStatus.INITIALIZED, ServiceStatus.STARTING, ServiceStatus.RUNNING):
            logger.info(f"Servis zaten başlatılmış: {service_name} (durum: {status})")
            return True
            
        # Bağımlılıkları kontrol et ve başlat
        dependencies = self.dependency_graph.get_dependencies(service_name)
        for dependency in dependencies:
            dep_status = self.service_status.get(dependency)
            if dep_status not in (ServiceStatus.INITIALIZED, ServiceStatus.RUNNING):
                logger.info(f"{service_name} servisi {dependency} bağımlılığını bekliyor")
                
                # Bağımlılığı başlat
                if not await self.initialize_service(dependency):
                    logger.error(f"{service_name} servisi {dependency} bağımlılığı başlatılamadı")
                    self.service_status[service_name] = ServiceStatus.FAILED
                    return False
        
        # Servis örneğini al veya oluştur
        service = self.services.get(service_name)
        if not service and service_name in self.service_classes:
            # Servisi dinamik olarak oluştur
            service_class = self.service_classes[service_name]
            try:
                service = service_class(client=self.client, config=self.config, db=self.db, stop_event=self.stop_event)
                self.services[service_name] = service
                logger.info(f"Servis dinamik olarak oluşturuldu: {service_name}")
            except Exception as e:
                logger.error(f"Servis oluşturma hatası {service_name}: {str(e)}", exc_info=True)
                self.service_errors[service_name] = e
                self.service_status[service_name] = ServiceStatus.FAILED
                return False
        
        # Servisi başlat
        try:
            self.service_status[service_name] = ServiceStatus.INITIALIZING
            
            # initialize() metodu varsa çağır
            if hasattr(service, 'initialize') and callable(service.initialize):
                logger.info(f"Servis başlatılıyor: {service_name}")
                success = await service.initialize()
                
                if not success:
                    logger.error(f"Servis başlatılamadı: {service_name}")
                    self.service_status[service_name] = ServiceStatus.FAILED
                    return False
            
            self.service_status[service_name] = ServiceStatus.INITIALIZED
            logger.info(f"Servis başlatıldı: {service_name}")
            return True
            
        except Exception as e:
            error_msg = f"Servis başlatma hatası {service_name}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.service_errors[service_name] = e
            self.service_status[service_name] = ServiceStatus.FAILED
            return False
    
    async def start_service(self, service_name: str) -> bool:
        """
        Belirtilen servisi başlatır ve çalışma döngüsünü başlatır.
        
        Args:
            service_name: Başlatılacak servisin adı
            
        Returns:
            bool: Başarılı ise True
        """
        try:
            service = self.services.get(service_name)
            if not service:
                logger.error(f"Başlatılacak servis bulunamadı: {service_name}")
                return False
            
            # Servisin başlatılma durumunu kontrol et
            if hasattr(service, 'running') and service.running:
                logger.debug(f"Servis {service_name} zaten çalışıyor, atlanıyor")
                return True
            
            # Öncelikle servisi başlat
            success = False
            try:
                # Önce initialize et
                if not hasattr(service, 'initialized') or not service.initialized:
                    await service.initialize()
                
                # Sonra başlat
                success = await service.start()
                
                if not success:
                    logger.error(f"Servis {service_name} başlatılamadı")
                    return False
                    
            except Exception as e:
                logger.error(f"Servis {service_name} başlatılırken hata: {str(e)}")
                logger.debug(traceback.format_exc())
                return False
            
            # Çalışma döngüsünü başlat
            if hasattr(service, 'run') and callable(service.run):
                # Servis için task oluştur
                task = asyncio.create_task(service.run())
                task.set_name(f"service_task_{service_name}")
                self.tasks.append(task)
                logger.info(f"Servis {service_name} başlatıldı ve çalışma döngüsü etkinleştirildi")
            else:
                if service_name in self.critical_services:
                    logger.error(f"KRİTİK SERVİS {service_name} 'run' metoduna sahip değil! Bu servis otomatik çalışamayacak.")
                else:
                    logger.warning(f"Servis {service_name} 'run' metoduna sahip değil. Elle çağrılması gerekecek.")
                
                # Servisin durumunu True olarak işaretle
                if hasattr(service, 'running'):
                    service.running = True
                elif hasattr(service, 'is_running'):
                    service.is_running = True
                
            return True
            
        except Exception as e:
            logger.error(f"Servis {service_name} başlatılırken beklenmeyen hata: {str(e)}")
            logger.debug(traceback.format_exc())
            return False
    
    async def stop_service(self, service_name: str) -> bool:
        """
        Bir servisi durdur
        
        Args:
            service_name: Durdurulacak servis adı
            
        Returns:
            bool: Başarılı ise True
        """
        # Servis var mı kontrol et
        if service_name not in self.services:
            logger.error(f"Servis bulunamadı: {service_name}")
            return False
            
        # Servis zaten durdurulmuş mu?
        status = self.service_status.get(service_name)
        if status in (ServiceStatus.STOPPED, ServiceStatus.UNINITIALIZED):
            logger.info(f"Servis zaten durdurulmuş: {service_name}")
            return True
            
        service = self.services[service_name]
        
        # Bu servise bağımlı olan servisleri durdur
        dependents = self.dependency_graph.get_dependents(service_name)
        for dependent in dependents:
            dep_status = self.service_status.get(dependent)
            if dep_status not in (ServiceStatus.STOPPED, ServiceStatus.UNINITIALIZED):
                logger.info(f"{service_name} servisi durdurulmadan önce {dependent} bağımlısı durduruluyor")
                
                # Bağımlı servisi durdur
                if not await self.stop_service(dependent):
                    logger.error(f"{service_name} servisi durdurulamadı çünkü {dependent} bağımlısı durdurulamadı")
                    return False
        
        # Servisi durdur
        try:
            self.service_status[service_name] = ServiceStatus.STOPPING
            
            # stop() metodu varsa çağır
            if hasattr(service, 'stop') and callable(service.stop):
                logger.info(f"Servis durduruluyor: {service_name}")
                await service.stop()
            
            self.service_stop_times[service_name] = datetime.now()
            self.service_status[service_name] = ServiceStatus.STOPPED
            logger.info(f"Servis durduruldu: {service_name}")
            
            # Event dağıt
            await self._emit_service_event("service_stopped", service_name)
            
            return True
            
        except Exception as e:
            error_msg = f"Servis durdurma hatası {service_name}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.service_errors[service_name] = e
            
            # Başarısız olsa da durduruldu olarak işaretle
            self.service_status[service_name] = ServiceStatus.STOPPED
            
            # Event dağıt
            await self._emit_service_event("service_stop_failed", service_name, {"error": str(e)})
            
            return False
    
    async def restart_service(self, service_name: str) -> bool:
        """
        Bir servisi yeniden başlat
        
        Args:
            service_name: Yeniden başlatılacak servis adı
            
        Returns:
            bool: Başarılı ise True
        """
        await self.stop_service(service_name)
        return await self.start_service(service_name)
    
    async def start_all_services(self, custom_order: List[str] = None) -> bool:
        """
        Tüm servisleri başlat
        
        Args:
            custom_order: Özel başlatma sırası (None ise dependency graph kullanılır)
            
        Returns:
            bool: Tümü başarılı ise True
        """
        # Başlatma sırasını belirle
        if custom_order:
            start_order = custom_order
        else:
            start_order = self.dependency_graph.get_start_order()
            
        # Tüm servisleri başlat
        all_success = True
        for service_name in start_order:
            if service_name in self.services or service_name in self.service_classes:
                if not await self.start_service(service_name):
                    logger.error(f"{service_name} servisi başlatılamadı")
                    all_success = False
                    
        return all_success
    
    async def stop_all_services(self, custom_order: List[str] = None) -> bool:
        """
        Tüm servisleri durdur
        
        Args:
            custom_order: Özel durdurma sırası (None ise dependency graph kullanılır)
            
        Returns:
            bool: Tümü başarılı ise True
        """
        # Durdurma sırasını belirle
        if custom_order:
            stop_order = custom_order
        else:
            stop_order = self.dependency_graph.get_stop_order()
            
        # Stop event'i ayarla
        self.stop_event.set()
            
        # Tüm servisleri durdur
        all_success = True
        for service_name in stop_order:
            if service_name in self.services:
                if not await self.stop_service(service_name):
                    logger.error(f"{service_name} servisi durdurulamadı")
                    all_success = False
                    
        return all_success
    
    async def stop_services(self) -> None:
        """
        Tüm servisleri durdurur. 
        Bu metod eski kod tabanı ile uyumluluk içindir ve stop_all_services'i çağırır.
        
        Returns:
            bool: Tümü başarılı ise True
        """
        # Stop event'i ayarla
        self.stop_event.set()
        
        # Tüm servisleri durdur
        try:
            # Çalışan servisleri belirle ve sadece onları durdur
            running_services = []
            for name, service in self.services.items():
                is_running = False
                
                if hasattr(service, 'running'):
                    is_running = service.running
                elif hasattr(service, 'is_running'):
                    is_running = service.is_running
                    
                if is_running:
                    running_services.append(name)
            
            # Durdurma sırasını belirle (sadece çalışan servisler için)
            stop_order = self.dependency_graph.get_stop_order()
            
            # Sadece çalışan servisleri durdurma sırasında tut
            filtered_stop_order = [s for s in stop_order if s in running_services]
            
            if filtered_stop_order:
                logger.info("Servisler durduruluyor. Sıra: " + ", ".join(filtered_stop_order))
                
                # Servisleri sırayla durdur
                for service_name in filtered_stop_order:
                    service = self.services.get(service_name)
                    if not service:
                        logger.warning(f"Durdurulacak servis bulunamadı: {service_name}")
                        continue
                        
                    try:
                        logger.info(f"Servis durduruluyor: {service_name}")
                        # stop metodu varsa çağır
                        if hasattr(service, 'stop') and callable(service.stop):
                            await service.stop()
                            
                            # Durduruldu olarak işaretle
                            if hasattr(service, 'running'):
                                service.running = False
                            if hasattr(service, 'is_running'):
                                service.is_running = False
                                
                            logger.info(f"Servis durduruldu: {service_name}")
                    except Exception as e:
                        logger.error(f"Servis durdurulurken hata: {service_name} - {str(e)}")
            else:
                logger.info("Çalışan servis bulunmadı, durdurma işlemi atlanıyor.")
                
            return True
        except Exception as e:
            logger.error(f"Servisleri durdururken hata: {str(e)}")
            return False
    
    async def dependency_check(self, print_graph=False):
        """
        Servis bağımlılıklarını kontrol et
        
        Args:
            print_graph: Bağımlılık grafını yazdır
        """
        # Kaydedilmiş tüm servisleri al
        all_services = set(self.services.keys()) | set(self.service_classes.keys())
        
        # Grafdaki tüm servisleri al
        graph_services = self.dependency_graph.get_all_services()
        
        # Grafta olmayan servisleri kontrol et
        missing_in_graph = all_services - graph_services
        if missing_in_graph:
            logger.warning(f"Bağımlılık grafında olmayan servisler: {missing_in_graph}")
            
        # Kayıt edilmemiş servisleri kontrol et
        missing_registration = graph_services - all_services
        if missing_registration:
            logger.warning(f"Kayıt edilmemiş servisler: {missing_registration}")
            
        # Döngüsel bağımlılıkları kontrol et
        cycles = self.dependency_graph.detect_circular_dependencies()
        if cycles:
            logger.error(f"Döngüsel bağımlılıklar tespit edildi:")
            for cycle in cycles:
                cycle_str = " -> ".join(cycle)
                logger.error(f"  Döngü: {cycle_str}")
                
        # Bağımlılık grafını yazdır
        if print_graph:
            logger.info("Servis bağımlılık grafı:")
            for service in sorted(graph_services):
                dependencies = self.dependency_graph.get_dependencies(service)
                dependents = self.dependency_graph.get_dependents(service)
                
                if dependencies:
                    deps_str = ", ".join(sorted(dependencies))
                    logger.info(f"  {service} bağımlılıkları: {deps_str}")
                    
                if dependents:
                    deps_str = ", ".join(sorted(dependents))
                    logger.info(f"  {service}'e bağımlı: {deps_str}")
                    
            # Başlatma ve durdurma sıralarını yazdır
            try:
                start_order = self.dependency_graph.get_start_order()
                logger.info(f"Başlatma sırası: {start_order}")
                
                stop_order = self.dependency_graph.get_stop_order()
                logger.info(f"Durdurma sırası: {stop_order}")
            except ServiceManagerException as e:
                logger.error(f"Sıralama hesaplanırken hata: {str(e)}")
    
    async def _emit_service_event(self, event_type: str, service_name: str, data: Dict = None):
        """
        Servis olayı yayınla
        
        Args:
            event_type: Olay tipi
            service_name: Servis adı
            data: Ek veri
        """
        try:
            # EventService var mı kontrol et
            event_service = self.get_service("event")
            if event_service:
                event_data = data or {}
                event_data["service_name"] = service_name
                await event_service.emit(event_type, event_data)
            else:
                # EventBus singleton'ını kullan
                event_bus = EventBus()
                event_data = data or {}
                event_data["service_name"] = service_name
                await event_bus.emit(event_type, event_data, source="service_manager")
        except Exception as e:
            logger.error(f"Servis olayı yayınlanırken hata: {str(e)}")

    async def start_services(self) -> None:
        """
        Tüm servisleri başlatır ve çalışma döngülerini başlatır.
        
        Returns:
            None
        """
        logger.info("Servisler başlatılıyor...")
        
        # Kritik servisleri otomatik ekle
        self.critical_services = [
            "message",
            "promo",
            "group",
            "user",
            "error"
        ]
        
        if not hasattr(self, 'tasks'):
            self.tasks = []
        
        # Servislerin başlatılma sırasını belirle
        start_order = self._determine_start_order()
        logger.info(f"Servisler başlatma sırası: {', '.join(start_order)}")
        
        # Önce kritik servisleri başlat
        critical_services = [s for s in start_order if s in self.critical_services]
        if critical_services:
            logger.info(f"Kritik servisler önce başlatılıyor: {', '.join(critical_services)}")
            
            # Kritik servisleri başlat
            for service_name in critical_services:
                # Servis mevcut mu kontrol et
                service = self.services.get(service_name)
                if not service:
                    logger.warning(f"Kritik servis bulunamadı: {service_name}")
                    continue
                
                # Servisi başlat ve hatalarla özel ilgilen
                try:
                    await self.start_service(service_name)
                except Exception as e:
                    logger.error(f"Kritik servis başlatma hatası: {service_name} - {str(e)}")
                    # Yeniden başlatmayı dene
                    try:
                        logger.warning(f"Kritik servis {service_name} yeniden başlatılıyor...")
                        await self.restart_service(service_name)
                    except Exception as e2:
                        logger.error(f"Kritik servis yeniden başlatma hatası: {service_name} - {str(e2)}")
        
        # Diğer servisleri başlat
        non_critical_services = [s for s in start_order if s not in self.critical_services]
        for service_name in non_critical_services:
            service = self.services.get(service_name)
            if not service:
                logger.warning(f"Servis bulunamadı: {service_name}")
                continue
                
            await self.start_service(service_name)
        
        # Kritik servisleri kontrol et - eğer yoksa veya çalışmıyorsa zorla
        await self.enforce_critical_services()
        
        # Watchdog'u başlat
        await self.start_watchdog()
        
        # Durumları logla
        for name, service in self.services.items():
            status = "Aktif" if hasattr(service, 'running') and service.running else "Devre dışı"
            has_run = hasattr(service, 'run') and callable(service.run)
            
            if name in self.critical_services and not has_run:
                logger.error(f"KRİTİK SERVİS {name} 'run' metoduna sahip değil! Bu servis otomatik çalışamayacak.")
            elif not has_run:
                logger.warning(f"Servis {name} 'run' metoduna sahip değil. Bu servis otomatik çalışamayacak.")
            
            logger.info(f"Servis {name}: {status} {'- Çalışma döngüsü MEVCUT' if has_run else '- Çalışma döngüsü YOK'}")
        
        all_running = all(hasattr(s, 'running') and s.running for s in self.services.values())
        logger.info(f"Servisler başlatıldı. Durum: {'Tümü Aktif' if all_running else 'Bazıları Devre Dışı'}")
        
        # Otomatik düzeltme için kriter servisleri kontrol et
        await self._check_critical_services_health()
    
    async def _check_critical_services_health(self):
        """
        Kritik servislerin düzgün çalıştığından emin olur ve gerekirse düzeltici önlemler alır.
        """
        # MessageService için özel kontrol
        message_service = self.services.get("message")
        if message_service:
            if not hasattr(message_service, 'run') or not callable(message_service.run):
                logger.critical("⚠️ MessageService'te run metodu yok! Servisler düzgün çalışamaz.")
            
            # Mesaj servisi çalışmıyorsa, zorla başlat
            if hasattr(message_service, 'is_running') and not message_service.is_running:
                logger.warning("MessageService çalışmıyor, zorla başlatılıyor!")
                try:
                    await message_service.start()
                    # Task oluştur
                    task = asyncio.create_task(message_service.run())
                    task.set_name("service_task_message")
                    self.tasks.append(task)
                    logger.info("MessageService zorla başlatıldı!")
                except Exception as e:
                    logger.error(f"MessageService zorla başlatılırken hata: {str(e)}")
            
            # Next_run_time kontrolü
            if hasattr(message_service, 'next_run_time'):
                now = datetime.now()
                # Eğer bir sonraki çalışma zamanı çok ilerideyse, yakın bir zamana getir
                if message_service.next_run_time > now + timedelta(minutes=30):
                    logger.warning(f"MessageService'in bir sonraki çalışma zamanı çok ileri: {message_service.next_run_time}")
                    message_service.next_run_time = now + timedelta(minutes=1)
                    logger.info(f"MessageService'in bir sonraki çalışma zamanı ayarlandı: {message_service.next_run_time}")
        
        # PromoService için özel kontrol
        promo_service = self.services.get("promo")
        if promo_service:
            if not hasattr(promo_service, 'run') or not callable(promo_service.run):
                logger.critical("⚠️ PromoService'te run metodu yok! Servisler düzgün çalışamaz.")
            
            # Promo servisi çalışmıyorsa, zorla başlat
            if hasattr(promo_service, 'running') and not promo_service.running:
                logger.warning("PromoService çalışmıyor, zorla başlatılıyor!")
                try:
                    await promo_service.start()
                    # Task oluştur
                    task = asyncio.create_task(promo_service.run())
                    task.set_name("service_task_promo")
                    self.tasks.append(task)
                    logger.info("PromoService zorla başlatıldı!")
                except Exception as e:
                    logger.error(f"PromoService zorla başlatılırken hata: {str(e)}")
    
    async def enforce_critical_services(self):
        """
        Kritik servislerin çalıştığından emin olur.
        Eğer herhangi bir kritik servis eksikse, onu oluşturur ve başlatır.
        """
        # Bu metod zaten var, biraz geliştirelim
        if not hasattr(self, 'critical_services'):
            self.critical_services = [
                "message",
                "promo",
                "group",
                "user",
                "error"
            ]
            
        for service_name in self.critical_services:
            if service_name not in self.services or self.services[service_name] is None:
                logger.warning(f"Kritik servis {service_name} eksik, oluşturuluyor")
                
                # Servisi tekrar oluştur
                try:
                    # Servisi oluştur
                    service = self.service_factory.create_service(service_name)
                    
                    if service:
                        # Servisi kaydedip başlat
                        self.services[service_name] = service
                        
                        # Servisi initialize et ve başlat
                        await service.initialize()
                        await service.start()
                        
                        # Run için task oluştur
                        if hasattr(service, 'run') and callable(service.run):
                            task = asyncio.create_task(service.run())
                            task.set_name(f"service_task_{service_name}")
                            self.tasks.append(task)
                            
                        logger.info(f"Kritik servis {service_name} başarıyla yeniden başlatıldı")
                    else:
                        logger.error(f"Kritik servis {service_name} oluşturulamadı")
                except Exception as e:
                    logger.error(f"Kritik servis {service_name} oluşturma hatası: {str(e)}")
                    logger.debug(traceback.format_exc())

# Global ServiceManager örneği
_service_manager = None

def get_service_manager(config=None, db=None, client=None) -> ServiceManager:
    """
    Global ServiceManager örneğini döndür, yoksa oluştur
    """
    global _service_manager
    if _service_manager is None:
        _service_manager = ServiceManager(config=config, db=db, client=client)
    return _service_manager 