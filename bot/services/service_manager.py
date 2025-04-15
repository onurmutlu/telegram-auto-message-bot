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
import traceback
from typing import Dict, Any, List, Set, Optional, Tuple
from datetime import datetime

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
    
    def __init__(self, service_factory, client, config, db, stop_event=None):
        """
        ServiceManager sınıfının başlatıcısı.
        
        Args:
            service_factory: Servis oluşturmak için kullanılacak fabrika nesnesi
            client: Telegram istemcisi
            config: Yapılandırma nesnesi
            db: Veritabanı bağlantısı
            stop_event: Durdurma sinyali
        """
        self.service_factory = service_factory
        self.client = client
        self.config = config
        self.db = db
        self.stop_event = stop_event
        self.services = {}
        self.dependencies = {}
        self.tasks = []
        self.start_time = datetime.now()
        self.name = "service_manager"
        
        # Aktif servisler listesi
        self.active_services = [
            "user", "group", "reply", "gpt", "dm", "invite", "promo", 
            "announcement", "datamining", "message"
        ]
        
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
            'user': set(),              # UserService bağımsız çalışabilir
            'group': set(),             # GroupService bağımsız çalışabilir
            'reply': set(),             # ReplyService bağımsız çalışabilir
            'dm': {'user'},             # DMService, UserService'e bağımlıdır
            'invite': {'dm'},           # InviteService, DMService'e bağımlıdır
            'promo': {'dm', 'user'},    # PromoService, DMService ve UserService'e bağımlıdır
            'datamining': {'user'},     # DataMiningService, UserService'e bağımlıdır
            'message': {'group'},       # MessageService, GroupService'e bağımlıdır
            'gpt': set(),               # GptService bağımsız çalışabilir
            'announcement': {'group'}   # AnnouncementService, GroupService'e bağımlıdır
        }
        
    async def create_and_register_services(self, service_names: List[str]) -> Dict[str, Any]:
        """
        Belirtilen servisleri oluşturur ve kaydeder.
        
        Args:
            service_names: Oluşturulacak servis adları
            
        Returns:
            Dict: Servis adı -> Servis nesnesi eşlemesi
        """
        logger.info(f"Servisler oluşturuluyor: {', '.join(service_names)}")
        
        for name in service_names:
            try:
                service = self._create_service(name)
                if service:
                    self.services[name] = service
                    logger.info(f"Servis oluşturuldu: {name}")
                else:
                    logger.warning(f"Servis oluşturulamadı: {name}")
            except Exception as e:
                logger.error(f"Servis oluşturma hatası ({name}): {str(e)}")
                
        # Servislere referansları ilet
        self._inject_service_references()
        
        # Rate limiter'ı servislere entegre et
        try:
            from bot.utils.adaptive_rate_limiter import AdaptiveRateLimiter
            
            # Global bir rate limiter oluştur
            global_rate_limiter = AdaptiveRateLimiter(
                initial_rate=3,  # Başlangıç hızı
                period=60,       # Saniye başına
                error_backoff=1.5,
                max_jitter=2.0
            )
            
            # Her servise rate limiter ekle
            for name, service in self.services.items():
                if not hasattr(service, 'rate_limiter'):
                    setattr(service, 'rate_limiter', global_rate_limiter)
                    logger.debug(f"{name} servisine rate limiter eklendi")
        except ImportError:
            logger.warning("AdaptiveRateLimiter modülü bulunamadı, rate limiting devre dışı")
        except Exception as e:
            logger.error(f"Rate limiter oluşturma hatası: {str(e)}")
        
        return self.services

    def _create_service(self, service_type):
        """
        Belirli bir servis oluşturur.
        
        Args:
            service_type: Oluşturulacak servis tipi
            
        Returns:
            BaseService: Oluşturulan servis veya None
        """
        try:
            # Servis oluştururken tüm gerekli parametreleri geçirin
            service = self.service_factory.create_service(
                service_type,
                self.client, 
                self.config,
                self.db,
                self.stop_event
            )
            return service
        except Exception as e:
            logger.error(f"Servis oluşturma hatası ({service_type}): {str(e)}")
            return None
        
    def _inject_service_references(self):
        """Servislere diğer servislerin referanslarını enjekte eder."""
        for name, service in self.services.items():
            # Name özelliğini kontrol et ve eksikse ekle
            if not hasattr(service, 'name'):
                setattr(service, 'name', name)
                logger.warning(f"Serviste 'name' özniteliği eksik, otomatik eklendi: {name}")
            
            # service_name özelliğini kontrol et ve eksikse ekle
            if not hasattr(service, 'service_name'):
                setattr(service, 'service_name', name)
                logger.warning(f"Serviste 'service_name' özniteliği eksik, otomatik eklendi: {name}")
            
            # Referansları enjekte et
            try:
                if hasattr(service, 'set_services'):
                    service.set_services(self.services)
                    logger.debug(f"Servis referansları enjekte edildi: {name}")
            except Exception as e:
                logger.error(f"Servis referansı enjekte edilirken hata ({name}): {str(e)}")
                
    async def initialize_service_communications(self):
        """Servisleri birbirine bağlar."""
        logger.info("Servisler arası iletişim ayarlanıyor")
        
        # Her servise diğer servislere referans ver
        for name, service in self.services.items():
            if service is None:
                logger.warning(f"Servis bulunamadı: {name}")
                continue
                
            if hasattr(service, 'set_services'):
                try:
                    # Asenkron set_services varsa
                    if asyncio.iscoroutinefunction(service.set_services):
                        await service.set_services(self.services)
                    else:
                        # Normal metot ise doğrudan çağır
                        service.set_services(self.services)
                    logger.debug(f"Servis referansları enjekte edildi: {name}")
                except Exception as e:
                    logger.error(f"Servis iletişim hatası ({name}): {str(e)}")
                
    async def start_services(self) -> None:
        """
        Tüm servisleri başlatır. Bağımlılıkları göz önünde bulundurarak sıralı başlatma yapar.
        
        Returns:
            None
        """
        # Başlatma sırasını belirle (bağımlılıklara göre)
        start_order = ["user", "group", "reply", "gpt", "dm", "invite", "promo", "datamining", "message", "announcement"]
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
                    task.set_name(f"service_task_{name}")  # Task'a isim ver
                    self.tasks.append(task)
                    
                    logger.info(f"Servis başlatıldı: {name}")
                    
                except Exception as e:
                    logger.error(f"Servis başlatma hatası ({name}): {str(e)}")
        
        # Servisler arası iletişimi başlat
        await self.initialize_service_communications()
                
    async def start_service(self, service_name):
        """
        Belirli bir servisi başlatır.
        """
        if service_name not in self.services:
            logger.error(f"Servis bulunamadı: {service_name}")
            return False
            
        service = self.services[service_name]
        if not service:
            logger.error(f"Servis örneği boş: {service_name}")
            return False
            
        try:
            # Önce gerekli metodların varlığını kontrol et
            required_methods = ["initialize", "start", "run", "stop"]
            for method in required_methods:
                if not hasattr(service, method):
                    logger.error(f"Servis '{service_name}' gerekli '{method}' metoduna sahip değil")
                    return False
            
            # Önce initialize edilmiş mi kontrol et
            if not getattr(service, 'initialized', False):
                try:
                    initialized = await service.initialize()
                    if not initialized:
                        logger.error(f"Servis başlatılamadı: {service_name}")
                        return False
                except Exception as e:
                    logger.error(f"Initialize hatası ({service_name}): {str(e)}")
                    logger.debug(traceback.format_exc())
                    return False
                    
            # Servisi başlat
            try:
                started = await service.start()
                if started:
                    # run metodunu çalıştırmak için task oluştur
                    task = asyncio.create_task(service.run())
                    task.set_name(f"service_task_{service_name}")
                    self.tasks.append(task)
                    logger.info(f"Servis başlatıldı: {service_name}")
                    return True
                else:
                    logger.error(f"Servis başlatılamadı (start False döndü): {service_name}")
                    return False
            except Exception as e:
                logger.error(f"Start metodu hatası ({service_name}): {str(e)}")
                logger.debug(traceback.format_exc())
                return False
                
        except Exception as e:
            logger.error(f"Servis başlatma genel hatası ({service_name}): {str(e)}")
            logger.debug(traceback.format_exc())
            return False

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
                    
        # Görevleri iptal et ve bekle
        if self.tasks:
            for task in self.tasks:
                if not task.done() and not task.cancelled():
                    task.cancel()
            
            # İptal edilen görevlerin tamamlanmasını bekle
            try:
                await asyncio.wait(self.tasks, timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning("Bazı servis görevleri 5 saniye içinde sonlanmadı")
            except Exception as e:
                logger.error(f"Servis görevleri beklenirken hata: {str(e)}")
            
            # Task listesini temizle
            self.tasks.clear()
            
    async def get_status(self) -> Dict[str, Dict[str, Any]]:
        """
        Tüm servislerin durumunu getirir.
        
        Returns:
            Dict: Servis adı -> Servis durumu eşleşmesi
        """
        status = {}
        for name, service in self.services.items():
            try:
                if hasattr(service, 'get_status'):
                    status[name] = await service.get_status()
                else:
                    status[name] = {"running": hasattr(service, "running") and service.running}
            except Exception as e:
                logger.error(f"{name} servisi durum hatası: {str(e)}")
                status[name] = {"error": str(e)}
                
        # Service Manager'ın kendi durumu
        status["service_manager"] = {
            "running": True,
            "uptime_seconds": (datetime.now() - self.start_time).total_seconds(),
            "active_services": len(self.services),
            "active_tasks": len(self.tasks),
            "started_at": self.start_time.strftime("%Y-%m-%d %H:%M:%S")
        }
                
        return status
        
    async def get_statistics(self) -> Dict[str, Dict[str, Any]]:
        """
        Tüm servislerin istatistiklerini getirir.
        
        Returns:
            Dict: Servis adı -> Servis istatistikleri eşleşmesi
        """
        statistics = {}
        for name, service in self.services.items():
            try:
                if hasattr(service, 'get_statistics'):
                    statistics[name] = await service.get_statistics()
                else:
                    statistics[name] = {}
            except Exception as e:
                logger.error(f"{name} servisi istatistik hatası: {str(e)}")
                statistics[name] = {"error": str(e)}
                
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
            try:
                if hasattr(service, 'pause'):
                    await service.pause()
                    logger.info(f"Servis duraklatıldı: {service_name}")
                    return True
                else:
                    logger.warning(f"Servis pause metodu içermiyor: {service_name}")
            except Exception as e:
                logger.error(f"Servis duraklatma hatası ({service_name}): {str(e)}")
                
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
            try:
                if hasattr(service, 'resume'):
                    await service.resume()
                    logger.info(f"Servis devam ettirildi: {service_name}")
                    return True
                else:
                    logger.warning(f"Servis resume metodu içermiyor: {service_name}")
            except Exception as e:
                logger.error(f"Servis devam ettirme hatası ({service_name}): {str(e)}")
                
        return False
        
    async def restart_service(self, service_name: str) -> bool:
        """
        Belirli bir servisi yeniden başlatır.
        
        Args:
            service_name: Yeniden başlatılacak servis adı
            
        Returns:
            bool: Başarılı ise True
        """
        if service_name not in self.services:
            logger.warning(f"Yeniden başlatılacak servis bulunamadı: {service_name}")
            return False
            
        service = self.services[service_name]
        
        try:
            # Servisi durdur
            logger.info(f"Servis yeniden başlatılıyor: {service_name}")
            
            # İlgili taskı bul ve iptal et
            for task in self.tasks[:]:
                if task.get_name() == f"service_task_{service_name}":
                    task.cancel()
                    # Task listesinden kaldır
                    self.tasks.remove(task)
                    break
            
            # Servisi durdur
            await service.stop()
            
            # Servisi başlat
            await service.initialize()
            await service.start()
            
            # Yeni task oluştur
            task = asyncio.create_task(service.run())
            task.set_name(f"service_task_{service_name}")
            self.tasks.append(task)
            
            logger.info(f"Servis başarıyla yeniden başlatıldı: {service_name}")
            return True
            
        except Exception as e:
            logger.error(f"Servis yeniden başlatma hatası ({service_name}): {str(e)}")
            return False

    async def validate_templates(self):
        """Tüm servislerin şablonları doğru yüklediğini kontrol eder."""
        results = {}
        
        for name, service in self.services.items():
            # Her servisin şablon listelerini kontrol et
            templates = []
            if hasattr(service, 'message_templates'):
                templates.extend(getattr(service, 'message_templates', []))
            if hasattr(service, 'responses'):
                templates.extend(sum([v for v in getattr(service, 'responses', {}).values()], []))
            if hasattr(service, 'invite_templates'):
                templates.extend(getattr(service, 'invite_templates', []))
            
            results[name] = {
                "template_count": len(templates),
                "sample": templates[:2] if templates else []
            }
        
        return results

    def set_services(self, services: Dict[str, Any]) -> None:
        """
        Diğer servislere referansları ayarlar.
        
        Args:
            services: Servis adı -> Servis nesnesi eşleşmesi
        """
        self.services = services
        logger.debug(f"ServiceManager servisi diğer servislere bağlandı")
        
    def get_service(self, service_name: str) -> Optional[Any]:
        """
        İsmi belirtilen servisi döndürür.
        
        Args:
            service_name: Servis adı
            
        Returns:
            Optional[Any]: Servis nesnesi veya None
        """
        return self.services.get(service_name)
        
    def has_service(self, service_name: str) -> bool:
        """
        İsmi belirtilen servisin mevcut olup olmadığını kontrol eder.
        
        Args:
            service_name: Servis adı
            
        Returns:
            bool: Servis mevcutsa True
        """
        return service_name in self.services