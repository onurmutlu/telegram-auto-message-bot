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
from typing import Dict, Any, Optional
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
        self.client = client
        self.config = config
        self.db = db
        self.stop_event = stop_event
        self.running = False
        self.start_time = None
        self.initialized = False
        
    async def initialize(self) -> bool:
        """
        Servisi başlatmadan önce hazırlar.
        
        Returns:
            bool: Başarılı ise True
        """
        self.initialized = True
        logger.info(f"{self.service_name} servisi başlatılıyor...")
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
        
    async def _run_async_db_method(self, method, *args, **kwargs) -> Any:
        """
        Veritabanı metodlarını asenkron olarak çalıştırmak için yardımcı metod.
        
        Args:
            method: Çalıştırılacak metod
            *args: Metoda geçirilecek pozisyonel argümanlar
            **kwargs: Metoda geçirilecek anahtar kelime argümanları
            
        Returns:
            Any: Metodun dönüş değeri
        """
        try:
            if asyncio.iscoroutinefunction(method):
                return await method(*args, **kwargs)
            else:
                # Asenkron olmayan metodları bir executor'da çalıştır
                return await asyncio.to_thread(method, *args, **kwargs)
        except Exception as e:
            logger.error(f"DB işlemi hatası: {str(e)}")
            return None