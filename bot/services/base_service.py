"""
# ============================================================================ #
# Dosya: base_service.py
# Yol: /Users/siyahkare/code/telegram-bot/bot/services/base_service.py
# İşlev: Tüm servisler için temel sınıf.
#
# © 2025 SiyahKare Yazılım - Tüm Hakları Saklıdır
# ============================================================================ #
"""

import asyncio
import logging
import functools
from typing import Dict, Any, Optional, Callable
from datetime import datetime
from abc import ABC, abstractmethod
from config_helper import ConfigAdapter

logger = logging.getLogger(__name__)

class BaseService(ABC):
    """
    Tüm servisler için temel sınıf.
    
    Bu sınıf, tüm servislerde ortak olan işlevleri sağlar.
    Her servis bu sınıfı miras almalıdır.
    
    Attributes:
        service_name: Servis adı
        client: Telegram istemcisi
        config: Yapılandırma nesnesi
        db: Veritabanı bağlantısı
        db_pool: Veritabanı bağlantı havuzu
        stop_event: Durdurma eventi
        initialized: Servisin başlatılıp başlatılmadığını belirtir
        services: Diğer servislerin referansları
        _is_running: Servisin çalışıp çalışmadığını belirtir
        start_time: Servisin başlatıldığı zaman
    """
    
    def __init__(self, service_name=None, client=None, config=None, db=None, stop_event=None):
        """
        BaseService constructor.
        
        Args:
            service_name: Servis adı
            client: Telegram istemcisi
            config: Yapılandırma nesnesi
            db: Veritabanı bağlantısı
            stop_event: Durdurma eventi
        """
        self.name = service_name
        self.service_name = service_name
        self.client = client
        # Config nesnesini adaptör ile uyumlu hale getir
        self.config = ConfigAdapter.adapt_config(config)
        self.db = db
        self.db_pool = None
        self.stop_event = stop_event
        self.initialized = False
        self.services = {}
        self._is_running = False
        self.start_time = None  # Servisin başlatıldığı zaman
        
    @abstractmethod
    async def initialize(self) -> bool:
        """
        Servisi başlat ve gerekli kaynakları yükle
        
        Returns:
            bool: Başarılı ise True
        """
        self.initialized = True
        return True
        
    @abstractmethod
    async def start(self) -> bool:
        """
        Servisi başlat
        
        Returns:
            bool: Başarılı ise True
        """
        if not self.initialized:
            await self.initialize()
            
        logger.info(f"{self.name} servisi başlatılıyor...")
        self._is_running = True
        self.start_time = datetime.now()  # Start time'ı ayarla
        logger.info(f"{self.name} servisi başlatıldı.")
        return True
        
    @abstractmethod
    async def stop(self) -> None:
        """
        Servisi durdur
        
        Returns:
            None
        """
        logger.info(f"{self.name} servisi durduruluyor...")
        self._is_running = False
        logger.info(f"{self.name} servisi durduruldu.")
        
    def is_running(self) -> bool:
        """
        Servisin çalışıp çalışmadığını kontrol et
        
        Returns:
            bool: Çalışıyorsa True
        """
        return self._is_running
        
    def set_services(self, services: Dict[str, Any]) -> None:
        """
        Diğer servisleri ayarla
        
        Args:
            services: Servis adı -> Servis nesnesi eşleşmesi
        """
        self.services = services
        
    def get_service(self, service_name: str) -> Optional[Any]:
        """
        Belirli bir servisi döndür
        
        Args:
            service_name: Servis adı
            
        Returns:
            İstenen servis veya None
        """
        return self.services.get(service_name)
        
    async def run(self) -> None:
        """
        Servisin ana çalışma döngüsü.
        
        Bu metot alt sınıflar tarafından uygulanmalıdır.
        
        Returns:
            None
        """
        try:
            while not self.stop_event.is_set():
                if not self._is_running:
                    await asyncio.sleep(1)
                    continue
                    
                # Servis özel işlemleri burada yapılacak
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"{self.name} servisi çalışırken hata: {str(e)}")
            self._is_running = False
            
    async def get_status(self) -> Dict[str, Any]:
        """
        Servisin mevcut durumunu döndürür.
        
        Returns:
            Dict: Servis durum bilgileri
        """
        return {
            'name': self.service_name,
            'running': self._is_running,
            'uptime': (datetime.now() - self.start_time).total_seconds() if self.start_time else 0,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'last_error': None
        }
        
    async def get_statistics(self) -> Dict[str, Any]:
        """
        Servisin istatistiklerini döndürür.
        
        Returns:
            Dict: Servis istatistikleri
        """
        return {}
        
    async def _run_async_db_method(self, method: Callable, *args, **kwargs) -> Any:
        """
        Veritabanı metodunu thread-safe biçimde çalıştırır.
        Senkron ve asenkron metodları otomatik algılar ve uygun şekilde çalıştırır.
        
        Args:
            method: Çalıştırılacak veritabanı metodu
            *args: Metoda geçirilecek argümanlar
            **kwargs: Metoda geçirilecek anahtar kelimeli argümanlar
            
        Returns:
            Any: Metodun döndürdüğü değer
        """
        try:
            # Metod zaten bir coroutine ise (asenkron)
            if asyncio.iscoroutinefunction(method):
                return await method(*args, **kwargs)
            # Senkron bir fonksiyon ise executor kullan
            else:
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(
                    None, 
                    functools.partial(method, *args, **kwargs)
                )
        except Exception as e:
            logger.error(f"Veritabanı metodu çalıştırılırken hata: {str(e)}, metod: {method.__name__}")
            # Uygun bir varsayılan değer döndür
            if method.__name__ == 'fetchall':
                return []
            elif method.__name__ == 'fetchone':
                return None
            else:
                raise  # Diğer durumlarda hatayı yeniden fırlat

    def connect_services(self, services: Dict[str, Any]) -> None:
        """
        Diğer servislere referansları ayarlar (set_services ile aynı işlevi görür).
        
        Args:
            services: Servis adı -> Servis nesnesi eşleşmesi
        """
        self.services = services
        logger.debug(f"{self.name} servisi diğer servislere bağlandı")
        
    async def dispatch_event(self, event_name: str, data: Dict[str, Any]) -> None:
        """Diğer servislere event gönderir."""
        if not hasattr(self, 'services'):
            logger.warning(f"{self.name}: Servisler bağlanmadan event gönderilmeye çalışıldı")
            return
            
        for service_name, service in self.services.items():
            if service_name != self.name and hasattr(service, 'handle_event'):
                try:
                    await service.handle_event(event_name, self.name, data)
                except Exception as e:
                    logger.error(f"Event gönderimi sırasında hata: {str(e)}")
                    
    async def handle_event(self, event_name: str, sender: str, data: Dict[str, Any]) -> None:
        """Diğer servislerden gelen eventi işler."""
        logger.debug(f"{self.name} servisi '{event_name}' eventi aldı ({sender} göndericisinden)")
        # Alt sınıflar bu metodu override edebilir

    async def handle_error(self, error, context=None):
        """Hata yönetimi"""
        error_msg = f"❌ {self.service_name} servisinde hata: {str(error)}"
        if context:
            error_msg += f" (Bağlam: {context})"
        logger.error(error_msg)
        
    def is_active(self):
        """Servisin aktif olup olmadığını kontrol eder"""
        return self._is_running

class SomeService(BaseService):
    def __init__(self, client, config, db, stop_event=None):
        # İlk parametre olarak servis adını belirt
        super().__init__("service_name_here", client, config, db, stop_event)
        
        # Diğer başlatma kodları...