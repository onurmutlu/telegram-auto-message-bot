import asyncio
import logging
from typing import Optional, Dict, Any, ClassVar, List
from abc import ABC, abstractmethod

from app.core.config import settings
from app.core.scheduler import scheduler

logger = logging.getLogger(__name__)

class ConfigAdapter:
    """
    Servisler için yapılandırma ayarları adaptörü.
    
    Farklı kaynaklardan (dosya, veritabanı, çevre değişkenleri) gelen
    ayarları tek bir arayüzle sunar.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = config or {}
        
    def get(self, key: str, default: Any = None) -> Any:
        """
        Ayar değerini getirir.
        
        Args:
            key: Ayar anahtarı
            default: Bulunamazsa döndürülecek varsayılan değer
            
        Returns:
            Any: Ayar değeri
        """
        # Önce iç yapılandırmaya bak
        if key in self._config:
            return self._config[key]
        
        # Çevre değişkenlerine bak
        env_key = key.upper()
        if hasattr(settings, env_key):
            return getattr(settings, env_key)
            
        # En son varsayılan değeri döndür
        return default
        
    def set(self, key: str, value: Any) -> None:
        """
        Ayar değerini ayarlar.
        
        Args:
            key: Ayar anahtarı
            value: Ayar değeri
        """
        self._config[key] = value
        
    def update(self, config_dict: Dict[str, Any]) -> None:
        """
        Ayarları günceller.
        
        Args:
            config_dict: Yeni ayarları içeren sözlük
        """
        self._config.update(config_dict)
        
    def get_all(self) -> Dict[str, Any]:
        """
        Tüm ayarları döndürür.
        
        Returns:
            Dict[str, Any]: Tüm ayarlar
        """
        return self._config.copy()


class BaseService(ABC):
    """
    Tüm servisler için temel sınıf.
    
    Asenkron başlatma, durdurma ve güncelleme işlemlerini sağlar.
    """
    
    # Sınıf değişkenleri
    service_name: ClassVar[str] = "base_service"
    default_interval: ClassVar[int] = 60  # Varsayılan güncelleme aralığı (saniye)
    
    def __init__(
        self,
        client=None,
        config: Optional[Dict[str, Any]] = None,
        stop_event: Optional[asyncio.Event] = None,
        **kwargs
    ):
        """
        Servis başlatma.
        
        Args:
            client: Telegram istemcisi
            config: Yapılandırma ayarları
            stop_event: Durdurma eventi
            **kwargs: Ek parametreler
        """
        self.client = client
        self.config = ConfigAdapter(config)
        self.stop_event = stop_event or asyncio.Event()
        self.running = False
        self._job_ids: List[str] = []
        
        # Ek parametreleri ayarla
        for key, value in kwargs.items():
            setattr(self, key, value)
            
        self.logger = logging.getLogger(f"service.{self.get_service_name()}")
        self.logger.info(f"{self.get_service_name()} servisi başlatıldı")
        
    @classmethod
    def get_service_name(cls) -> str:
        """
        Servis adını döndürür.
        
        Returns:
            str: Servis adı
        """
        return cls.service_name
        
    async def initialize(self) -> bool:
        """
        Servisi başlatma öncesi hazırlık yapar.
        Bu metod, service_manager.py tarafından kullanılır.
        
        Returns:
            bool: Başlatma hazırlığı başarılıysa True
        """
        return await self._start()
        
    async def start(self) -> bool:
        """
        Servisi başlatır.
        
        Returns:
            bool: Başlatma başarılıysa True
        """
        try:
            if self.running:
                self.logger.warning(f"{self.get_service_name()} servisi zaten çalışıyor")
                return True
                
            self.logger.info(f"{self.get_service_name()} servisi başlatılıyor")
            
            # Servisin özel başlatma işlemlerini çağır
            result = await self._start()
            
            if result:
                self.running = True
                
                # Güncelleme görevini zamanlayıcıya ekle
                interval = self.config.get("update_interval", self.default_interval)
                job_id = await scheduler.add_interval_job(
                    func=self.update,
                    seconds=interval,
                    job_id=f"{self.get_service_name()}_update"
                )
                self._job_ids.append(job_id)
                
                self.logger.info(f"{self.get_service_name()} servisi başlatıldı (aralık: {interval}s)")
            else:
                self.logger.error(f"{self.get_service_name()} servisi başlatılamadı")
                
            return result
        except Exception as e:
            self.logger.exception(f"{self.get_service_name()} başlatma hatası: {str(e)}")
            return False
            
    async def stop(self) -> bool:
        """
        Servisi durdurur.
        
        Returns:
            bool: Durdurma başarılıysa True
        """
        try:
            if not self.running:
                self.logger.warning(f"{self.get_service_name()} servisi zaten durmuş")
                return True
                
            self.logger.info(f"{self.get_service_name()} servisi durduruluyor")
            
            # Zamanlayıcı görevlerini kaldır
            for job_id in self._job_ids:
                scheduler.remove_job(job_id)
            self._job_ids.clear()
            
            # Durdurma olayını tetikle
            self.stop_event.set()
            
            # Servisin özel durdurma işlemlerini çağır
            result = await self._stop()
            
            if result:
                self.running = False
                self.logger.info(f"{self.get_service_name()} servisi durduruldu")
            else:
                self.logger.error(f"{self.get_service_name()} servisi durdurulamadı")
                
            return result
        except Exception as e:
            self.logger.exception(f"{self.get_service_name()} durdurma hatası: {str(e)}")
            return False
            
    async def update(self) -> None:
        """
        Servis güncelleme işlevini çağırır.
        Bu metod zamanlayıcı tarafından çağrılır.
        """
        try:
            # Servis durdurulduysa güncelleme yapma
            if self.stop_event.is_set() or not self.running:
                return
                
            # Alt sınıfın güncelleme işlemini çağır
            await self._update()
        except Exception as e:
            self.logger.exception(f"{self.get_service_name()} güncelleme hatası: {str(e)}")
            
    async def restart(self) -> bool:
        """
        Servisi yeniden başlatır.
        
        Returns:
            bool: Yeniden başlatma başarılıysa True
        """
        await self.stop()
        # Durdurma eventi yenileniyor
        self.stop_event = asyncio.Event()
        return await self.start()
    
    async def run(self) -> None:
        """
        Servisin ana döngüsü. Bu metod service_manager.py tarafından çağrılır.
        Varsayılan olarak asenkron uyku döngüsü ile çalışır ve _update metodunu çağırır.
        
        Bu metod override edilebilir ancak genellikle gerekli değildir.
        """
        self.logger.info(f"{self.get_service_name()} run() metodu başlatıldı")
        
        # Service manager tarafından başlatıldığında
        if not self.running:
            await self.start()
            
        try:
            while not self.stop_event.is_set() and self.running:
                try:
                    # _update metodunu çağır - scheduler'dan bağımsız olarak
                    await self._update()
                except Exception as e:
                    self.logger.exception(f"{self.get_service_name()} run güncelleme hatası: {str(e)}")
                    
                # Servis özel aralığına göre bekle
                await asyncio.sleep(self.default_interval)
                
        except asyncio.CancelledError:
            self.logger.info(f"{self.get_service_name()} run() metodu iptal edildi")
            # Durdurma işlemini çağır
            await self.stop()
        except Exception as e:
            self.logger.exception(f"{self.get_service_name()} run() metodu hatası: {str(e)}")
        finally:
            self.logger.info(f"{self.get_service_name()} run() metodu sonlandı")
            
    @abstractmethod
    async def _start(self) -> bool:
        """
        Alt sınıflar tarafından uygulanacak başlatma metodu.
        
        Returns:
            bool: Başlatma başarılıysa True
        """
        pass
        
    @abstractmethod
    async def _stop(self) -> bool:
        """
        Alt sınıflar tarafından uygulanacak durdurma metodu.
        
        Returns:
            bool: Durdurma başarılıysa True
        """
        pass
        
    @abstractmethod
    async def _update(self) -> None:
        """
        Alt sınıflar tarafından uygulanacak güncelleme metodu.
        """
        pass 