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

logger = logging.getLogger(__name__)

class BaseService:
    """
    Tüm servisler için temel sınıf.
    
    Her servis, bu temel sınıftan türetilmelidir. Temel sınıf, tüm servislerde
    ortak olan işlevselliği sağlar.
    
    Attributes:
        service_name: Servis adı
        client: Telethon istemcisi
        config: Uygulama yapılandırması
        db: Veritabanı bağlantısı
        stop_event: Durdurma sinyali için asyncio.Event nesnesi
        running: Servisin çalışıp çalışmadığını belirtir
        start_time: Servisin başlangıç zamanı
        initialized: Servisin başlatılıp başlatılmadığını belirtir
    """
    
    def __init__(self, service_name: str, client: Any, config: Any, db: Any, stop_event: asyncio.Event):
        """
        BaseService sınıfının başlatıcısı.
        
        Args:
            service_name: Servis adı
            client: Telethon istemcisi
            config: Uygulama yapılandırması  
            db: Veritabanı bağlantısı
            stop_event: Durdurma sinyali için asyncio.Event nesnesi
        """
        self.service_name = service_name
        self.name = service_name  # Her iki özelliği de ayarlıyoruz - bu tutarsızlık sorununu çözecek
        self.client = client
        self.config = config
        self.db = db
        self.stop_event = stop_event
        self.running = False
        self.start_time = None
        self.initialized = False
        
    async def initialize(self) -> bool:
        """
        Temel servisi başlatır.
        """
        # İstemcinin UserBot mu yoksa Bot mu olduğunu kontrol et (her zaman UserBot olarak ayarla)
        self._is_user_mode = True
        
        # Oturum başlama zamanını kaydet
        self.start_time = datetime.now()
        
        # Durum bilgisi
        logger.info(f"{self.name} servisi başlatılıyor...")
        
        return True
        
    async def start(self) -> bool:
        """
        Servisi başlatır.
        
        Returns:
            bool: Başarılı ise True
        """
        if not self.initialized:
            await self.initialize()
            
        self.running = True
        self.start_time = datetime.now()
        logger.info(f"{self.service_name} servisi başlatıldı.")
        return True
        
    async def stop(self) -> None:
        """
        Servisi güvenli bir şekilde durdurur.
        
        Returns:
            None
        """
        self.running = False
        logger.info(f"{self.service_name} servisi durduruldu.")
        
    async def run(self) -> None:
        """
        Servisin ana çalışma döngüsü.
        
        Bu metot alt sınıflar tarafından uygulanmalıdır.
        
        Returns:
            None
        """
        raise NotImplementedError("Her servis kendi run metodunu uygulamalıdır.")
        
    async def get_status(self) -> Dict[str, Any]:
        """
        Servisin mevcut durumunu döndürür.
        
        Returns:
            Dict: Servis durum bilgileri
        """
        return {
            'name': self.service_name,
            'running': self.running,
            'uptime': (datetime.now() - self.start_time).total_seconds() if self.start_time else 0,
            'start_time': self.start_time.isoformat() if self.start_time else None
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
        
        Args:
            method: Çalıştırılacak veritabanı metodu
            *args: Metoda geçirilecek argümanlar
            **kwargs: Metoda geçirilecek anahtar kelimeli argümanlar
            
        Returns:
            Any: Metodun döndürdüğü değer
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, 
            functools.partial(method, *args, **kwargs)
        )

    def set_services(self, services: Dict[str, Any]) -> None:
        """
        Diğer servislere referansları ayarlar.
        
        Args:
            services: Servis adı -> Servis nesnesi eşleşmesi
        """
        self.services = services
        logger.debug(f"{self.name} servisi diğer servislere bağlandı")
        
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

class SomeService(BaseService):
    def __init__(self, client, config, db, stop_event=None):
        # İlk parametre olarak servis adını belirt
        super().__init__("service_name_here", client, config, db, stop_event)
        
        # Diğer başlatma kodları...