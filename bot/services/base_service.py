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

logger = logging.getLogger(__name__)

class BaseService(ABC):
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
        self.is_running = False
        self.start_time = None
        self.initialized = False
        
    @abstractmethod
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
        
    @abstractmethod
    async def start(self) -> bool:
        """
        Servisi başlatır.
        
        Returns:
            bool: Başarılı ise True
        """
        if not self.initialized:
            await self.initialize()
            
        self.is_running = True
        self.start_time = datetime.now()
        logger.info(f"{self.service_name} servisi başlatıldı.")
        return True
        
    @abstractmethod
    async def stop(self) -> None:
        """
        Servisi güvenli bir şekilde durdurur.
        
        Returns:
            None
        """
        # Önce durum değişkenini güncelle
        self.is_running = False
        
        # Durdurma sinyalini ayarla (varsa)
        if hasattr(self, 'stop_event') and self.stop_event:
            self.stop_event.set()
            
        # Diğer durdurma sinyallerini de kontrol et
        if hasattr(self, 'shutdown_event'):
            self.shutdown_event.set()
        
        # Çalışan görevleri iptal et
        try:
            service_tasks = [task for task in asyncio.all_tasks() 
                        if (task.get_name().startswith(f"{self.name}_task_") or
                            task.get_name().startswith(f"{self.service_name}_task_")) and 
                        not task.done() and not task.cancelled()]
                        
            for task in service_tasks:
                task.cancel()
                
            # Kısa bir süre bekle
            try:
                await asyncio.sleep(0.5)
            except asyncio.CancelledError:
                pass
                
            # İptal edilen görevlerin tamamlanmasını kontrol et
            if service_tasks:
                await asyncio.wait(service_tasks, timeout=2.0)
        except Exception as e:
            logger.error(f"{self.service_name} görevleri iptal edilirken hata: {str(e)}")
            
        logger.info(f"{self.service_name} servisi durduruldu.")
        
    async def run(self) -> None:
        """
        Servisin ana çalışma döngüsü.
        
        Bu metot alt sınıflar tarafından uygulanmalıdır.
        
        Returns:
            None
        """
        try:
            while not self.stop_event.is_set():
                if not self.is_running:
                    await asyncio.sleep(1)
                    continue
                    
                # Servis özel işlemleri burada yapılacak
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"{self.name} servisi çalışırken hata: {str(e)}")
            self.is_running = False
            
    async def get_status(self) -> Dict[str, Any]:
        """
        Servisin mevcut durumunu döndürür.
        
        Returns:
            Dict: Servis durum bilgileri
        """
        return {
            'name': self.service_name,
            'running': self.is_running,
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

    async def handle_error(self, error, context=None):
        """Hata yönetimi"""
        error_msg = f"❌ {self.service_name} servisinde hata: {str(error)}"
        if context:
            error_msg += f" (Bağlam: {context})"
        logger.error(error_msg)
        
    def is_active(self):
        """Servisin aktif olup olmadığını kontrol eder"""
        return self.is_running

class SomeService(BaseService):
    def __init__(self, client, config, db, stop_event=None):
        # İlk parametre olarak servis adını belirt
        super().__init__("service_name_here", client, config, db, stop_event)
        
        # Diğer başlatma kodları...