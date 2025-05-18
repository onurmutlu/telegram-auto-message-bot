#!/usr/bin/env python3
import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Any, Optional, Union, List

logger = logging.getLogger(__name__)

class ConfigAdapter:
    """Yapılandırma adaptörü sınıfı."""
    
    @staticmethod
    def get_config(key: str, default: Any = None) -> Any:
        """Yapılandırma değerini al."""
        from app.core.config import settings
        return getattr(settings, key, default)

class BaseService(ABC):
    """
    Servisler için temel sınıf.
    
    Tüm servisler bu sınıftan türetilmeli ve gerekli metodları uygulamalıdır.
    Temel servis yaşam döngüsü yönetimi burada gerçekleştirilir.
    """
    
    def __init__(self, name: str, interval: int = 60):
        """BaseService başlatıcısı."""
        self.name = name
        self.interval = interval
        self.running = False
        self.initialized = False
        self.start_time = None
        self.last_run_time = None
        self.error_count = 0
        self.success_count = 0
        self.status_history: List[Dict[str, Any]] = []
        self._task: Optional[asyncio.Task] = None
        logger.info(f"{self.name} servisi başlatıldı")
    
    async def initialize(self) -> bool:
        """
        Servisi başlat.
        
        Bu metod, servis başlatıldığında bir kez çağrılır.
        Veritabanı bağlantıları, kaynak tahsisi vb. işlemler burada yapılmalıdır.
        
        Returns:
            bool: Başlatma başarılı ise True
        """
        try:
            success = await self._start()
            self.initialized = success
            logger.info(f"Service '{self.name}' initialized: {success}")
            return success
        except Exception as e:
            logger.error(f"Error initializing service '{self.name}': {e}", exc_info=True)
            self.initialized = False
            return False
    
    async def start(self):
        """
        Servisi çalıştır.
        
        Bu metod, servisin ana döngüsünü başlatır ve arka planda çalışmasını sağlar.
        """
        if not self.initialized:
            logger.warning(f"Service '{self.name}' not initialized, initializing now")
            self.initialized = await self.initialize()
            
            if not self.initialized:
                logger.error(f"Failed to initialize service '{self.name}', cannot start")
                return
        
        if self.running:
            logger.warning(f"Service '{self.name}' already running")
            return
        
        logger.info(f"Starting service '{self.name}'")
        self.running = True
        self.start_time = datetime.now()
        
        # Arka planda çalışacak görevi oluştur
        self._task = asyncio.create_task(self._run_loop(), name=f"service_{self.name}")
    
    async def _run_loop(self):
        """Servisin ana çalışma döngüsü."""
        logger.info(f"Service '{self.name}' started")
        
        while self.running:
            try:
                self.last_run_time = datetime.now()
                
                # Servisin ana işini çalıştır
                success = await self._update()
                
                if success:
                    self.success_count += 1
                else:
                    self.error_count += 1
                    
                # Son durumu kaydet
                self._update_status_history()
                
                # Belirlenen aralık kadar bekle
                await asyncio.sleep(self.interval)
                
            except asyncio.CancelledError:
                logger.info(f"Service '{self.name}' task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in service '{self.name}': {e}", exc_info=True)
                self.error_count += 1
                # Hata durumunda daha kısa bekle
                await asyncio.sleep(min(self.interval, 30))  # En fazla 30 saniye bekle
    
    def _update_status_history(self):
        """Servis çalışma durumunu güncelle."""
        status = {
            "timestamp": datetime.now().isoformat(),
            "running": self.running,
            "success": self.success_count,
            "errors": self.error_count,
            "last_run": self.last_run_time.isoformat() if self.last_run_time else None
        }
        
        self.status_history.append(status)
        
        # Sadece son 10 durumu sakla
        if len(self.status_history) > 10:
            self.status_history.pop(0)
    
    async def stop(self):
        """Servisi durdur."""
        if not self.running:
            logger.warning(f"Service '{self.name}' not running")
            return
        
        logger.info(f"Stopping service '{self.name}'")
        self.running = False
        
        # Eğer görev varsa, iptal et ve tamamlanmasını bekle
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        
        # Servis kapanış işlemlerini yap
        success = await self._stop()
        logger.info(f"Service '{self.name}' stopped: {success}")
    
    async def cleanup(self):
        """
        Servis kapatılırken temizlik işleri.
        
        Kaynakları serbest bırakma, bağlantıları kapatma işlemleri burada yapılmalıdır.
        """
        try:
            if self.running:
                await self.stop()
            
            logger.info(f"Cleaning up service '{self.name}'")
            # Ek temizlik işlemleri burada yapılabilir
            
            self.initialized = False
            logger.info(f"Service '{self.name}' cleanup completed")
        except Exception as e:
            logger.error(f"Error during cleanup of service '{self.name}': {e}", exc_info=True)
    
    async def get_status(self) -> Dict[str, Any]:
        """
        Servisin mevcut durumunu döndür.
        
        Returns:
            Dict[str, Any]: Servis durum bilgileri
        """
        uptime = (datetime.now() - self.start_time).total_seconds() if self.start_time else 0
        
        return {
            "name": self.name,
            "running": self.running,
            "initialized": self.initialized,
            "uptime_seconds": uptime,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "last_run": self.last_run_time.isoformat() if self.last_run_time else None,
            "success_count": self.success_count,
            "error_count": self.error_count,
            "interval": self.interval
        }
    
    async def set_interval(self, seconds: int) -> bool:
        """
        Servisin çalışma aralığını değiştir.
        
        Args:
            seconds: Yeni çalışma aralığı (saniye)
            
        Returns:
            bool: İşlem başarılı ise True
        """
        if seconds < 1:
            logger.warning(f"Invalid interval for service '{self.name}': {seconds}")
            return False
        
        self.interval = seconds
        logger.info(f"Service '{self.name}' interval updated to {seconds} seconds")
        return True
    
    @abstractmethod
    async def _start(self) -> bool:
        """
        Servis başlatma özel işlemleri.
        
        Alt sınıflar tarafından uygulanmalıdır.
        
        Returns:
            bool: Başlatma başarılı ise True
        """
        pass
    
    @abstractmethod
    async def _stop(self) -> bool:
        """
        Servis durdurma özel işlemleri.
        
        Alt sınıflar tarafından uygulanmalıdır.
        
        Returns:
            bool: Durdurma başarılı ise True
        """
        pass
    
    @abstractmethod
    async def _update(self) -> bool:
        """
        Servisin periyodik olarak çalıştıracağı iş.
        
        Alt sınıflar tarafından uygulanmalıdır.
        
        Returns:
            bool: İşlem başarılı ise True
        """
        pass 